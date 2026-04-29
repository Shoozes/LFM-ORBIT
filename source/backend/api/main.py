import asyncio
import base64
import json
import logging
import os
import warnings
from contextlib import asynccontextmanager
from datetime import date
from typing import Any

try:
    from sentinelhub import SHRateLimitWarning
    warnings.filterwarnings('ignore', category=SHRateLimitWarning)
except ImportError:
    SHRateLimitWarning = None  # type: ignore[assignment]

from core.grid import cell_to_boundary, cell_to_latlng, is_supported_cell_id, normalize_bbox
import httpx
from fastapi import FastAPI, HTTPException, Path, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from core.analyzer import analyze_alert
from core.agent_bus import get_bus_stats, get_recent_dialogue, list_pins, delete_pin, upsert_pin, post_message as bus_post
from core.config import (
    PROVIDER_FALLBACK_ORDER,
    PROVIDER_NASA_DIRECT,
    PROVIDER_SENTINELHUB_DIRECT,
    PROVIDER_SIMSAT_MAPBOX,
    PROVIDER_SIMSAT_SENTINEL,
    REGION,
    get_runtime_mode_summary,
    resolve_nasa_credentials,
    resolve_sentinel_credentials,
)
from core.depth_anything import (
    DepthAnythingUnavailable,
    estimate_depth_summary,
    get_depth_anything_status,
    set_depth_anything_enabled,
)
from core.gallery import list_gallery, get_gallery_item
from core.ground_agent import run_ground_agent
from core.inference import model_status as llm_model_status
from core.ice_snow_monitoring import score_ice_snow_extent
from core.lifeline_monitoring import (
    build_lifeline_monitor_report,
    evaluate_lifeline_predictions,
    list_lifeline_assets,
)
from core.link_state import is_link_connected, set_link_state
from core.maritime_monitoring import (
    build_maritime_monitor_report,
    normalize_maritime_timestamp,
)
from core.metrics import read_metrics_summary
from core.mission import get_active_mission, list_missions, start_mission, stop_mission
from core.queue import get_alert_counts, get_recent_alerts
from core.replay import list_seeded_replays, load_seeded_replay, rescan_seeded_replay
from core.runtime_state import ensure_runtime_state, reset_runtime_state
from core.satellite_agent import run_satellite_agent
from core.scanner import stream_region_scan
from core.simsat_client import get_simsat_client, SimSatConfig
from core.telemetry import build_health_payload
from core.temporal_use_cases import (
    classify_temporal_use_case as classify_temporal_use_case_record,
    list_temporal_use_cases,
)
from core.timelapse import generate_timelapse_frames
from core.vlm import explain_vlm_caption, explain_vlm_grounding, explain_vlm_vqa

logger = logging.getLogger(__name__)


def _normalize_bbox_for_request(value: list[float] | None) -> list[float] | None:
    if value is None:
        return None
    try:
        return normalize_bbox(value)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc


def _date_key(value: str | None) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    parts = text.split("-")
    if len(parts) > 3:
        raise ValueError("date must use YYYY, YYYY-MM, or YYYY-MM-DD")
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) >= 2 else 1
        day = int(parts[2]) if len(parts) >= 3 else 1
        return date(year, month, day)
    except (TypeError, ValueError) as exc:
        raise ValueError("date must use YYYY, YYYY-MM, or YYYY-MM-DD") from exc


def _validate_date_order(start_date: str | None, end_date: str | None) -> None:
    start_key = _date_key(start_date)
    end_key = _date_key(end_date)
    if start_key and end_key and start_key > end_key:
        raise ValueError("start_date must be on or before end_date")


def _should_reset_on_boot() -> bool:
    return os.getenv("RESET_RUNTIME_STATE_ON_BOOT", "false").lower() in ("true", "1", "yes")


def _should_run_agent_pair_on_boot() -> bool:
    return os.getenv("RUN_AGENT_PAIR_ON_BOOT", "true").lower() not in ("false", "0", "no")


def _cors_allow_origins() -> list[str]:
    configured = os.getenv("ORBIT_CORS_ALLOW_ORIGINS", "").strip()
    if configured:
        origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
        if origins:
            return origins
    return [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ]


def _require_local_request(request: Request | None = None) -> None:
    if request is None:
        return
    host = request.client.host if request.client else ""
    if host in {"127.0.0.1", "::1", "localhost", "testclient"}:
        return
    raise HTTPException(status_code=403, detail="Local-only control endpoint")


