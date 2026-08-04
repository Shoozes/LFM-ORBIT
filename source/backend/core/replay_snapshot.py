from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

from core.agent_bus import get_recent_messages, list_pins, post_message, upsert_pin
from core.gallery import add_gallery_item, get_gallery_item, list_gallery
from core.metrics import read_metrics_summary, seed_metrics_summary
from core.mission import (
    MISSION_CONFIRMATION_POLICIES,
    get_active_mission,
    list_missions,
    start_mission,
    update_mission_progress,
)
from core.queue import estimate_payload_bytes, get_recent_alerts, push_alert
from core.request_limits import validate_json_shape
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
        converted = float(value)
        return converted if math.isfinite(converted) else default
    except (TypeError, ValueError):
        return default


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "enabled"}:
            return True
        if normalized in {"0", "false", "no", "off", "disabled", ""}:
            return False
    # Unknown snapshot values must not silently opt into a flagged state.
    return False


def _restore_active_mission(snapshot: dict[str, Any]) -> int | None:
    mission = snapshot.get("active_mission") if isinstance(snapshot.get("active_mission"), dict) else None
    if mission is None:
        return None
    raw_confirmation_policy = mission.get("confirmation_policy")
    confirmation_policy = str(raw_confirmation_policy).strip().lower() if raw_confirmation_policy else None
    if confirmation_policy and confirmation_policy not in MISSION_CONFIRMATION_POLICIES:
        raise ValueError("snapshot confirmation_policy is invalid")
    restored = start_mission(
        task_text=str(mission.get("task_text") or "Imported replay snapshot"),
        bbox=mission.get("bbox") if isinstance(mission.get("bbox"), list) else None,
        start_date=mission.get("start_date"),
        end_date=mission.get("end_date"),
        mission_mode=str(mission.get("mission_mode") or "replay"),
        confirmation_policy=confirmation_policy,
        replay_id=mission.get("replay_id"),
        summary=mission.get("summary"),
        use_case_id=mission.get("use_case_id"),
        target_pack_id=mission.get("target_pack_id") if mission.get("target_pack_id") else None,
        object_targets=mission.get("object_targets") if isinstance(mission.get("object_targets"), list) else None,
    )
    update_mission_progress(
        int(restored["id"]),
        int(mission.get("cells_scanned") or 0),
        int(mission.get("flags_found") or 0),
    )
    return int(restored["id"])


def _validate_finite_values(value: Any, *, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"snapshot contains a non-finite number at {path}")
    if isinstance(value, dict):
        for key, child in value.items():
            _validate_finite_values(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_finite_values(child, path=f"{path}[{index}]")


def _validate_snapshot(snapshot: dict[str, Any]) -> None:
    if not isinstance(snapshot, dict) or snapshot.get("format") != SNAPSHOT_FORMAT:
        raise ValueError(f"snapshot format must be {SNAPSHOT_FORMAT}")
    if snapshot.get("schema_version") not in (None, 1):
        raise ValueError("unsupported snapshot schema_version")

    try:
        validate_json_shape(snapshot)
    except ValueError as exc:
        raise ValueError(f"invalid snapshot shape: {exc}") from exc
    _validate_finite_values(snapshot)

    active_mission = snapshot.get("active_mission")
    if active_mission is not None and not isinstance(active_mission, dict):
        raise ValueError("active_mission must be an object or null")
    if isinstance(active_mission, dict):
        bbox = active_mission.get("bbox")
        if bbox is not None and (not isinstance(bbox, list) or len(bbox) != 4):
            raise ValueError("active_mission.bbox must contain four coordinates")

    section_limits = {"missions": 500, "alerts": 200, "gallery": 500, "pins": 500, "messages": 500}
    for section, limit in section_limits.items():
        rows = snapshot.get(section, [])
        if rows is None:
            continue
        if not isinstance(rows, list):
            raise ValueError(f"snapshot.{section} must be an array")
        if len(rows) > limit:
            raise ValueError(f"snapshot.{section} exceeds the {limit}-row limit")
        if any(not isinstance(row, dict) for row in rows):
            raise ValueError(f"snapshot.{section} contains a non-object row")

    for index, alert in enumerate(snapshot.get("alerts") or []):
        payload_bytes = alert.get("payload_bytes")
        if payload_bytes is not None:
            try:
                numeric_bytes = int(payload_bytes)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"snapshot.alerts[{index}].payload_bytes must be an integer") from exc
            if numeric_bytes < 0 or numeric_bytes > 64_000_000:
                raise ValueError(f"snapshot.alerts[{index}].payload_bytes is outside the supported range")
        reasons = alert.get("reason_codes")
        if reasons is not None and (not isinstance(reasons, list) or any(not isinstance(item, str) for item in reasons)):
            raise ValueError(f"snapshot.alerts[{index}].reason_codes must be an array of strings")

    for index, item in enumerate(snapshot.get("gallery") or []):
        if not str(item.get("cell_id") or "").strip():
            raise ValueError(f"snapshot.gallery[{index}].cell_id is required")
        for field in ("lat", "lng", "change_score"):
            if field in item and _coerce_float(item.get(field), default=math.nan) != _coerce_float(item.get(field), default=math.nan):
                raise ValueError(f"snapshot.gallery[{index}].{field} must be numeric")


def _apply_replay_snapshot(snapshot: dict[str, Any], *, reset: bool) -> dict[str, Any]:

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
            detection_summary=alert.get("detection_summary") if isinstance(alert.get("detection_summary"), dict) else None,
            object_deltas=alert.get("object_deltas") if isinstance(alert.get("object_deltas"), list) else None,
            visual_model_review=alert.get("visual_model_review") if isinstance(alert.get("visual_model_review"), dict) else None,
            downlinked=_coerce_bool(alert.get("downlinked")),
            mission_id=mission_id or alert.get("mission_id"),
            use_case_id=str(alert.get("use_case_id") or "") or None,
            target_pack_id=str(alert.get("target_pack_id") or "") or None,
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


def import_replay_snapshot(snapshot: dict[str, Any], *, reset: bool = True) -> dict[str, Any]:
    """Validate the complete payload before reset, then restore it as one import unit."""
    _validate_snapshot(snapshot)
    previous = export_replay_snapshot(limit=500) if reset else None
    if reset:
        reset_runtime_state()
    try:
        return _apply_replay_snapshot(snapshot, reset=reset)
    except Exception as exc:
        if previous is not None:
            try:
                reset_runtime_state(archive_missions=False)
                _apply_replay_snapshot(previous, reset=True)
            except Exception as rollback_exc:
                raise RuntimeError(f"snapshot import failed and rollback failed: {rollback_exc}") from exc
        raise RuntimeError(f"snapshot import failed; runtime was not committed: {exc}") from exc
