import base64
import logging
import os
import warnings
from contextlib import asynccontextmanager
from datetime import datetime, timezone

try:
    from sentinelhub import SHRateLimitWarning
    warnings.filterwarnings('ignore', category=SHRateLimitWarning)
except ImportError:
    pass

from core.grid import cell_to_boundary, cell_to_latlng
import httpx
from fastapi import FastAPI, Path, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.analyzer import analyze_alert
from core.agent_bus import get_bus_stats, get_recent_dialogue, init_bus, list_pins, delete_pin, upsert_pin, post_message as bus_post
from core.config import (
    PROVIDER_SENTINELHUB_DIRECT,
    PROVIDER_SIMSAT_SENTINEL,
    REGION,
    get_runtime_mode_summary,
    resolve_sentinel_credentials,
)
from core.gallery import list_gallery, get_gallery_item
from core.ground_agent import run_ground_agent
from core.inference import model_status as llm_model_status
from core.link_state import is_link_connected, set_link_state
from core.metrics import init_metrics, read_metrics_summary
from core.mission import get_active_mission, list_missions, start_mission, stop_mission, reset_missions
from core.queue import get_alert_counts, get_recent_alerts, init_db
from core.satellite_agent import run_satellite_agent
from core.scanner import stream_region_scan
from core.sentinel_provider import is_sentinelhub_available
from core.simsat_client import get_simsat_client, SimSatConfig
from core.telemetry import build_health_payload
from core.timelapse import generate_timelapse_frames
from core.vlm import run_vlm_grounding, run_vlm_vqa, run_vlm_caption

logger = logging.getLogger(__name__)


def _should_reset_on_boot() -> bool:
    return os.getenv("RESET_RUNTIME_STATE_ON_BOOT", "false").lower() in ("true", "1", "yes")


@asynccontextmanager
async def lifespan(_: FastAPI):
    import asyncio
    reset = _should_reset_on_boot()
    init_db(reset=reset)
    init_metrics(reset=reset)
    init_bus(reset=reset)
    if reset:
        reset_missions()

    mode = get_runtime_mode_summary()
    logger.info(
        "[BOOT] provider=%s",
        mode["active_provider"],
    )

    stop_event = asyncio.Event()
    sat_task = asyncio.create_task(run_satellite_agent(stop_event))
    gnd_task = asyncio.create_task(run_ground_agent(stop_event))
    logger.info("Agent pair launched: satellite_agent + ground_agent")

    yield

    stop_event.set()
    sat_task.cancel()
    gnd_task.cancel()
    try:
        await asyncio.gather(sat_task, gnd_task, return_exceptions=True)
    except Exception:
        pass
    logger.info("Agent pair stopped.")


app = FastAPI(
    title="Canopy Sentinel API",
    description="Satellite-first deforestation triage system",
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
        "timeout_seconds": config.timeout_seconds,
        "endpoints": {
            "sentinel_historical": "/data/image/sentinel",
            "sentinel_current": "/data/current/image/sentinel",
        },
    }


@app.get("/api/provider/status")
def provider_status():
    """
    Provider status endpoint.

    Returns the active provider, availability of each provider tier,
    credential detection status, the fallback policy, and the current
    demo/semi-real truth flags so callers can self-describe the scoring mode.
    """
    config = SimSatConfig.from_env()
    client = get_simsat_client()
    sentinel_creds = resolve_sentinel_credentials()
    mode = get_runtime_mode_summary()

    simsat_available = client.is_available()
    sentinelhub_available = sentinel_creds.available

    return {
        "active_provider": REGION.observation_mode,
        "demo_mode_enabled": False,
        "describe_demo_as_semi_real": False,
        "providers": {
            PROVIDER_SIMSAT_SENTINEL: {
                "available": simsat_available,
                "description": "Official SimSat API (hackathon submission path)",
            },
            PROVIDER_SENTINELHUB_DIRECT: {
                "available": sentinelhub_available,
                "credential_source": sentinel_creds.source,
                "description": "Direct Sentinel Hub access",
            },
        },

        "sentinel_credential_source": sentinel_creds.source,
    }


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
    import asyncio
    import json as _json

    await websocket.accept()
    last_id = 0

    # Send recent history on connect
    try:
        history = get_recent_dialogue(limit=40)
        if history:
            last_id = max(m["id"] for m in history)
            await websocket.send_text(_json.dumps({"type": "history", "messages": history}))
    except Exception:
        pass

    try:
        while True:
            await asyncio.sleep(0.8)

            from core.agent_bus import _connect as _bus_connect
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
                import json
                messages = [
                    {
                        "id": r["id"],
                        "sender": r["sender"],
                        "recipient": r["recipient"],
                        "msg_type": r["msg_type"],
                        "cell_id": r["cell_id"],
                        "payload": json.loads(r["payload"]),
                        "timestamp": r["timestamp"],
                    }
                    for r in rows
                ]
                last_id = messages[-1]["id"]
                await websocket.send_text(_json.dumps({"type": "messages", "messages": messages}))

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
def inject_operator_message(body: dict):
    """
    Inject an operator message into the agent bus.
    Allows the human operator to interrupt agents with queries or commands.
    """
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
    lat: float
    lng: float
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



