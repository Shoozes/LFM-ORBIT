"""Mission replay support.

Loads curated, local-first replay packs into the existing runtime tables so
the standard Mission / Logs / Inspect / Agent Dialogue surfaces can walk a
judge through a completed mission without waiting for a realtime scan loop.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.agent_bus import mark_messages_read, post_message, upsert_pin
from core.gallery import add_gallery_item, resolve_seeded_thumbnail
from core.metrics import seed_metrics_summary
from core.mission import get_mission, start_mission, update_mission_progress
from core.queue import estimate_payload_bytes, push_alert
from core.runtime_state import reset_runtime_state

_REPLAYS_DIR = Path(__file__).resolve().parent.parent / "assets" / "replays"
_SEEDED_DIR = Path(__file__).resolve().parent.parent / "assets" / "seeded_data"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _replay_paths() -> list[Path]:
    return sorted(_REPLAYS_DIR.glob("*.json"))


def _seeded_meta_paths() -> list[Path]:
    return sorted(_SEEDED_DIR.glob("sh_*_meta.json"))


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Replay manifest {path.name} must contain an object")
    return data


def _seeded_replay_id(signature: str) -> str:
    return f"seeded_cache_sh_{signature}"


def _seeded_meta_to_replay_spec(path: Path) -> dict[str, Any] | None:
    data = _load_json(path)
    signature = str(data.get("chunk_signature") or path.stem.removeprefix("sh_").removesuffix("_meta"))
    asset_key = f"sh_{signature}"
    webm_path = _SEEDED_DIR / f"{asset_key}.webm"
    if not webm_path.exists():
        return None
    frames_count = int(data.get("frames_count") or 0)
    if frames_count < 2:
        return None

    bbox = data.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None
    lat = float(data.get("lat") or (float(bbox[1]) + float(bbox[3])) / 2.0)
    lon = float(data.get("lon") or (float(bbox[0]) + float(bbox[2])) / 2.0)
    location = str(data.get("location_name") or f"Replay cache {signature}")
    target_task = str(data.get("target_task") or "temporal_change_review")
    target_category = str(data.get("target_category") or data.get("use_case_id") or "temporal_change")
    use_case_id = str(data.get("use_case_id") or target_category or "temporal_change_generic")
    frame_dates = [str(item) for item in data.get("frame_dates", []) if item]
    before_label = frame_dates[0] if frame_dates else str(data.get("start_date") or "baseline")
    after_label = frame_dates[-1] if frame_dates else str(data.get("end_date") or "current")
    source = str(data.get("source") or "seeded_sentinelhub_replay")
    summary = (
        f"Fast replay generated from replay cache {asset_key}: {frames_count} cloud-gated frames "
        f"for {target_category.replace('_', ' ')}."
    )

    return {
        "replay_id": _seeded_replay_id(signature),
        "source_kind": "seeded_cache",
        "title": location,
        "description": str(data.get("region_note") or summary),
        "summary": summary,
        "task_text": (
            f"Replay {location} and review {target_task.replace('_', ' ')} with current proof surfaces."
        ),
        "bbox": bbox,
        "start_date": data.get("start_date"),
        "end_date": data.get("end_date"),
        "use_case_id": use_case_id,
        "cells_scanned": 1,
        "flags_found": 1,
        "primary_cell_id": f"seeded_{signature}",
        "alerts": [
            {
                "seeded_video": asset_key,
                "event_id": f"replay_seeded_{signature}",
                "cell_id": f"seeded_{signature}",
                "lat": lat,
                "lng": lon,
                "change_score": 0.0,
                "confidence": 0.68,
                "priority": "review",
                "reason_codes": ["seeded_data", "training_ready", use_case_id],
                "observation_source": "seeded_sentinelhub_replay",
                "before_window": {"label": before_label},
                "after_window": {"label": after_label},
                "timelapse_analysis": str(data.get("vlm_explanation") or summary),
                "analysis_summary": summary,
                "satellite_note": f"Replay cache restored from {source}.",
                "ground_note": "Ground review can inspect the cached timelapse immediately, or rescan the same bbox with the current runtime model.",
                "findings": [
                    f"{frames_count} accepted frames",
                    f"source: {source}",
                    f"use case: {use_case_id}",
                ],
            }
        ],
    }


def _load_replay_spec(replay_id: str) -> dict[str, Any]:
    for path in _replay_paths():
        data = _load_json(path)
        if str(data.get("replay_id")) == replay_id:
            data.setdefault("source_kind", "curated_replay")
            return data
    for path in _seeded_meta_paths():
        data = _seeded_meta_to_replay_spec(path)
        if data and data["replay_id"] == replay_id:
            return data
    raise ValueError(f"Unknown replay_id '{replay_id}'")


def list_seeded_replays() -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    for path in _replay_paths():
        data = _load_json(path)
        alerts = list(data.get("alerts") or [])
        primary_cell_id = str(
            data.get("primary_cell_id")
            or (alerts[0].get("cell_id") if alerts else "")
        )
        catalog.append(
            {
                "replay_id": str(data.get("replay_id") or path.stem),
                "source_kind": "curated_replay",
                "title": str(data.get("title") or path.stem),
                "description": str(data.get("description") or ""),
                "task_text": str(data.get("task_text") or ""),
                "summary": str(data.get("summary") or ""),
                "bbox": data.get("bbox"),
                "start_date": data.get("start_date"),
                "end_date": data.get("end_date"),
                "cells_scanned": int(data.get("cells_scanned") or 0),
                "flags_found": int(data.get("flags_found") or len(alerts)),
                "primary_cell_id": primary_cell_id,
                "alert_count": len(alerts),
            }
        )
    curated_ids = {item["replay_id"] for item in catalog}
    for path in _seeded_meta_paths():
        data = _seeded_meta_to_replay_spec(path)
        if not data or data["replay_id"] in curated_ids:
            continue
        alerts = list(data.get("alerts") or [])
        catalog.append(
            {
                "replay_id": data["replay_id"],
                "source_kind": "seeded_cache",
                "title": str(data.get("title") or data["replay_id"]),
                "description": str(data.get("description") or ""),
                "task_text": str(data.get("task_text") or ""),
                "summary": str(data.get("summary") or ""),
                "bbox": data.get("bbox"),
                "start_date": data.get("start_date"),
                "end_date": data.get("end_date"),
                "use_case_id": data.get("use_case_id"),
                "cells_scanned": int(data.get("cells_scanned") or 0),
                "flags_found": int(data.get("flags_found") or len(alerts)),
                "primary_cell_id": str(data.get("primary_cell_id") or (alerts[0].get("cell_id") if alerts else "")),
                "alert_count": len(alerts),
            }
        )
    return catalog


def _seeded_video_data_url(asset_key: str) -> str:
    asset_path = _SEEDED_DIR / f"{asset_key}.webm"
    if not asset_path.exists():
        raise FileNotFoundError(f"Missing replay asset: {asset_path.name}")
    return "data:video/webm;base64," + base64.b64encode(asset_path.read_bytes()).decode("ascii")


def _seeded_signature(asset_key: str) -> str:
    parts = asset_key.split("_", 1)
    return parts[1] if len(parts) == 2 else asset_key


def _severity_to_action(alert: dict[str, Any]) -> str:
    custom_action = str(alert.get("ground_action") or "").strip()
    if custom_action:
        return custom_action

    priority = str(alert.get("priority") or "")
    if priority == "critical":
        return "ESCALATE — replay confirms severe canopy-loss evidence."
    if priority == "high":
        return "CONFIRM — replay supports durable canopy removal."
    if priority == "medium":
        return "MONITOR — replay shows supporting evidence with lower urgency."
    return "ARCHIVE — replay below escalation threshold."


def _alert_payload_bytes(alert: dict[str, Any]) -> int:
    payload = {
        "event_id": alert["event_id"],
        "cell_id": alert["cell_id"],
        "change_score": alert["change_score"],
        "confidence": alert["confidence"],
        "priority": alert["priority"],
        "reason_codes": alert["reason_codes"],
        "observation_source": alert["observation_source"],
        "before_window": alert["before_window"],
        "after_window": alert["after_window"],
    }
    return estimate_payload_bytes(payload)


def _seed_metrics(spec: dict[str, Any], alerts: list[dict[str, Any]]) -> dict[str, Any]:
    total_payload_bytes = sum(_alert_payload_bytes(alert) for alert in alerts)
    cells_scanned = int(spec.get("cells_scanned") or len(alerts))
    alerts_found = len(alerts)
    discard_ratio = 0.0 if cells_scanned <= 0 else round((cells_scanned - alerts_found) / cells_scanned, 4)
    timestamp = _now()
    flagged_examples = [
        {
            "event_id": str(alert["event_id"]),
            "cell_id": str(alert["cell_id"]),
            "cycle_index": 1,
            "change_score": float(alert["change_score"]),
            "confidence": float(alert["confidence"]),
            "priority": str(alert["priority"]),
            "reason_codes": list(alert.get("reason_codes") or []),
            "payload_bytes": _alert_payload_bytes(alert),
            "timestamp": timestamp,
            "demo_forced_anomaly": False,
            "runtime_truth_mode": "replay",
            "imagery_origin": "cached_api",
            "scoring_basis": "visual_only",
        }
        for alert in alerts[:5]
    ]
    metrics = {
        "region_id": "replay",
        "demo_mode_enabled": False,
        "demo_mode_loop_scan": False,
        "runtime_truth_mode": "replay",
        "imagery_origin": "cached_api",
        "scoring_basis": "visual_only",
        "total_cycles_completed": 1,
        "total_cells_scanned": cells_scanned,
        "total_alerts_emitted": alerts_found,
        "total_payload_bytes": total_payload_bytes,
        "total_bandwidth_saved_mb": round(max(cells_scanned - alerts_found, 0) * 5.0, 4),
        "latest_discard_ratio": discard_ratio,
        "latest_cycle_index": 1,
        "latest_cycle_started_at": timestamp,
        "latest_cycle_completed_at": timestamp,
        "pct_scenes_rejected": 0.0,
        "pct_low_valid_coverage": 0.0,
        "average_inference_latency_ms": 0.0,
        "peak_memory_mb": 0.0,
        "runtime_failures_by_stage": {},
        "runtime_rejections_by_reason": {},
        "flagged_examples": flagged_examples,
    }
    return seed_metrics_summary(metrics)


def load_seeded_replay(replay_id: str) -> dict[str, Any]:
    spec = _load_replay_spec(replay_id)
    alerts = list(spec.get("alerts") or [])
    if not alerts:
        raise ValueError(f"Replay '{replay_id}' has no alerts to load")

    reset_runtime_state()

    mission = start_mission(
        task_text=str(spec.get("task_text") or spec.get("title") or replay_id),
        bbox=spec.get("bbox"),
        start_date=spec.get("start_date"),
        end_date=spec.get("end_date"),
        mission_mode="replay",
        replay_id=replay_id,
        summary=str(spec.get("summary") or spec.get("description") or ""),
    )
    mission_id = int(mission["id"])

    post_message(
        sender="operator",
        recipient="broadcast",
        msg_type="mission",
        payload={
            "mission_id": mission_id,
            "task": mission["task_text"],
            "bbox": mission.get("bbox"),
            "replay_id": replay_id,
            "note": f"[REPLAY #{mission_id}] Loaded cached API replay: {spec.get('title', replay_id)}",
        },
    )
    post_message(
        sender="ground",
        recipient="broadcast",
        msg_type="status",
        payload={
            "replay_id": replay_id,
            "note": "Replay mode loaded. Realtime scan loops are idled so the operator can inspect a completed mission without runtime drift.",
        },
    )

    for alert in alerts:
        alert_payload_bytes = _alert_payload_bytes(alert)
        push_alert(
            event_id=str(alert["event_id"]),
            region_id="replay",
            cell_id=str(alert["cell_id"]),
            change_score=float(alert["change_score"]),
            confidence=float(alert["confidence"]),
            priority=str(alert["priority"]),
            reason_codes=list(alert.get("reason_codes") or []),
            payload_bytes=alert_payload_bytes,
            observation_source=str(alert.get("observation_source") or "replay"),
            runtime_truth_mode="replay",
            imagery_origin="cached_api",
            scoring_basis="visual_only",
            before_window=dict(alert.get("before_window") or {}),
            after_window=dict(alert.get("after_window") or {}),
            downlinked=True,
        )

        seeded_video = str(alert["seeded_video"])
        video_b64 = _seeded_video_data_url(seeded_video)
        thumb = resolve_seeded_thumbnail(_seeded_signature(seeded_video))
        add_gallery_item(
            cell_id=str(alert["cell_id"]),
            lat=float(alert["lat"]),
            lng=float(alert["lng"]),
            severity=str(alert["priority"]),
            change_score=float(alert["change_score"]),
            mission_id=mission_id,
            fetch_thumb=False,
            timelapse_b64=video_b64,
            timelapse_analysis=str(alert.get("timelapse_analysis") or ""),
            context_thumb=thumb,
            context_thumb_source="seeded_cache" if thumb else None,
            timelapse_source="replay",
        )

        upsert_pin(
            pin_type="satellite",
            cell_id=str(alert["cell_id"]),
            lat=float(alert["lat"]),
            lng=float(alert["lng"]),
            label=f"SAT ◆ {str(alert['cell_id'])[:8]}",
            note=str(alert.get("satellite_note") or "Replay satellite flag."),
        )
        upsert_pin(
            pin_type="ground",
            cell_id=str(alert["cell_id"]),
            lat=float(alert["lat"]),
            lng=float(alert["lng"]),
            label=f"GND ● {str(alert['cell_id'])[:8]}",
            note=str(alert.get("ground_note") or "Replay ground confirmation."),
            severity=str(alert["priority"]),
        )

        post_message(
            sender="satellite",
            recipient="ground",
            msg_type="flag",
            cell_id=str(alert["cell_id"]),
            payload={
                "event_id": str(alert["event_id"]),
                "note": str(alert.get("satellite_note") or ""),
                "change_score": float(alert["change_score"]),
                "confidence": float(alert["confidence"]),
                "reason_codes": list(alert.get("reason_codes") or []),
                "observation_source": str(alert.get("observation_source") or "replay"),
                "runtime_truth_mode": "replay",
                "imagery_origin": "cached_api",
                "scoring_basis": "visual_only",
                "before_window": dict(alert.get("before_window") or {}),
                "after_window": dict(alert.get("after_window") or {}),
            },
        )
        post_message(
            sender="ground",
            recipient="satellite",
            msg_type="confirmation",
            cell_id=str(alert["cell_id"]),
            payload={
                "severity": str(alert["priority"]),
                "action": _severity_to_action(alert),
                "analysis_summary": str(alert.get("analysis_summary") or ""),
                "timelapse_analysis": str(alert.get("timelapse_analysis") or ""),
                "findings": list(alert.get("findings") or []),
                "note": str(alert.get("ground_note") or ""),
            },
        )

    update_mission_progress(
        mission_id,
        cells_scanned=int(spec.get("cells_scanned") or len(alerts)),
        flags_found=int(spec.get("flags_found") or len(alerts)),
    )
    mark_messages_read(recipient="ground", msg_type="flag")
    mark_messages_read(recipient="satellite", msg_type="confirmation")
    refreshed_mission = get_mission(mission_id)
    if refreshed_mission is None:
        raise ValueError(f"Replay mission '{replay_id}' failed to persist")

    metrics = _seed_metrics(spec, alerts)

    return {
        "replay_id": replay_id,
        "mission": refreshed_mission,
        "primary_cell_id": str(spec.get("primary_cell_id") or alerts[0]["cell_id"]),
        "alerts_loaded": len(alerts),
        "metrics": metrics,
        "title": str(spec.get("title") or replay_id),
        "summary": str(spec.get("summary") or ""),
    }


def rescan_seeded_replay(replay_id: str) -> dict[str, Any]:
    """Start a live mission from replay metadata so new model/runtime behavior can rescan it."""
    spec = _load_replay_spec(replay_id)
    reset_runtime_state()
    mission = start_mission(
        task_text=str(spec.get("task_text") or spec.get("title") or replay_id),
        bbox=spec.get("bbox"),
        start_date=spec.get("start_date"),
        end_date=spec.get("end_date"),
        mission_mode="live",
        replay_id=None,
        summary=f"Rescan from replay {replay_id}. Uses the current runtime/model stack.",
        use_case_id=str(spec.get("use_case_id") or "") or None,
    )
    post_message(
        sender="operator",
        recipient="broadcast",
        msg_type="mission",
        payload={
            "mission_id": mission["id"],
            "task": mission["task_text"],
            "bbox": mission.get("bbox"),
            "source_replay_id": replay_id,
            "note": f"[RESCAN #{mission['id']}] Started live rescan from replay: {spec.get('title', replay_id)}",
        },
    )
    return {
        "source_replay_id": replay_id,
        "mission": mission,
        "title": str(spec.get("title") or replay_id),
        "summary": str(spec.get("summary") or ""),
    }