def _is_windows_transport_disconnect_noise(context: dict[str, Any]) -> bool:
    exc = context.get("exception")
    handle = str(context.get("handle") or "")
    return (
        isinstance(exc, ConnectionResetError)
        and "_ProactorBasePipeTransport._call_connection_lost" in handle
    )


def _install_asyncio_disconnect_noise_filter() -> None:
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()

    def _handler(loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
        if _is_windows_transport_disconnect_noise(context):
            logger.debug("Suppressed benign Windows websocket disconnect noise: %s", context.get("exception"))
            return
        if previous_handler is not None:
            previous_handler(loop, context)
            return
        loop.default_exception_handler(context)

    loop.set_exception_handler(_handler)


def _decode_bus_payload(raw_payload: str):
    try:
        return json.loads(raw_payload)
    except Exception:
        return {"note": str(raw_payload)}


async def _safe_send_text(websocket: WebSocket, payload: dict) -> bool:
    try:
        await websocket.send_text(json.dumps(payload))
        return True
    except RuntimeError as exc:
        if "close message has been sent" in str(exc):
            return False
        raise


@asynccontextmanager
async def lifespan(_: FastAPI):
    _install_asyncio_disconnect_noise_filter()

    reset = _should_reset_on_boot()
    if reset:
        reset_runtime_state()
    else:
        ensure_runtime_state()

    mode = get_runtime_mode_summary()
    logger.info(
        "[BOOT] provider=%s",
        mode["active_provider"],
    )

    stop_event = asyncio.Event()
    agent_tasks: list[asyncio.Task] = []
    if _should_run_agent_pair_on_boot():
        agent_tasks = [
            asyncio.create_task(run_satellite_agent(stop_event)),
            asyncio.create_task(run_ground_agent(stop_event)),
        ]
        logger.info("Agent pair launched: satellite_agent + ground_agent")
    else:
        logger.info("Agent pair launch skipped by RUN_AGENT_PAIR_ON_BOOT=false")

    yield

    stop_event.set()
    for task in agent_tasks:
        task.cancel()
    try:
        if agent_tasks:
            await asyncio.gather(*agent_tasks, return_exceptions=True)
    except Exception as exc:
        logger.debug("Agent pair shutdown gather raised: %s", exc)
    logger.info("Agent pair stopped.")


app = FastAPI(
    title="LFM Orbit API",
    description="Satellite-first forest and infrastructure intelligence system",
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return build_health_payload(get_alert_counts())


@app.get("/api/alerts/recent")
def recent_alerts(limit: int = Query(default=50, ge=1, le=200)):
    return get_recent_alerts(limit=limit)


@app.get("/api/metrics/summary")
def metrics_summary():
    return read_metrics_summary()


class LinkStateBody(BaseModel):
    connected: bool


@app.get("/api/link/status")
def link_status():
    """Return local SAT-to-ground downlink state for replay exercises."""
    connected = is_link_connected()
    stats = get_bus_stats()
    return {
        "connected": connected,
        "state": "LINK OPEN" if connected else "LINK OFFLINE",
        "queued_messages": stats["unread_messages"],
    }


@app.post("/api/link/state")
def update_link_state(body: LinkStateBody, request: Request = None):
    """Toggle local downlink connectivity without restarting the stack."""
    _require_local_request(request)
    set_link_state(body.connected)
    bus_post(
        sender="operator",
        recipient="broadcast",
        msg_type="status",
        payload={
            "connected": body.connected,
            "note": "LINK RESTORED" if body.connected else "LINK OFFLINE",
        },
    )
    return link_status()



@app.get("/api/simsat/status")
def simsat_status():
    """
    Check SimSat API connection status and configuration.
    
    Returns information about SimSat availability and token configuration.
    """
    config = SimSatConfig.from_env()
    client = get_simsat_client()
    
    return {
        "simsat_base_url": config.base_url,
        "simsat_available": client.is_available(),
        "mapbox_token_configured": bool(config.mapbox_token),
        "timeout_seconds": config.timeout_seconds,
        "endpoints": {
            "sentinel_historical": "/data/image/sentinel",
            "sentinel_current": "/data/current/image/sentinel",
            "mapbox_historical": "/data/image/mapbox",
            "mapbox_current": "/data/current/image/mapbox",
        },
    }


@app.get("/api/provider/status")
def provider_status():
    """
    Provider status endpoint.

    Returns the active provider, availability of each provider tier,
    credential detection status, the fallback policy, and the current runtime
    truth/origin/scoring fields so callers can self-describe the evidence mode.
    """
    client = get_simsat_client()
    sentinel_creds = resolve_sentinel_credentials()
    nasa_creds = resolve_nasa_credentials()
    simsat_config = SimSatConfig.from_env()

    simsat_available = client.is_available()
    sentinelhub_available = sentinel_creds.available
    nasa_available = nasa_creds.available

    mode = get_runtime_mode_summary()
    return {
        "active_provider": REGION.observation_mode,
        "runtime_truth_mode": mode["runtime_truth_mode"],
        "imagery_origin": mode["imagery_origin"],
        "scoring_basis": mode["scoring_basis"],
        "demo_mode_enabled": mode["demo_mode_enabled"],
        "imagery_backed_scoring_enabled": mode["imagery_backed_scoring_enabled"],
        "providers": {
            PROVIDER_SIMSAT_SENTINEL: {
                "available": simsat_available,
                "description": "Official SimSat API endpoint",
            },
            PROVIDER_SIMSAT_MAPBOX: {
                "available": simsat_available and bool(simsat_config.mapbox_token),
                "credential_source": "env" if simsat_config.mapbox_token else "unavailable",
                "description": "Optional SimSat Mapbox imagery endpoint",
            },
            PROVIDER_SENTINELHUB_DIRECT: {
                "available": sentinelhub_available,
                "credential_source": sentinel_creds.source,
                "description": "Direct Sentinel Hub access",
            },
            PROVIDER_NASA_DIRECT: {
                "available": nasa_available,
                "credential_source": nasa_creds.source,
                "description": "Direct NASA API fallback",
            },
        },
        "sentinel_secret_detected": sentinelhub_available,
        "sentinel_credential_source": sentinel_creds.source,
        "fallback_order": list(PROVIDER_FALLBACK_ORDER),
    }


@app.get("/api/temporal/use-cases")
def temporal_use_cases():
    """Return temporal scan use cases, methods, and starter examples."""
    cases = list_temporal_use_cases()
    return {"use_cases": cases, "count": len(cases)}


@app.post("/api/temporal/classify")
def temporal_classify(body: dict):
    """Auto-select the temporal use case for mission, alert, or API-prep metadata."""
    requested = body.get("use_case_id") if isinstance(body, dict) else None
    return classify_temporal_use_case_record(body if isinstance(body, dict) else {}, requested)


class LifelineMonitorBody(BaseModel):
    asset_id: str | None = Field(default=None, max_length=120)
    asset: dict[str, Any] | None = None
    candidate: dict[str, Any] = Field(default_factory=dict)
    baseline_frame: dict[str, Any] = Field(default_factory=dict)
    current_frame: dict[str, Any] = Field(default_factory=dict)
    task_text: str = Field(default="", max_length=1000)


class LifelineEvalBody(BaseModel):
    cases: list[dict[str, Any]] = Field(min_length=1, max_length=200)


class IceSnowScoreBody(BaseModel):
    frames: list[dict[str, Any]] = Field(min_length=1, max_length=120)
    runtime_truth_mode: str = Field(default="replay", max_length=40)
    imagery_origin: str = Field(default="cached_api", max_length=80)
    observation_source: str = Field(default="seeded_sentinelhub_multispectral_replay", max_length=120)
    min_accepted_frames: int = Field(default=3, ge=2, le=24)


@app.get("/api/lifelines/assets")
def lifeline_assets(category: str | None = None, region: str | None = None):
    """Return seeded civilian lifeline assets for before/after monitoring."""
    assets = list_lifeline_assets(category=category, region=region)
    return {"assets": assets, "count": len(assets)}


@app.post("/api/lifelines/monitor")
def lifeline_monitor(body: LifelineMonitorBody):
    """Build a before/after civilian lifeline report and downlink decision."""
    try:
        return build_lifeline_monitor_report(
            asset_id=body.asset_id,
            asset=body.asset,
            candidate=body.candidate,
            baseline_frame=body.baseline_frame,
            current_frame=body.current_frame,
            task_text=body.task_text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/lifelines/evaluate")
def lifeline_evaluate(body: LifelineEvalBody):
    """Evaluate lifeline candidate decisions against expected actions."""
    return evaluate_lifeline_predictions(body.cases)


@app.post("/api/ice-snow/score")
def ice_snow_score(body: IceSnowScoreBody):
    """Score long-window ice/snow extent from Sentinel-2 L2A frame summaries."""
    return score_ice_snow_extent(
        body.frames,
        runtime_truth_mode=body.runtime_truth_mode,
        imagery_origin=body.imagery_origin,
        observation_source=body.observation_source,
        min_accepted_frames=body.min_accepted_frames,
    )


class MaritimeMonitorBody(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    timestamp: str | None = None
    task_text: str = Field(default="", max_length=1000)
    anomaly_description: str = Field(default="", max_length=1000)
    include_stac: bool = False
    radius_km: float = Field(default=10.0, gt=0.0, le=100.0)
    distance_km: float = Field(default=10.0, gt=0.0, le=100.0)
    max_items: int = Field(default=4, ge=1, le=12)
    max_cloud_cover: int = Field(default=30, ge=0, le=100)

    @field_validator("timestamp")
    @classmethod
    def _valid_timestamp(cls, value: str | None) -> str | None:
        if value is None or not str(value).strip():
            return None
        return normalize_maritime_timestamp(value)


@app.post("/api/maritime/monitor")
def maritime_monitor(body: MaritimeMonitorBody):
    """Build an Orbit-native maritime monitor and cardinal investigation plan."""
    return build_maritime_monitor_report(
        lat=body.lat,
        lon=body.lon,
        timestamp=body.timestamp,
        task_text=body.task_text,
        anomaly_description=body.anomaly_description,
        include_stac=body.include_stac,
        radius_km=body.radius_km,
        distance_km=body.distance_km,
        max_items=body.max_items,
        max_cloud_cover=body.max_cloud_cover,
    )


@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        await stream_region_scan(websocket)
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("WebSocket telemetry stream error")
        return


@app.websocket("/ws/agent-dialogue")
async def agent_dialogue_websocket(websocket: WebSocket):
    """
    Real-time agent dialogue stream.
    Sends all agent_bus messages as they arrive (polling every 0.8s).
    Frontend receives the full conversation between satellite and ground agents.
    """
    from core.agent_bus import _connect as _bus_connect

    await websocket.accept()
    last_id = 0

    # Send recent history on connect
    try:
        history = get_recent_dialogue(limit=40)
        if history:
            last_id = max(m["id"] for m in history)
            if not await _safe_send_text(websocket, {"type": "history", "messages": history}):
                return
    except Exception as exc:
        logger.debug("Agent dialogue history bootstrap failed: %s", exc)

    try:
        while True:
            await asyncio.sleep(0.8)

            with _bus_connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, sender, recipient, msg_type, cell_id, payload, timestamp
                    FROM agent_messages
                    WHERE id > ?
                    ORDER BY id ASC
                    LIMIT 30
                    """,
                    (last_id,),
                ).fetchall()

            if rows:
                messages = [
                    {
                        "id": r["id"],
                        "sender": r["sender"],
                        "recipient": r["recipient"],
                        "msg_type": r["msg_type"],
                        "cell_id": r["cell_id"],
                        "payload": _decode_bus_payload(r["payload"]),
                        "timestamp": r["timestamp"],
                    }
                    for r in rows
                ]
                last_id = messages[-1]["id"]
                if not await _safe_send_text(websocket, {"type": "messages", "messages": messages}):
                    return

    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("Agent dialogue WebSocket error")


# ---------------------------------------------------------------------------
# Agent bus REST endpoints
# ---------------------------------------------------------------------------

@app.get("/api/agent/bus/stats")
def agent_bus_stats():
    """Return agent message bus statistics."""
    return get_bus_stats()


@app.get("/api/agent/bus/dialogue")
def agent_bus_dialogue(limit: int = Query(default=60, ge=1, le=200)):
    """Return recent agent dialogue messages in chronological order."""
    return {"messages": get_recent_dialogue(limit=limit)}


@app.post("/api/agent/bus/inject")
def inject_operator_message(body: dict, request: Request = None):
    """
    Inject an operator message into the agent bus.
    Allows the human operator to interrupt agents with queries or commands.
    """
    _require_local_request(request)
    content = str(body.get("message", "")).strip()
    if not content:
        return JSONResponse(status_code=400, content={"error": "message is required"})

    msg_id = bus_post(
        sender="operator",
        recipient="ground",
        msg_type="query",
        cell_id=body.get("cell_id"),
        payload={
            "message": content,
            "note": f"Operator message: {content}",
        },
    )
    return {"id": msg_id, "status": "injected"}


# ---------------------------------------------------------------------------
# Map pins endpoints
# ---------------------------------------------------------------------------

class PinBody(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)
    label: str = ""
    note: str = ""
    cell_id: str | None = None


@app.get("/api/map/pins")
def get_map_pins():
    """Return all map pins (satellite, ground, operator)."""
    return {"pins": list_pins()}


@app.post("/api/map/pins")
def drop_operator_pin(body: PinBody):
    """Drop an operator (OPR) pin on the map."""
    label = body.label.strip() or f"OPR ★ ({body.lat:.3f}, {body.lng:.3f})"
    pin_id = upsert_pin(
        pin_type="operator",
        lat=body.lat,
        lng=body.lng,
        label=label,
        note=body.note or "Operator marker.",
        cell_id=body.cell_id,
    )
    return {"id": pin_id, "status": "dropped"}


@app.delete("/api/map/pins/{pin_id}")
def remove_pin(pin_id: int):
    """Remove a pin by id."""
    removed = delete_pin(pin_id)
    if not removed:
        return JSONResponse(status_code=404, content={"error": "Pin not found"})
    return {"status": "removed"}



class BboxRequest(BaseModel):
    bbox: list[float]

    @field_validator("bbox")
    @classmethod
    def _valid_bbox(cls, value: list[float]) -> list[float]:
        normalized = _normalize_bbox_for_request(value)
        if normalized is None:
            raise ValueError("bbox is required")
        return normalized


class AlertAnalysisBody(BaseModel):
    change_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)
    before_window: dict = Field(default_factory=dict)
    after_window: dict = Field(default_factory=dict)
    observation_source: str = Field(default="unknown")
    demo_forced_anomaly: bool = Field(default=False)

@app.post("/api/analysis/timelapse")
def analysis_timelapse(body: BboxRequest):
    from core.analyzer import analyze_timelapse

    analysis_text = analyze_timelapse(body.bbox)
    return {"analysis": analysis_text}

@app.post("/api/analysis/alert")
def analyze_alert_endpoint(body: AlertAnalysisBody):
    """
    Analyze a deforestation alert using AI.

    Production path: Uses offline LFM signal analysis (CPU-only, deterministic).
    The offline path is always available and requires no external services.
    """
    return analyze_alert(
        change_score=body.change_score,
        confidence=body.confidence,
        reason_codes=body.reason_codes,
        before_window=body.before_window,
        after_window=body.after_window,
        observation_source=body.observation_source,
        demo_forced_anomaly=body.demo_forced_anomaly,
    )


# ---------------------------------------------------------------------------
# Mission Control endpoints
# ---------------------------------------------------------------------------

class MissionStartBody(BaseModel):
    task_text: str = Field(min_length=1, max_length=1000)
    bbox: list[float] | None = None   # [west, south, east, north]
    start_date: str | None = None
    end_date: str | None = None
    use_case_id: str | None = None

    @field_validator("task_text")
    @classmethod
    def _strip_task_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("task_text is required")
        return text

    @field_validator("bbox")
    @classmethod
    def _valid_optional_bbox(cls, value: list[float] | None) -> list[float] | None:
        return _normalize_bbox_for_request(value)

    @model_validator(mode="after")
    def _valid_date_order(self) -> "MissionStartBody":
        _validate_date_order(self.start_date, self.end_date)
        return self


class RuntimeResetBody(BaseModel):
    clear_observation_store_files: bool = False


@app.post("/api/mission/start")
def mission_start(body: MissionStartBody, request: Request = None):
    """Start a new autonomous scan mission. Agents will restrict scanning to bbox if provided."""
    _require_local_request(request)
    mission = start_mission(
        task_text=body.task_text,
        bbox=body.bbox,
        start_date=body.start_date,
        end_date=body.end_date,
        use_case_id=body.use_case_id,
    )
    # Announce the mission on the agent bus
    bus_post(
        sender="operator",
        recipient="broadcast",
        msg_type="mission",
        payload={
            "mission_id": mission["id"],
            "task": mission["task_text"],
            "bbox": mission["bbox"],
            "temporal_use_case": mission.get("use_case_decision"),
            "note": f"[MISSION #{mission['id']}] Operator tasked: {mission['task_text']}",
        },
    )
    return mission


@app.get("/api/mission/current")
def mission_current():
    """Return the currently active mission, or null."""
    m = get_active_mission()
    return {"mission": m}


@app.post("/api/mission/stop")
def mission_stop(request: Request = None):
    """Stop the active mission."""
    _require_local_request(request)
    active = get_active_mission()
    stop_mission()
    bus_post(
        sender="operator",
        recipient="broadcast",
        msg_type="mission",
        payload={
            "task": "IDLE",
            "note": (
                "[REPLAY] Operator exited replay. Resuming realtime sweep."
                if active and active.get("mission_mode") == "replay"
                else "[MISSION] Operator stopped mission. Resuming full-grid sweep."
            ),
        },
    )
    return {"status": "stopped"}


@app.get("/api/mission/history")
def mission_history(limit: int = Query(default=20, ge=1, le=100)):
    """Return recent mission history."""
    return {"missions": list_missions(limit=limit)}


@app.get("/api/replay/catalog")
def replay_catalog():
    """Return bundled replay missions available in this workspace."""
    return {"replays": list_seeded_replays()}


@app.post("/api/replay/load/{replay_id}")
def replay_load(replay_id: str = Path(...), request: Request = None):
    """Reset runtime state and load a bundled replay mission into the standard app surfaces."""
    _require_local_request(request)
    try:
        return load_seeded_replay(replay_id)
    except FileNotFoundError as exc:
        return JSONResponse(status_code=404, content={"error": str(exc)})
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@app.post("/api/replay/rescan/{replay_id}")
def replay_rescan(replay_id: str = Path(...), request: Request = None):
    """Start a live rescan from a replay mission using the current runtime/model stack."""
    _require_local_request(request)
    try:
        return rescan_seeded_replay(replay_id)
    except FileNotFoundError as exc:
        return JSONResponse(status_code=404, content={"error": str(exc)})
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@app.post("/api/runtime/reset")
def runtime_reset(body: RuntimeResetBody | None = None, request: Request = None):
    """Reset mutable runtime state for deterministic local runs, demos, and tests."""
    _require_local_request(request)
    payload = body or RuntimeResetBody()
    summary = reset_runtime_state(
        clear_observation_store_files=payload.clear_observation_store_files,
    )
    return {
        "status": "reset",
        **summary,
    }



class CredentialsBody(BaseModel):
    client_id: str
    client_secret: str

@app.post("/api/settings/credentials")
def update_credentials(body: CredentialsBody, request: Request = None):
    """Save Sentinel Hub credentials to the secrets file."""
    _require_local_request(request)
    from pathlib import Path

    secrets_dir = Path(__file__).resolve().parents[3] / ".tools" / ".secrets"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    secrets_file = secrets_dir / "sentinel.txt"

    with open(secrets_file, "w", encoding="utf-8") as f:
        f.write(f"SENTINEL_CLIENT_ID={body.client_id}\n")
        f.write(f"SENTINEL_CLIENT_SECRET={body.client_secret}\n")

    return {"status": "ok"}

# ---------------------------------------------------------------------------
# Gallery endpoints
# ---------------------------------------------------------------------------

@app.get("/api/gallery")
def get_gallery(
    mission_id: int | None = Query(default=None),
    severity: str | None = Query(default=None),
    limit: int = Query(default=60, ge=1, le=200),
):
    """Return gallery metadata (imagery thumbnails excluded — use /api/gallery/{cell_id} for images)."""
    items = list_gallery(mission_id=mission_id, severity=severity, limit=limit)
    return {"items": items, "total": len(items)}


@app.get("/api/gallery/{cell_id}")
def get_gallery_cell(cell_id: str = Path(...)):
    """Return full gallery item including context thumbnail."""
    item = get_gallery_item(cell_id)
    if not item:
        return JSONResponse(status_code=404, content={"error": "Cell not in gallery"})
    return item


# ---------------------------------------------------------------------------
# Timelapse endpoints
# ---------------------------------------------------------------------------

class TimelapseBody(BboxRequest):
    start_date: str
    end_date: str
    steps: int = Field(default=12, ge=2, le=24)

    @model_validator(mode="after")
    def _valid_date_order(self) -> "TimelapseBody":
        _validate_date_order(self.start_date, self.end_date)
        return self


@app.post("/api/timelapse/generate")
def generate_timelapse(body: TimelapseBody):
    """Generate a timelapse WebM video for a bounding box over a time range."""
    result = generate_timelapse_frames(
        bbox=body.bbox,
        start_date=body.start_date,
        end_date=body.end_date,
        steps=body.steps
    )
    return result


@app.get("/api/inference/status")
def inference_status():
    """LFM GGUF model load status for the satellite inference engine."""
    return llm_model_status()


@app.get("/api/analysis/status")
def analysis_status():
    """
    AI analysis model availability status.

    The satellite can optionally use a locally resolved GGUF artifact for
    live triage reasoning. Ground analysis uses the offline LFM signal
    analyzer which is always available.
    """
    ms = llm_model_status()
    gguf_name = ms.get("name", "LFM2.5-VL-450M-Q4_0.gguf")
    return {
        "default_model": "offline_lfm_v1",
        "optional_model": gguf_name,
        "satellite_inference_loaded": ms.get("loaded", False),
        "models": {
            "offline_lfm_v1": {
                "available": True,
                "description": "Offline LFM signal analysis -- production, CPU-only",
                "requires": "none",
            },
            gguf_name: {
                "available": ms.get("loaded", False),
                "description": "Optional GGUF artifact for satellite triage reasoning",
                "path": ms.get("path", ""),
                "repo_id": ms.get("repo_id", ""),
                "revision": ms.get("revision", ""),
                "source": ms.get("source", ""),
                "manifest_path": ms.get("manifest_path", ""),
                "mmproj_path": ms.get("mmproj_path", ""),
                "source_handoff_path": ms.get("source_handoff_path", ""),
                "source_handoff_present": ms.get("source_handoff_present", False),
                "training_result_manifest": ms.get("training_result_manifest", ""),
                "training_result_manifest_path": ms.get("training_result_manifest_path", ""),
                "training_result_manifest_present": ms.get("training_result_manifest_present", False),
                "readme_path": ms.get("readme_path", ""),
                "readme_present": ms.get("readme_present", False),
                "requires": "llama-cpp-python",
            },
        },
        "note": (
            "Satellite triage can use a resolved GGUF artifact for live reasoning. "
            "Ground validation always uses offline_lfm_v1."
        ),
    }


# ---------------------------------------------------------------------------
# Vision-Language Model (VLM) endpoints
# ---------------------------------------------------------------------------

class VlmGroundingBody(BboxRequest):
    prompt: str

class VlmVqaBody(BboxRequest):
    question: str

class VlmCaptionBody(BboxRequest):
    """Caption request for a validated bbox."""


class DepthAnythingSettingsBody(BaseModel):
    enabled: bool


class DepthEstimateBody(BaseModel):
    image_b64: str = Field(..., min_length=1)

@app.post("/api/vlm/grounding")
def vlm_grounding(body: VlmGroundingBody):
    return explain_vlm_grounding(body.bbox, body.prompt)

@app.post("/api/vlm/vqa")
def vlm_vqa(body: VlmVqaBody):
    return explain_vlm_vqa(body.bbox, body.question)

@app.post("/api/vlm/caption")
def vlm_caption(body: VlmCaptionBody):
    return explain_vlm_caption(body.bbox)


@app.get("/api/depth/status")
def depth_status():
    """Optional Depth Anything V3 runtime status."""
    return get_depth_anything_status()


@app.post("/api/depth/settings")
def depth_settings(body: DepthAnythingSettingsBody):
    """Toggle Depth Anything V3 for the current backend process."""
    return set_depth_anything_enabled(body.enabled)


@app.post("/api/depth/estimate")
def depth_estimate(body: DepthEstimateBody):
    """Run optional Depth Anything V3 and return compact depth statistics."""
    try:
        return estimate_depth_summary(body.image_b64)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except DepthAnythingUnavailable as exc:
        return JSONResponse(status_code=409, content={"error": str(exc), "status": get_depth_anything_status()})

# ---------------------------------------------------------------------------
# Ground Agent Chat endpoint  (LFM-native — no external API key required)
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


@app.post("/api/agent/chat")
def ground_agent_chat(request: ChatRequest):
    """
    Ground Station Chat Agent.
    LFM-native intent classifier — reads live metrics and DB state.
    No external API key required.
    """
    if not request.messages:
        return {"reply": "No message received."}
    last_msg = request.messages[-1].content
    from core.ground_agent_knowledge import get_ground_agent_reply
    return {"reply": get_ground_agent_reply(last_msg)}


# ---------------------------------------------------------------------------
# Imagery endpoints
# ---------------------------------------------------------------------------

_ESRI_SATELLITE_EXPORT = (
    "https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/export"
)
_IMAGERY_TIMEOUT = 12.0


def _cell_bbox(cell_id: str, buffer_deg: float = 0.025) -> tuple[float, float, float, float]:
    """Return a (west, south, east, north) bounding box around an H3 cell.

    Args:
        cell_id: H3 cell identifier.
        buffer_deg: Extra padding in degrees added on all sides of the cell boundary.
            Default 0.025° ≈ 2.8 km at the equator, giving useful imagery context.

    Returns:
        Tuple of (west, south, east, north) in WGS-84 decimal degrees.
    """
    boundary = cell_to_boundary(cell_id)
    lats = [p[0] for p in boundary]
    lngs = [p[1] for p in boundary]
    return (
        min(lngs) - buffer_deg,
        min(lats) - buffer_deg,
        max(lngs) + buffer_deg,
        max(lats) + buffer_deg,
    )


def _fetch_esri_image(bbox: tuple[float, float, float, float], size: int = 256) -> str | None:
    """Fetch a satellite imagery chip from ESRI World Imagery and return it as a base64 data URL."""
    west, south, east, north = bbox
    params = {
        "bbox": f"{west},{south},{east},{north}",
        "bboxSR": "4326",
        "imageSR": "4326",
        "size": f"{size},{size}",
        "format": "png32",
        "f": "image",
        "transparent": "false",
    }
    try:
        with httpx.Client(timeout=_IMAGERY_TIMEOUT) as client:
            response = client.get(_ESRI_SATELLITE_EXPORT, params=params)
        if response.status_code == 200 and response.headers.get("content-type", "").startswith("image/"):
            encoded = base64.b64encode(response.content).decode("ascii")
            return f"data:image/png;base64,{encoded}"
        logger.warning("ESRI imagery fetch returned HTTP %d", response.status_code)
        return None
    except Exception as exc:
        logger.warning("ESRI imagery fetch error: %s", exc)
        return None


def _fetch_simsat_image(
    lat: float, lng: float, date: str | None = None
) -> str | None:
    """Fetch a satellite imagery chip from SimSat and return it as a base64 data URL."""
    try:
        client = get_simsat_client()
        if not client.is_available():
            return None

        if REGION.observation_mode == PROVIDER_SIMSAT_MAPBOX:
            if date:
                response = client.fetch_mapbox_historical(
                    lat=lat,
                    lng=lng,
                    date=date,
                    width=512,
                    height=512,
                )
            else:
                response = client.fetch_mapbox_current(lat=lat, lng=lng, width=512, height=512)
        elif date:
            response = client.fetch_sentinel_historical(lat=lat, lng=lng, date=date)
        else:
            response = client.fetch_sentinel_current(lat=lat, lng=lng)

        if response.success and response.image_data:
            content_type = (response.metadata or {}).get("content_type", "image/png")
            if not content_type or not content_type.startswith("image/"):
                content_type = "image/png"
            encoded = base64.b64encode(response.image_data).decode("ascii")
            return f"data:{content_type};base64,{encoded}"
        return None
    except Exception as exc:
        logger.warning("SimSat imagery fetch error: %s", exc)
        return None


@app.get("/api/imagery/cell/{cell_id}")
def cell_imagery(
    cell_id: str = Path(..., description="H3 cell identifier"),
    size: int = Query(default=256, ge=64, le=512, description="Image size in pixels"),
):
    """
    Fetch before/after satellite imagery chips for an H3 cell.

    Returns ESRI World Imagery for spatial context (always available) and
    SimSat before/after imagery when the SimSat API is reachable.
    Images are returned as base64-encoded data URLs.
    """
    if not is_supported_cell_id(cell_id):
        return JSONResponse(status_code=400, content={"error": "Unsupported or invalid cell_id"})

    try:
        centroid_lat, centroid_lng = cell_to_latlng(cell_id)
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid cell_id"})

    bbox = _cell_bbox(cell_id)

    # Context image (ESRI — always attempted)
    context_image = _fetch_esri_image(bbox, size=size)

    # Before/after from SimSat when available
    before_image: str | None = None
    after_image: str | None = None
    imagery_source = "esri_arcgis"

    simsat_client = get_simsat_client()
    if simsat_client.is_available():
        before_image = _fetch_simsat_image(centroid_lat, centroid_lng, date=REGION.before_label)
        after_image = _fetch_simsat_image(centroid_lat, centroid_lng, date=None)
        if before_image or after_image:
            imagery_source = (
                "simsat_mapbox"
                if REGION.observation_mode == PROVIDER_SIMSAT_MAPBOX
                else "simsat_sentinel"
            )

    return {
        "cell_id": cell_id,
        "centroid_lat": round(centroid_lat, 6),
        "centroid_lng": round(centroid_lng, 6),
        "cell_bbox": list(bbox),  # convert tuple → list for JSON array serialization
        "imagery_source": imagery_source,
        "before_label": REGION.before_label,
        "after_label": REGION.after_label,
        "context_image": context_image,
        "before_image": before_image,
        "after_image": after_image,
    }