class AlertAnalysisBody(BaseModel):
    change_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)
    before_window: dict = Field(default_factory=dict)
    after_window: dict = Field(default_factory=dict)
    observation_source: str = Field(default="unknown")
    demo_forced_anomaly: bool = Field(default=False)

@app.post("/api/analysis/timelapse")
def analysis_timelapse(body: dict):
    from core.analyzer import analyze_timelapse
    
    bbox = body.get("bbox")
    if not bbox or len(bbox) != 4:
        return {"error": "Invalid bounding box array"}
        
    analysis_text = analyze_timelapse(bbox)
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
    task_text: str
    bbox: list[float] | None = None   # [west, south, east, north]
    start_date: str | None = None
    end_date: str | None = None


@app.post("/api/mission/start")
def mission_start(body: MissionStartBody):
    """Start a new autonomous scan mission. Agents will restrict scanning to bbox if provided."""
    if not body.task_text.strip():
        return JSONResponse(status_code=400, content={"error": "task_text is required"})
    mission = start_mission(
        task_text=body.task_text.strip(),
        bbox=body.bbox,
        start_date=body.start_date,
        end_date=body.end_date,
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
def mission_stop():
    """Stop the active mission."""
    stop_mission()
    bus_post(
        sender="operator",
        recipient="broadcast",
        msg_type="mission",
        payload={"task": "IDLE", "note": "[MISSION] Operator stopped mission. Resuming full-grid sweep."},
    )
    return {"status": "stopped"}


@app.get("/api/mission/history")
def mission_history(limit: int = Query(default=20, ge=1, le=100)):
    """Return recent mission history."""
    return {"missions": list_missions(limit=limit)}



class CredentialsBody(BaseModel):
    client_id: str
    client_secret: str

@app.post("/api/settings/credentials")
def update_credentials(body: CredentialsBody):
    """Save Sentinel Hub credentials to the secrets file."""
    import os
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

class TimelapseBody(BaseModel):
    bbox: list[float]  # [w, s, e, n]
    start_date: str
    end_date: str
    steps: int = 12


@app.post("/api/timelapse/generate")
def generate_timelapse(body: TimelapseBody):
    """Generate a timelapse MP4 video for a bounding box over a time range."""
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

    The satellite uses the embedded LFM GGUF model (llama-cpp-python) for
    live triage reasoning.  Ground analysis uses the offline LFM signal
    analyzer which is always available.
    """
    ms = llm_model_status()
    gguf_name = ms.get("name", "LFM2.5-1.2B-Thinking-Q4_K_M.gguf")
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
                "description": "LFM 2.5 1.2B Thinking GGUF -- satellite triage reasoning",
                "path": ms.get("path", ""),
                "requires": "llama-cpp-python",
            },
        },
        "note": (
            "Satellite triage uses the GGUF model for live reasoning. "
            "Ground validation always uses offline_lfm_v1."
        ),
    }


# ---------------------------------------------------------------------------
# Vision-Language Model (VLM) mock endpoints
# ---------------------------------------------------------------------------

class VlmGroundingBody(BaseModel):
    bbox: list[float]
    prompt: str

class VlmVqaBody(BaseModel):
    bbox: list[float]
    question: str

class VlmCaptionBody(BaseModel):
    bbox: list[float]

@app.post("/api/vlm/grounding")
def vlm_grounding(body: VlmGroundingBody):
    items = run_vlm_grounding(body.bbox, body.prompt)
    return {"results": items}

@app.post("/api/vlm/vqa")
def vlm_vqa(body: VlmVqaBody):
    answer = run_vlm_vqa(body.bbox, body.question)
    return {"answer": answer}

@app.post("/api/vlm/caption")
def vlm_caption(body: VlmCaptionBody):
    caption = run_vlm_caption(body.bbox)
    return {"caption": caption}

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

        if date:
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
            imagery_source = "simsat_sentinel"

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