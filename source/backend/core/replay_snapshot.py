from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.agent_bus import get_recent_messages, list_pins, post_message, upsert_pin
from core.gallery import add_gallery_item, get_gallery_item, list_gallery
from core.metrics import read_metrics_summary, seed_metrics_summary
from core.mission import get_active_mission, list_missions, start_mission, update_mission_progress
from core.queue import estimate_payload_bytes, get_recent_alerts, push_alert
from core.runtime_state import reset_runtime_state


SNAPSHOT_FORMAT = "orbit_runtime_snapshot_v1"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _gallery_with_assets(limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in list_gallery(limit=limit):
        full = get_gallery_item(str(item.get("cell_id") or ""))
        rows.append(full or item)
    return rows


def export_replay_snapshot(*, limit: int = 200) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 500))
    return {
        "format": SNAPSHOT_FORMAT,
        "schema_version": 1,
        "exported_at": _now(),
        "active_mission": get_active_mission(),
        "missions": list_missions(limit=safe_limit),
        "alerts": get_recent_alerts(limit=min(safe_limit, 200)).get("alerts", []),
        "gallery": _gallery_with_assets(safe_limit),
        "pins": list_pins(),
        "messages": get_recent_messages(limit=safe_limit),
        "metrics": read_metrics_summary(),
    }


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_bool(value: Any) -> bool:
    return bool(value)


def _restore_active_mission(snapshot: dict[str, Any]) -> int | None:
    mission = snapshot.get("active_mission") if isinstance(snapshot.get("active_mission"), dict) else None
    if mission is None:
        return None
    restored = start_mission(
        task_text=str(mission.get("task_text") or "Imported replay snapshot"),
        bbox=mission.get("bbox") if isinstance(mission.get("bbox"), list) else None,
        start_date=mission.get("start_date"),
        end_date=mission.get("end_date"),
        mission_mode=str(mission.get("mission_mode") or "replay"),
        replay_id=mission.get("replay_id"),
        summary=mission.get("summary"),
        use_case_id=mission.get("use_case_id"),
    )
    update_mission_progress(
        int(restored["id"]),
        int(mission.get("cells_scanned") or 0),
        int(mission.get("flags_found") or 0),
    )
    return int(restored["id"])


def import_replay_snapshot(snapshot: dict[str, Any], *, reset: bool = True) -> dict[str, Any]:
    if not isinstance(snapshot, dict) or snapshot.get("format") != SNAPSHOT_FORMAT:
        raise ValueError(f"snapshot format must be {SNAPSHOT_FORMAT}")
    if reset:
        reset_runtime_state()

    metrics = snapshot.get("metrics")
    if isinstance(metrics, dict):
        seed_metrics_summary(metrics)

    mission_id = _restore_active_mission(snapshot)

    alert_count = 0
    for alert in snapshot.get("alerts") if isinstance(snapshot.get("alerts"), list) else []:
        if not isinstance(alert, dict):
            continue
        payload = {
            "event_id": alert.get("event_id"),
            "cell_id": alert.get("cell_id"),
            "change_score": alert.get("change_score"),
            "confidence": alert.get("confidence"),
            "priority": alert.get("priority"),
            "reason_codes": alert.get("reason_codes"),
            "observation_source": alert.get("observation_source"),
        }
        push_alert(
            event_id=str(alert.get("event_id") or f"snapshot_alert_{alert_count + 1}"),
            region_id=str(alert.get("region_id") or "snapshot"),
            cell_id=str(alert.get("cell_id") or f"snapshot_cell_{alert_count + 1}"),
            change_score=_coerce_float(alert.get("change_score")),
            confidence=_coerce_float(alert.get("confidence")),
            priority=str(alert.get("priority") or "review"),
            reason_codes=[str(item) for item in alert.get("reason_codes") or []],
            payload_bytes=int(alert.get("payload_bytes") or estimate_payload_bytes(payload)),
            demo_forced_anomaly=_coerce_bool(alert.get("demo_forced_anomaly")),
            observation_source=str(alert.get("observation_source") or "snapshot_import"),
            runtime_truth_mode=alert.get("runtime_truth_mode"),
            imagery_origin=alert.get("imagery_origin"),
            scoring_basis=alert.get("scoring_basis"),
            before_window=alert.get("before_window") if isinstance(alert.get("before_window"), dict) else None,
            after_window=alert.get("after_window") if isinstance(alert.get("after_window"), dict) else None,
            boundary_context=alert.get("boundary_context") if isinstance(alert.get("boundary_context"), list) else None,
            downlinked=_coerce_bool(alert.get("downlinked")),
        )
        alert_count += 1

    gallery_count = 0
    for item in snapshot.get("gallery") if isinstance(snapshot.get("gallery"), list) else []:
        if not isinstance(item, dict):
            continue
        cell_id = str(item.get("cell_id") or "")
        if not cell_id:
            continue
        add_gallery_item(
            cell_id=cell_id,
            lat=_coerce_float(item.get("lat")),
            lng=_coerce_float(item.get("lng")),
            severity=str(item.get("severity") or "review"),
            change_score=_coerce_float(item.get("change_score")),
            mission_id=mission_id or item.get("mission_id"),
            fetch_thumb=False,
            timelapse_b64=item.get("timelapse_b64"),
            timelapse_analysis=item.get("timelapse_analysis"),
            context_thumb=item.get("context_thumb"),
            context_thumb_source=item.get("context_thumb_source"),
            timelapse_source=item.get("timelapse_source"),
        )
        gallery_count += 1

    pin_count = 0
    for pin in snapshot.get("pins") if isinstance(snapshot.get("pins"), list) else []:
        if not isinstance(pin, dict):
            continue
        upsert_pin(
            pin_type=str(pin.get("pin_type") or "operator"),
            cell_id=pin.get("cell_id"),
            lat=_coerce_float(pin.get("lat")),
            lng=_coerce_float(pin.get("lng")),
            label=str(pin.get("label") or "Imported snapshot pin"),
            note=str(pin.get("note") or ""),
            severity=pin.get("severity"),
        )
        pin_count += 1

    message_count = 0
    for message in snapshot.get("messages") if isinstance(snapshot.get("messages"), list) else []:
        if not isinstance(message, dict):
            continue
        payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
        post_message(
            sender=str(message.get("sender") or "operator"),
            recipient=str(message.get("recipient") or "broadcast"),
            msg_type=str(message.get("msg_type") or "status"),
            cell_id=message.get("cell_id"),
            payload={**payload, "snapshot_imported": True},
        )
        message_count += 1

    return {
        "status": "imported",
        "format": SNAPSHOT_FORMAT,
        "reset": bool(reset),
        "mission_id": mission_id,
        "alerts_imported": alert_count,
        "gallery_imported": gallery_count,
        "pins_imported": pin_count,
        "messages_imported": message_count,
    }
