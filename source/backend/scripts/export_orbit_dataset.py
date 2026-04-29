"""Export Orbit alerts and grounded review outcomes into a reproducible local dataset."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from core.agent_bus import get_pin_for_cell, get_recent_messages
from core.config import REGION
from core.gallery import get_gallery_item, resolve_context_thumb
from core.grid import cell_to_latlng
from core.observation_store import list_observations
from core.queue import get_recent_alerts
from core.temporal_use_cases import build_api_prep_plan, build_training_jsonl_row, enrich_temporal_record


_MIME_SUFFIXES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/svg+xml": ".svg",
    "video/webm": ".webm",
    "video/mp4": ".mp4",
}
_DEFAULT_TASK = "deforestation_detection"
_SEEDED_DATA_DIR = Path(__file__).resolve().parent.parent / "assets" / "seeded_data"
_MONITOR_REPORT_MODES = {
    "orbit_lifeline_monitoring_v1",
    "orbit_maritime_monitoring_v1",
}


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned.strip("._") or "sample"


def _sample_id(primary_id: str, cell_id: str) -> str:
    base = _safe_name(primary_id or cell_id or "sample")
    safe_cell = _safe_name(cell_id or "cell")
    return f"{base}__{safe_cell}"


def _decode_data_url(data_url: str) -> tuple[bytes, str]:
    header, _, payload = data_url.partition(",")
    if not header.startswith("data:") or ";base64" not in header or not payload:
        raise ValueError("Only base64 data URLs are supported")
    mime_type = header[5:].split(";", 1)[0]
    suffix = _MIME_SUFFIXES.get(mime_type)
    if not suffix:
        raise ValueError(f"Unsupported data URL mime type: {mime_type}")
    return base64.b64decode(payload), suffix


def _write_asset(sample_dir: Path, stem: str, data_url: str | None) -> str | None:
    if not data_url:
        return None
    raw, suffix = _decode_data_url(data_url)
    asset_path = sample_dir / f"{stem}{suffix}"
    asset_path.write_bytes(raw)
    return asset_path.name


def _split_for_key(key: str, eval_ratio: float) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF
    return "eval" if bucket < eval_ratio else "train"


def _coerce_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _resolve_record_coordinates(record: dict[str, Any]) -> tuple[float | None, float | None]:
    lat = record.get("lat")
    lng = record.get("lng")
    if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
        return float(lat), float(lng)

    cell_id = str(record.get("cell_id") or "").strip()
    if not cell_id:
        return None, None

    pin = get_pin_for_cell(cell_id)
    if pin and isinstance(pin.get("lat"), (int, float)) and isinstance(pin.get("lng"), (int, float)):
        return float(pin["lat"]), float(pin["lng"])

    lat_guess, lng_guess = cell_to_latlng(cell_id)
    if cell_id.startswith("sq_") or (lat_guess, lng_guess) != (0.0, 0.0):
        return lat_guess, lng_guess
    return None, None


def _bbox_center(bbox: Any) -> tuple[float | None, float | None]:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None, None
    try:
        west, south, east, north = [float(item) for item in bbox]
    except (TypeError, ValueError):
        return None, None
    return (south + north) / 2.0, (west + east) / 2.0


def _read_monitor_reports(monitor_reports_dir: Path | None) -> list[tuple[Path, dict[str, Any]]]:
    if monitor_reports_dir is None:
        return []
    root = Path(monitor_reports_dir)
    if not root.exists():
        return []
    paths = [root] if root.is_file() else sorted(root.rglob("*.json"))
    reports: list[tuple[Path, dict[str, Any]]] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid monitor report JSON: {path}") from exc
        if isinstance(payload, dict) and payload.get("mode") in _MONITOR_REPORT_MODES:
            reports.append((path, payload))
    return reports


def _build_alert_record(alert: dict[str, Any], *, eval_ratio: float) -> dict[str, Any]:
    cell_id = str(alert["cell_id"])
    gallery_item = get_gallery_item(cell_id)
    has_gallery = gallery_item is not None
    sample_id = _sample_id(str(alert.get("event_id") or cell_id), cell_id)
    lat, lng = _resolve_record_coordinates({"cell_id": cell_id})
    return {
        "sample_id": sample_id,
        "split": _split_for_key(sample_id, eval_ratio),
        "record_type": "positive",
        "review_state": "ground_confirmed" if has_gallery else "satellite_flagged",
        "label_tier": "silver" if has_gallery else "bronze",
        "target_action": "alert",
        "target_category": "deforestation",
        "target_task": _DEFAULT_TASK,
        "region_id": alert["region_id"],
        "event_id": alert["event_id"],
        "cell_id": cell_id,
        "timestamp": alert.get("timestamp", ""),
        "change_score": _coerce_number(alert.get("change_score")),
        "confidence": _coerce_number(alert.get("confidence")),
        "priority": str(alert.get("priority") or ""),
        "reason_codes": list(alert.get("reason_codes", [])),
        "observation_source": alert.get("observation_source", "unknown"),
        "demo_forced_anomaly": bool(alert.get("demo_forced_anomaly", False)),
        "before_window": alert.get("before_window"),
        "after_window": alert.get("after_window"),
        "boundary_context": alert.get("boundary_context"),
        "confirmation_source": "ground_gallery" if has_gallery else "alert_queue",
        "timelapse_analysis": gallery_item.get("timelapse_analysis") if gallery_item else None,
        "rejection_reason": None,
        "lat": lat,
        "lng": lng,
        "assets": {
            "context_thumb": None,
            "timelapse": None,
        },
    }


def _monitor_use_case(report: dict[str, Any], default_id: str) -> dict[str, Any]:
    use_case = report.get("use_case") if isinstance(report.get("use_case"), dict) else {}
    return {
        "id": str(use_case.get("id") or default_id),
        "target_task": str(use_case.get("target_task") or f"{default_id}_monitoring"),
        "target_category": str(use_case.get("target_category") or default_id),
        "default_target_action": str(use_case.get("default_target_action") or "review"),
        "confidence": _coerce_number(use_case.get("confidence")),
    }


def _build_lifeline_monitor_record(
    report: dict[str, Any],
    source_path: Path,
    *,
    eval_ratio: float,
) -> dict[str, Any]:
    asset = report.get("asset") if isinstance(report.get("asset"), dict) else {}
    frames = report.get("frames") if isinstance(report.get("frames"), dict) else {}
    baseline = frames.get("baseline") if isinstance(frames.get("baseline"), dict) else {}
    current = frames.get("current") if isinstance(frames.get("current"), dict) else {}
    candidate = report.get("candidate") if isinstance(report.get("candidate"), dict) else {}
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    use_case = _monitor_use_case(report, "civilian_lifeline_disruption")
    asset_id = str(asset.get("asset_id") or source_path.stem)
    sample_id = _sample_id(f"monitor_{source_path.stem}", asset_id)
    center = asset.get("center") if isinstance(asset.get("center"), dict) else {}
    return {
        "sample_id": sample_id,
        "split": _split_for_key(sample_id, eval_ratio),
        "record_type": "monitor_report",
        "monitor_type": "lifeline_before_after",
        "review_state": f"monitor_{decision.get('action') or 'review'}",
        "label_tier": "generated_monitor",
        "target_action": str(decision.get("action") or candidate.get("action") or use_case["default_target_action"]),
        "target_category": use_case["target_category"],
        "target_task": use_case["target_task"],
        "region_id": REGION.region_id,
        "event_id": f"monitor_{source_path.stem}",
        "cell_id": asset_id,
        "timestamp": current.get("date") or baseline.get("date") or "",
        "change_score": 0.0,
        "confidence": _coerce_number(decision.get("confidence") or candidate.get("confidence")),
        "priority": str(decision.get("priority") or "review"),
        "reason_codes": [
            str(candidate.get("event_type") or ""),
            str(candidate.get("civilian_impact") or ""),
        ],
        "observation_source": "monitor_report",
        "demo_forced_anomaly": False,
        "before_window": baseline,
        "after_window": current,
        "bbox": asset.get("bbox"),
        "candidate_bbox": candidate.get("bbox"),
        "candidate": candidate,
        "decision": decision,
        "monitor_report_path": str(source_path),
        "monitor_report": report,
        "confirmation_source": "monitor_report",
        "timelapse_analysis": candidate.get("why"),
        "rejection_reason": None,
        "lat": center.get("lat"),
        "lng": center.get("lon"),
        "assets": {
            "context_thumb": None,
            "timelapse": None,
            "baseline_frame": baseline.get("asset_ref"),
            "current_frame": current.get("asset_ref"),
        },
    }


def _build_maritime_monitor_record(
    report: dict[str, Any],
    source_path: Path,
    *,
    eval_ratio: float,
) -> dict[str, Any]:
    target = report.get("target") if isinstance(report.get("target"), dict) else {}
    monitor = report.get("monitor") if isinstance(report.get("monitor"), dict) else {}
    stac = report.get("stac") if isinstance(report.get("stac"), dict) else {}
    stac_items = stac.get("items") if isinstance(stac.get("items"), list) else []
    use_case = _monitor_use_case(report, "maritime_activity")
    lat = target.get("lat")
    lon = target.get("lon")
    timestamp = str(target.get("timestamp") or "")
    sample_id = _sample_id(f"monitor_{source_path.stem}", f"{lat}_{lon}")
    visual_hrefs = [
        str(item.get("visual_href"))
        for item in stac_items
        if isinstance(item, dict) and item.get("visual_href")
    ]
    return {
        "sample_id": sample_id,
        "split": _split_for_key(sample_id, eval_ratio),
        "record_type": "monitor_report",
        "monitor_type": "maritime_stac_investigation",
        "review_state": "monitor_review",
        "label_tier": "generated_monitor",
        "target_action": use_case["default_target_action"],
        "target_category": use_case["target_category"],
        "target_task": use_case["target_task"],
        "region_id": REGION.region_id,
        "event_id": f"monitor_{source_path.stem}",
        "cell_id": f"maritime_{_safe_name(str(lat))}_{_safe_name(str(lon))}",
        "timestamp": timestamp,
        "change_score": 0.0,
        "confidence": use_case["confidence"],
        "priority": "review",
        "reason_codes": list(monitor.get("signals", []))[:12],
        "observation_source": str(stac.get("provider") or "monitor_report"),
        "demo_forced_anomaly": False,
        "before_window": None,
        "after_window": None,
        "bbox": target.get("anchor_bbox"),
        "stac": stac,
        "stac_items": stac_items,
        "monitor_report_path": str(source_path),
        "monitor_report": report,
        "confirmation_source": "monitor_report",
        "timelapse_analysis": monitor.get("objective"),
        "rejection_reason": None,
        "lat": lat,
        "lng": lon,
        "assets": {
            "context_thumb": None,
            "timelapse": None,
            "visual_hrefs": visual_hrefs,
        },
    }


def _build_monitor_report_record(
    report: dict[str, Any],
    source_path: Path,
    *,
    eval_ratio: float,
) -> dict[str, Any] | None:
    mode = str(report.get("mode") or "")
    if mode == "orbit_lifeline_monitoring_v1":
        return _build_lifeline_monitor_record(report, source_path, eval_ratio=eval_ratio)
    if mode == "orbit_maritime_monitoring_v1":
        return _build_maritime_monitor_record(report, source_path, eval_ratio=eval_ratio)
    return None


def _build_reject_record(message: dict[str, Any], *, eval_ratio: float) -> dict[str, Any] | None:
    cell_id = str(message.get("cell_id") or "").strip()
    if not cell_id:
        return None
    payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
    sample_id = _sample_id(f"reject_{message.get('id', 'sample')}", cell_id)
    lat, lng = _resolve_record_coordinates({"cell_id": cell_id})
    return {
        "sample_id": sample_id,
        "split": _split_for_key(sample_id, eval_ratio),
        "record_type": "control",
        "review_state": "ground_rejected",
        "label_tier": "weak_negative",
        "target_action": "prune",
        "target_category": "none",
        "target_task": _DEFAULT_TASK,
        "region_id": REGION.region_id,
        "event_id": f"reject_{message.get('id', 'sample')}",
        "cell_id": cell_id,
        "timestamp": message.get("timestamp", ""),
        "change_score": _coerce_number(payload.get("change_score")),
        "confidence": _coerce_number(payload.get("confidence")),
        "priority": "rejected",
        "reason_codes": list(payload.get("reason_codes", [])),
        "observation_source": payload.get("observation_source", "ground_review"),
        "demo_forced_anomaly": bool(payload.get("demo_forced_anomaly", False)),
        "before_window": payload.get("before_window"),
        "after_window": payload.get("after_window"),
        "boundary_context": None,
        "confirmation_source": "ground_reject",
        "timelapse_analysis": payload.get("timelapse_analysis"),
        "rejection_reason": str(payload.get("reason") or payload.get("note") or "").strip() or None,
        "source_message_id": message.get("id"),
        "lat": lat,
        "lng": lng,
        "assets": {
            "context_thumb": None,
            "timelapse": None,
        },
    }


def _build_api_observation_record(observation: dict[str, Any], *, eval_ratio: float) -> dict[str, Any] | None:
    sig = str(observation.get("chunk_signature") or "").strip()
    if not sig:
        return None

    observation_rows = observation.get("observations") if isinstance(observation.get("observations"), list) else []
    first_row = next((row for row in observation_rows if isinstance(row, dict)), {})
    cell_id = str(first_row.get("cell_id") or observation.get("cell_id") or "").strip()
    sample_id = _sample_id(f"api_{sig}", cell_id or sig)

    lat, lng = _resolve_record_coordinates({"cell_id": cell_id}) if cell_id else (None, None)
    if lat is None or lng is None:
        lat, lng = _bbox_center(observation.get("bbox"))

    training_ready = bool(observation.get("training_ready"))
    latest_text = ""
    for row in reversed(observation_rows):
        if isinstance(row, dict) and row.get("vlm_text"):
            latest_text = str(row["vlm_text"])
            break

    return {
        "sample_id": sample_id,
        "split": _split_for_key(sample_id, eval_ratio),
        "record_type": "api_observation",
        "review_state": "api_training_ready" if training_ready else "api_cached",
        "label_tier": "silver" if training_ready else "unlabeled",
        "target_action": "review",
        "target_category": "temporal_change",
        "target_task": "temporal_change_review",
        "region_id": REGION.region_id,
        "event_id": f"api_{sig}",
        "cell_id": cell_id,
        "chunk_signature": sig,
        "timestamp": observation.get("last_updated") or observation.get("created_at") or "",
        "change_score": 0.0,
        "confidence": 0.0,
        "priority": "review",
        "reason_codes": [],
        "observation_source": observation.get("source", "api_cache"),
        "demo_forced_anomaly": False,
        "before_window": None,
        "after_window": None,
        "bbox": observation.get("bbox"),
        "frame_years": list(observation.get("frame_years", [])),
        "observations": observation_rows,
        "confirmation_source": "observation_store",
        "timelapse_analysis": latest_text or None,
        "rejection_reason": None,
        "lat": lat,
        "lng": lng,
        "assets": {
            "context_thumb": None,
            "timelapse": None,
        },
    }


def _build_seeded_cache_record(meta_path: Path, *, eval_ratio: float) -> dict[str, Any] | None:
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    sig = str(meta.get("chunk_signature") or "").strip()
    if not sig:
        return None
    sample_id = _sample_id(f"seeded_{sig}", sig)
    training_ready = bool(meta.get("training_ready", False))
    frame_dates = list(meta.get("frame_dates", [])) if isinstance(meta.get("frame_dates"), list) else []
    date_windows = list(meta.get("date_windows", [])) if isinstance(meta.get("date_windows"), list) else []
    frame_quality = list(meta.get("frame_quality", [])) if isinstance(meta.get("frame_quality"), list) else []
    rejected_windows = list(meta.get("rejected_windows", [])) if isinstance(meta.get("rejected_windows"), list) else []
    location_name = str(meta.get("location_name") or "")
    use_case_id = str(meta.get("use_case_id") or "").strip()
    target_category = str(meta.get("target_category") or "").strip()
    target_task = str(meta.get("target_task") or "").strip()
    inferred_deforestation = "rond" in location_name.lower()
    return {
        "sample_id": sample_id,
        "split": _split_for_key(sample_id, eval_ratio),
        "record_type": "seeded_cache",
        "review_state": "seeded_training_ready" if training_ready else "seeded_cached",
        "label_tier": "silver" if training_ready else "unlabeled",
        "target_action": "review",
        "target_category": target_category or ("deforestation" if inferred_deforestation else "temporal_change"),
        "target_task": target_task or ("deforestation_detection" if inferred_deforestation else "temporal_change_review"),
        "region_id": REGION.region_id,
        "event_id": f"seeded_{sig}",
        "cell_id": f"seeded_{sig}",
        "chunk_signature": sig,
        "timestamp": frame_dates[-1] if frame_dates else str(meta.get("end_date") or ""),
        "change_score": 0.0,
        "confidence": 0.0,
        "priority": "review",
        "reason_codes": ["seeded_data", "training_ready"] if training_ready else ["seeded_data"],
        "observation_source": str(meta.get("source") or "seeded_cache"),
        "demo_forced_anomaly": False,
        "before_window": {"label": frame_dates[0]} if frame_dates else None,
        "after_window": {"label": frame_dates[-1]} if frame_dates else None,
        "bbox": meta.get("bbox"),
        "frame_dates": frame_dates,
        "date_windows": date_windows,
        "frame_quality": frame_quality,
        "rejected_windows": rejected_windows,
        "frames_count": int(meta.get("frames_count") or 0),
        "seeded_meta_path": str(meta_path),
        "visual_mode": meta.get("visual_mode"),
        "location_name": location_name,
        "region_note": meta.get("region_note"),
        "use_case_id": use_case_id or None,
        "confirmation_source": "seeded_data",
        "timelapse_analysis": str(meta.get("vlm_explanation") or "").strip() or None,
        "rejection_reason": None,
        "lat": meta.get("lat"),
        "lng": meta.get("lon"),
        "assets": {
            "context_thumb": None,
            "timelapse": None,
        },
    }


def _read_seeded_cache_records(*, eval_ratio: float) -> list[dict[str, Any]]:
    if not _SEEDED_DATA_DIR.exists():
        return []
    records: list[dict[str, Any]] = []
    for meta_path in sorted(_SEEDED_DATA_DIR.glob("sh_*_meta.json")):
        record = _build_seeded_cache_record(meta_path, eval_ratio=eval_ratio)
        if record is not None:
            records.append(record)
    return records


def build_export_records(
    limit: int = 200,
    eval_ratio: float = 0.2,
    include_rejects: bool = True,
    include_api_observations: bool = False,
    include_seeded_cache: bool = False,
    monitor_reports_dir: Path | None = None,
) -> list[dict[str, Any]]:
    alerts = get_recent_alerts(limit=limit).get("alerts", [])
    records = [_build_alert_record(alert, eval_ratio=eval_ratio) for alert in alerts]
    alert_cells = {str(alert["cell_id"]) for alert in alerts}

    if include_rejects:
        latest_reject_by_cell: dict[str, dict[str, Any]] = {}
        for message in get_recent_messages(limit=max(limit * 3, limit), sender="ground", msg_type="reject"):
            cell_id = str(message.get("cell_id") or "").strip()
            if not cell_id or cell_id in alert_cells:
                continue
            latest_reject_by_cell[cell_id] = message

        for message in latest_reject_by_cell.values():
            record = _build_reject_record(message, eval_ratio=eval_ratio)
            if record is not None:
                records.append(record)

    if include_api_observations:
        for observation in list_observations(training_ready_only=False):
            record = _build_api_observation_record(observation, eval_ratio=eval_ratio)
            if record is not None:
                records.append(record)

    if include_seeded_cache:
        seeded_records = _read_seeded_cache_records(eval_ratio=eval_ratio)
        seeded_signatures = {
            str(record.get("chunk_signature") or "")
            for record in seeded_records
            if record.get("chunk_signature")
        }
        if seeded_signatures:
            records = [
                record
                for record in records
                if not (
                    record.get("record_type") == "api_observation"
                    and str(record.get("chunk_signature") or "") in seeded_signatures
                )
            ]
        seen_signatures = {
            str(record.get("chunk_signature") or "")
            for record in records
            if record.get("chunk_signature")
        }
        for record in seeded_records:
            if str(record.get("chunk_signature") or "") not in seen_signatures:
                records.append(record)

    for source_path, report in _read_monitor_reports(monitor_reports_dir):
        record = _build_monitor_report_record(report, source_path, eval_ratio=eval_ratio)
        if record is not None:
            records.append(record)

    records.sort(key=lambda item: (str(item.get("timestamp") or ""), str(item.get("sample_id") or "")), reverse=True)
    return [enrich_temporal_record(record) for record in records[: max(1, int(limit))]]


def _resolve_context_thumb_data(record: dict[str, Any], gallery_item: dict[str, Any] | None) -> str | None:
    if gallery_item and gallery_item.get("context_thumb"):
        return str(gallery_item["context_thumb"])
    lat, lng = _resolve_record_coordinates(record)
    if lat is None or lng is None:
        return None
    return resolve_context_thumb(lat, lng)


def _resolve_cached_timelapse_data(chunk_signature: str | None) -> str | None:
    sig = str(chunk_signature or "").strip()
    if not sig:
        return None
    for prefix in ("sh", "nasa"):
        path = _SEEDED_DATA_DIR / f"{prefix}_{sig}.webm"
        if not path.exists():
            continue
        data_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:video/webm;base64,{data_b64}"
    return None


def write_dataset_export(
    output_dir: Path,
    *,
    limit: int = 200,
    eval_ratio: float = 0.2,
    include_rejects: bool = True,
    include_api_observations: bool = False,
    include_seeded_cache: bool = False,
    monitor_reports_dir: Path | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    samples_dir = output_dir / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)

    records = build_export_records(
        limit=limit,
        eval_ratio=eval_ratio,
        include_rejects=include_rejects,
        include_api_observations=include_api_observations,
        include_seeded_cache=include_seeded_cache,
        monitor_reports_dir=monitor_reports_dir,
    )
    train_count = 0
    eval_count = 0
    with_gallery = 0
    with_context_thumb = 0
    with_timelapse = 0
    control_count = 0
    positive_count = 0
    api_observation_count = 0
    seeded_cache_count = 0
    monitor_report_count = 0
    use_case_counts: dict[str, int] = {}

    for record in records:
        sample_dir = samples_dir / str(record["sample_id"])
        sample_dir.mkdir(parents=True, exist_ok=True)

        gallery_item = get_gallery_item(str(record["cell_id"])) if record["confirmation_source"] == "ground_gallery" else None
        if gallery_item:
            with_gallery += 1

        context_thumb_data = _resolve_context_thumb_data(record, gallery_item)
        record["assets"]["context_thumb"] = _write_asset(sample_dir, "context_thumb", context_thumb_data)
        if record["assets"]["context_thumb"]:
            with_context_thumb += 1

        if gallery_item:
            record["assets"]["timelapse"] = _write_asset(sample_dir, "timelapse", gallery_item.get("timelapse_b64"))
            if gallery_item.get("timelapse_analysis"):
                (sample_dir / "timelapse_analysis.txt").write_text(
                    str(gallery_item["timelapse_analysis"]),
                    encoding="utf-8",
                )
        elif record["record_type"] in {"api_observation", "seeded_cache"}:
            record["assets"]["timelapse"] = _write_asset(
                sample_dir,
                "timelapse",
                _resolve_cached_timelapse_data(record.get("chunk_signature")),
            )

        if record["assets"].get("timelapse"):
            with_timelapse += 1

        if isinstance(record.get("temporal_use_case"), dict):
            record["api_prep"] = build_api_prep_plan(record, record["temporal_use_case"])

        (sample_dir / "sample.json").write_text(
            json.dumps(record, indent=2),
            encoding="utf-8",
        )

        if record["record_type"] == "control":
            control_count += 1
        elif record["record_type"] == "api_observation":
            api_observation_count += 1
        elif record["record_type"] == "seeded_cache":
            seeded_cache_count += 1
        elif record["record_type"] == "monitor_report":
            monitor_report_count += 1
        else:
            positive_count += 1

        use_case = record.get("temporal_use_case") if isinstance(record.get("temporal_use_case"), dict) else {}
        use_case_id = str(use_case.get("id") or "unknown")
        use_case_counts[use_case_id] = use_case_counts.get(use_case_id, 0) + 1

        if record["split"] == "eval":
            eval_count += 1
        else:
            train_count += 1

    jsonl_path = output_dir / "samples.jsonl"
    train_path = output_dir / "train.jsonl"
    eval_path = output_dir / "eval.jsonl"
    training_path = output_dir / "training.jsonl"
    train_training_path = output_dir / "train_training.jsonl"
    eval_training_path = output_dir / "eval_training.jsonl"
    jsonl_lines = [json.dumps(record, sort_keys=True) for record in records]
    train_lines = [json.dumps(record, sort_keys=True) for record in records if record["split"] == "train"]
    eval_lines = [json.dumps(record, sort_keys=True) for record in records if record["split"] == "eval"]
    training_rows = [build_training_jsonl_row(record) for record in records]
    training_lines = [json.dumps(row, sort_keys=True) for row in training_rows]
    train_training_lines = [
        json.dumps(row, sort_keys=True) for row in training_rows if row["split"] == "train"
    ]
    eval_training_lines = [
        json.dumps(row, sort_keys=True) for row in training_rows if row["split"] == "eval"
    ]
    jsonl_path.write_text("\n".join(jsonl_lines) + ("\n" if jsonl_lines else ""), encoding="utf-8")
    train_path.write_text("\n".join(train_lines) + ("\n" if train_lines else ""), encoding="utf-8")
    eval_path.write_text("\n".join(eval_lines) + ("\n" if eval_lines else ""), encoding="utf-8")
    training_path.write_text(
        "\n".join(training_lines) + ("\n" if training_lines else ""),
        encoding="utf-8",
    )
    train_training_path.write_text(
        "\n".join(train_training_lines) + ("\n" if train_training_lines else ""),
        encoding="utf-8",
    )
    eval_training_path.write_text(
        "\n".join(eval_training_lines) + ("\n" if eval_training_lines else ""),
        encoding="utf-8",
    )

    manifest = {
        "format": "orbit_dataset_export_v2",
        "records": len(records),
        "positive_records": positive_count,
        "control_records": control_count,
        "api_observation_records": api_observation_count,
        "seeded_cache_records": seeded_cache_count,
        "monitor_report_records": monitor_report_count,
        "train_records": train_count,
        "eval_records": eval_count,
        "records_with_gallery": with_gallery,
        "records_with_context_thumb": with_context_thumb,
        "records_with_timelapse": with_timelapse,
        "eval_ratio": eval_ratio,
        "use_case_counts": dict(sorted(use_case_counts.items())),
        "paths": {
            "samples": "samples/",
            "samples_jsonl": jsonl_path.name,
            "train_jsonl": train_path.name,
            "eval_jsonl": eval_path.name,
            "training_jsonl": training_path.name,
            "train_training_jsonl": train_training_path.name,
            "eval_training_jsonl": eval_training_path.name,
        },
        "notes": [
            "Records are sourced from Orbit recent alerts plus recent ground-agent reject outcomes.",
            "Every export row attempts to materialize a local context thumbnail from gallery evidence or persisted map-pin coordinates.",
            "Each row is auto-classified against the temporal use-case catalog and mirrored into chat-style training JSONL.",
            "API observation rows can be included from the local observation store for near-autonomous data-prep refinement.",
            "Replay-cache rows can be included directly from the legacy assets/seeded_data folder for replay and timelapse training packs.",
            "Persisted maritime and lifeline monitor-report JSON files can be imported as generated monitor rows.",
            "Ground rejections are weak negatives with explicit provenance rather than operator-reviewed gold controls.",
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Orbit alerts and grounded review outcomes into a local dataset bundle.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory to write the dataset bundle.")
    parser.add_argument("--limit", type=int, default=200, help="Maximum recent records to export.")
    parser.add_argument("--eval-ratio", type=float, default=0.2, help="Deterministic eval split ratio from 0 to 1.")
    parser.add_argument(
        "--no-rejects",
        action="store_true",
        help="Only export alert-derived positives and skip ground-agent reject rows.",
    )
    parser.add_argument(
        "--no-api-observations",
        action="store_true",
        help="Skip cached API observation-store rows. CLI exports include them by default.",
    )
    parser.add_argument(
        "--include-seeded-cache",
        action="store_true",
        help="Include WebM timelapses and metadata directly from assets/seeded_data.",
    )
    parser.add_argument(
        "--monitor-reports-dir",
        type=Path,
        default=None,
        help="Optional JSON file or directory of persisted maritime/lifeline monitor reports to include.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    eval_ratio = max(0.0, min(float(args.eval_ratio), 1.0))
    manifest = write_dataset_export(
        args.output_dir,
        limit=max(1, int(args.limit)),
        eval_ratio=eval_ratio,
        include_rejects=not args.no_rejects,
        include_api_observations=not args.no_api_observations,
        include_seeded_cache=args.include_seeded_cache,
        monitor_reports_dir=args.monitor_reports_dir,
    )
    print(
        "[Orbit] Exported {records} samples to {path} "
        "({positive_records} positives, {control_records} controls, {api_observation_records} api observations, {seeded_cache_records} replay cache, {monitor_report_records} monitor reports, {train_records} train / {eval_records} eval, {records_with_context_thumb} with context)".format(
            path=args.output_dir,
            **manifest,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
