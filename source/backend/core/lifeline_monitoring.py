"""Civilian lifeline before/after monitoring helpers.

The module is intentionally deterministic and dependency-light. It normalizes
model candidates, compares baseline/current frame metadata, and returns a
compact downlink decision suitable for API use, replay fixtures, and training
export rows.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from core.temporal_use_cases import classify_temporal_use_case


LIFELINE_REPORT_VERSION = "orbit_lifeline_monitoring_v1"

EVENT_TYPES: tuple[str, ...] = (
    "probable_large_scale_disruption",
    "probable_surface_change",
    "probable_access_obstruction",
    "no_event",
)
SEVERITIES: tuple[str, ...] = ("low", "medium", "high")
ACTIONS: tuple[str, ...] = ("discard", "defer", "downlink_now")
CIVILIAN_IMPACTS: tuple[str, ...] = (
    "shipping_or_aid_disruption",
    "logistics_delay",
    "trade_disruption",
    "civilian_facility_disruption",
    "public_mobility_disruption",
    "water_service_disruption",
    "no_material_impact",
)
REQUIRED_CANDIDATE_FIELDS: tuple[str, ...] = (
    "event_type",
    "severity",
    "confidence",
    "bbox",
    "civilian_impact",
    "why",
    "action",
)

_SEED_ASSETS: tuple[dict[str, Any], ...] = (
    {
        "asset_id": "orbit_port_aid_hub",
        "display_name": "Port logistics and aid hub",
        "asset_type": "container_port",
        "category": "shipping_or_aid",
        "region": "global",
        "center": {"lat": 29.92, "lon": 32.54},
        "bbox": [32.25, 29.72, 32.75, 30.12],
        "why_monitor": "Port access and nearby channel disruption can slow aid, logistics, and trade flows.",
    },
    {
        "asset_id": "orbit_bridge_corridor",
        "display_name": "Bridge and road-access corridor",
        "asset_type": "bridge",
        "category": "public_mobility",
        "region": "global",
        "center": {"lat": 34.05, "lon": -118.24},
        "bbox": [-118.32, 33.99, -118.16, 34.11],
        "why_monitor": "Bridge or approach-road obstruction can disrupt evacuation, commuting, and response routes.",
    },
    {
        "asset_id": "orbit_water_service_node",
        "display_name": "Water service facility",
        "asset_type": "water_treatment",
        "category": "water_service",
        "region": "global",
        "center": {"lat": 39.74, "lon": -104.99},
        "bbox": [-105.08, 39.69, -104.90, 39.79],
        "why_monitor": "Facility damage or access loss can affect civilian water-service continuity.",
    },
)


def list_lifeline_assets(category: str | None = None, region: str | None = None) -> list[dict[str, Any]]:
    """Return seeded civilian lifeline assets, optionally filtered."""
    category_key = str(category or "").strip().lower()
    region_key = str(region or "").strip().lower()
    assets = []
    for asset in _SEED_ASSETS:
        if category_key and category_key not in str(asset.get("category", "")).lower():
            continue
        if region_key and region_key not in str(asset.get("region", "")).lower():
            continue
        assets.append(deepcopy(asset))
    return assets


def get_lifeline_asset(asset_id: str | None) -> dict[str, Any] | None:
    """Return a seeded asset by id."""
    target = str(asset_id or "").strip()
    if not target:
        return None
    for asset in _SEED_ASSETS:
        if asset["asset_id"] == target:
            return deepcopy(asset)
    return None


def _coerce_unit_float(value: Any, *, field_name: str, errors: list[str]) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        errors.append(f"{field_name} must be numeric")
        return 0.0
    if numeric < 0.0 or numeric > 1.0:
        errors.append(f"{field_name} must be between 0 and 1")
    return min(1.0, max(0.0, numeric))


def normalize_lifeline_bbox(value: Any) -> tuple[list[float], bool, list[str]]:
    """Normalize a model bbox in unit image coordinates."""
    errors: list[str] = []
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return [0.0, 0.0, 1.0, 1.0], False, ["bbox must contain four numeric values"]

    bbox = [
        _coerce_unit_float(value[0], field_name="bbox[0]", errors=errors),
        _coerce_unit_float(value[1], field_name="bbox[1]", errors=errors),
        _coerce_unit_float(value[2], field_name="bbox[2]", errors=errors),
        _coerce_unit_float(value[3], field_name="bbox[3]", errors=errors),
    ]
    if bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
        errors.append("bbox must be ordered as [x1, y1, x2, y2]")
    bbox_valid = not errors
    if not bbox_valid:
        return [0.0, 0.0, 1.0, 1.0], False, errors
    return [round(value, 4) for value in bbox], True, []


def _normalize_enum(value: Any, allowed: tuple[str, ...], default: str, field_name: str, errors: list[str]) -> str:
    text = str(value or "").strip().lower()
    if text in allowed:
        return text
    errors.append(f"{field_name} must be one of {', '.join(allowed)}")
    return default


def _normalize_confidence(value: Any, errors: list[str]) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        errors.append("confidence must be numeric")
        return 0.0
    if confidence < 0.0 or confidence > 1.0:
        errors.append("confidence must be between 0 and 1")
    return round(min(1.0, max(0.0, confidence)), 4)


def normalize_lifeline_candidate(candidate: dict[str, Any] | None) -> dict[str, Any]:
    """Return a strict, safe candidate with validation metadata."""
    raw = candidate if isinstance(candidate, dict) else {}
    errors: list[str] = []
    missing = [field for field in REQUIRED_CANDIDATE_FIELDS if field not in raw]
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")

    event_type = _normalize_enum(raw.get("event_type"), EVENT_TYPES, "no_event", "event_type", errors)
    severity = _normalize_enum(raw.get("severity"), SEVERITIES, "low", "severity", errors)
    civilian_impact = _normalize_enum(
        raw.get("civilian_impact"),
        CIVILIAN_IMPACTS,
        "no_material_impact",
        "civilian_impact",
        errors,
    )
    action = _normalize_enum(raw.get("action"), ACTIONS, "discard", "action", errors)
    confidence = _normalize_confidence(raw.get("confidence"), errors)
    bbox, bbox_valid, bbox_errors = normalize_lifeline_bbox(raw.get("bbox"))
    errors.extend(bbox_errors)

    why = str(raw.get("why") or "").strip()
    if not why:
        errors.append("why must be a non-empty explanation")

    if event_type == "no_event":
        civilian_impact = "no_material_impact"
        action = "discard"
        severity = "low"

    schema_valid = not errors
    return {
        "event_type": event_type,
        "severity": severity,
        "confidence": confidence,
        "bbox": bbox,
        "civilian_impact": civilian_impact,
        "why": why or "No reliable material change explanation was provided.",
        "action": action,
        "schema_valid": schema_valid,
        "bbox_valid": bbox_valid,
        "validation_errors": errors,
    }


def normalize_lifeline_frame(frame: dict[str, Any] | None, *, role: str) -> dict[str, Any]:
    """Normalize a baseline/current frame descriptor without requiring image bytes."""
    raw = frame if isinstance(frame, dict) else {}
    label = str(raw.get("label") or role).strip()
    date_value = str(raw.get("date") or raw.get("timestamp") or "").strip()
    return {
        "role": role,
        "label": label,
        "date": date_value,
        "source": str(raw.get("source") or "unresolved").strip(),
        "asset_ref": str(raw.get("asset_ref") or raw.get("href") or raw.get("path") or "").strip(),
        "quality": raw.get("quality"),
        "metadata": raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {},
    }


def _frame_pair_state(baseline_frame: dict[str, Any], current_frame: dict[str, Any]) -> dict[str, Any]:
    baseline_asset = str(baseline_frame.get("asset_ref") or "")
    current_asset = str(current_frame.get("asset_ref") or "")
    has_dates = bool(baseline_frame["date"]) and bool(current_frame["date"])
    has_distinct_dates = has_dates and baseline_frame["date"] != current_frame["date"]
    has_assets = bool(baseline_asset) and bool(current_asset)
    has_distinct_assets = has_assets and baseline_asset != current_asset
    frame_warnings: list[str] = []
    if not has_distinct_dates and not has_distinct_assets:
        frame_warnings.append("baseline/current frames are not proven distinct by date or asset reference")
    return {
        "baseline_label": baseline_frame["label"],
        "current_label": current_frame["label"],
        "baseline_date": baseline_frame["date"],
        "current_date": current_frame["date"],
        "distinct_contextual_frames": has_distinct_dates or has_distinct_assets,
        "asset_pair_available": has_assets,
        "warnings": frame_warnings,
    }


def score_lifeline_candidate(candidate: dict[str, Any], asset: dict[str, Any] | None = None) -> dict[str, Any]:
    """Score a normalized candidate into discard/defer/downlink_now."""
    normalized = normalize_lifeline_candidate(candidate)
    material_event = (
        normalized["event_type"] != "no_event"
        and normalized["civilian_impact"] != "no_material_impact"
    )
    reasons: list[str] = []

    if not normalized["schema_valid"]:
        reasons.append("candidate schema failed validation")
        action = "discard"
        priority = "none"
    elif not material_event:
        reasons.append("no material civilian lifeline impact")
        action = "discard"
        priority = "none"
    elif normalized["severity"] == "high" and normalized["confidence"] >= 0.75:
        reasons.append("high-severity material disruption with strong confidence")
        action = "downlink_now"
        priority = "critical"
    elif normalized["confidence"] >= 0.60:
        reasons.append("material change needs analyst review before escalation")
        action = "defer"
        priority = "watch"
    elif normalized["confidence"] >= 0.45:
        reasons.append("weak material signal retained as review candidate")
        action = "defer"
        priority = "low"
    else:
        reasons.append("confidence below review threshold")
        action = "discard"
        priority = "none"

    if asset:
        reasons.append(f"asset category: {asset.get('category', 'unknown')}")

    return {
        "action": action,
        "priority": priority,
        "accepted": action != "discard",
        "downlink_now": action == "downlink_now",
        "confidence": normalized["confidence"],
        "reasons": reasons,
        "candidate": normalized,
    }


def build_lifeline_monitor_report(
    *,
    asset_id: str | None = None,
    asset: dict[str, Any] | None = None,
    candidate: dict[str, Any] | None = None,
    baseline_frame: dict[str, Any] | None = None,
    current_frame: dict[str, Any] | None = None,
    task_text: str = "",
) -> dict[str, Any]:
    """Build a before/after civilian lifeline monitor report."""
    selected_asset = deepcopy(asset) if isinstance(asset, dict) else get_lifeline_asset(asset_id)
    if selected_asset is None:
        if asset_id:
            raise ValueError(f"unknown lifeline asset_id: {asset_id}")
        selected_asset = deepcopy(_SEED_ASSETS[0])

    baseline = normalize_lifeline_frame(baseline_frame, role="baseline")
    current = normalize_lifeline_frame(current_frame, role="current")
    frame_state = _frame_pair_state(baseline, current)
    normalized_candidate = normalize_lifeline_candidate(candidate)
    decision = score_lifeline_candidate(normalized_candidate, selected_asset)
    if decision["action"] != "discard" and not frame_state["distinct_contextual_frames"]:
        decision = {
            **decision,
            "action": "defer",
            "priority": "needs_context",
            "accepted": True,
            "downlink_now": False,
            "reasons": [
                *decision["reasons"],
                "downlink held until baseline/current frames are proven distinct",
            ],
        }
    mission_text = task_text.strip() or (
        "Compare before and after satellite frames for civilian lifeline disruption."
    )
    use_case = classify_temporal_use_case(
        {
            "task_text": mission_text,
            "reason_codes": [
                normalized_candidate["event_type"],
                normalized_candidate["civilian_impact"],
            ],
            "target_category": "civilian_lifeline",
        },
        "civilian_lifeline_disruption",
    )

    return {
        "mode": LIFELINE_REPORT_VERSION,
        "asset": selected_asset,
        "frames": {
            "baseline": baseline,
            "current": current,
            "pair_state": frame_state,
        },
        "candidate": normalized_candidate,
        "decision": {
            key: value
            for key, value in decision.items()
            if key != "candidate"
        },
        "use_case": use_case,
        "before_after_review": {
            "required_inputs": [
                "baseline_frame",
                "current_frame",
                "candidate.event_type",
                "candidate.bbox",
                "candidate.civilian_impact",
            ],
            "quality_gates": [
                "require distinct baseline/current context before treating color-only changes as real",
                "reject invalid unit bboxes before downlink escalation",
                "force no_event candidates to discard with no_material_impact",
                "preserve both frame descriptors for reproducible training rows",
            ],
            "analysis_questions": [
                "What changed between baseline and current frames?",
                "Does the change affect civilian mobility, logistics, trade, aid, facilities, or water service?",
                "Is the bbox tightly localized enough for a follow-up imagery fetch?",
            ],
        },
        "downlink_policy": {
            "actions": list(ACTIONS),
            "downlink_now_threshold": {
                "severity": "high",
                "confidence_gte": 0.75,
                "requires_material_impact": True,
                "requires_valid_schema": True,
            },
        },
        "training_export": {
            "format": "orbit_lifeline_before_after_v1",
            "candidate_schema": list(REQUIRED_CANDIDATE_FIELDS),
            "labels": {
                "event_types": list(EVENT_TYPES),
                "civilian_impacts": list(CIVILIAN_IMPACTS),
                "actions": list(ACTIONS),
            },
            "recommended_assets": [
                "baseline_frame.asset_ref",
                "current_frame.asset_ref",
                "candidate.bbox",
                "sample.json",
                "training.jsonl row",
            ],
        },
    }


def evaluate_lifeline_predictions(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate candidate decisions against expected actions for offline checks."""
    total = len(cases)
    rows: list[dict[str, Any]] = []
    counts = {
        "schema_valid": 0,
        "bbox_valid": 0,
        "action_match": 0,
        "expected_downlink_now": 0,
        "predicted_downlink_now": 0,
        "true_downlink_now": 0,
    }

    for index, case in enumerate(cases):
        candidate = normalize_lifeline_candidate(case.get("candidate"))
        decision = score_lifeline_candidate(candidate, case.get("asset") if isinstance(case.get("asset"), dict) else None)
        expected_action = str(case.get("expected_action") or "").strip().lower()
        predicted_action = decision["action"]
        if candidate["schema_valid"]:
            counts["schema_valid"] += 1
        if candidate["bbox_valid"]:
            counts["bbox_valid"] += 1
        if predicted_action == "downlink_now":
            counts["predicted_downlink_now"] += 1
        if expected_action == "downlink_now":
            counts["expected_downlink_now"] += 1
        if expected_action and predicted_action == expected_action:
            counts["action_match"] += 1
            if expected_action == "downlink_now":
                counts["true_downlink_now"] += 1
        rows.append(
            {
                "index": index,
                "predicted_action": predicted_action,
                "expected_action": expected_action or None,
                "schema_valid": candidate["schema_valid"],
                "bbox_valid": candidate["bbox_valid"],
                "confidence": candidate["confidence"],
                "reasons": decision["reasons"],
            }
        )

    expected_downlink = counts["expected_downlink_now"]
    downlink_recall = (
        counts["true_downlink_now"] / expected_downlink
        if expected_downlink
        else 1.0
    )
    return {
        "total": total,
        "schema_valid": counts["schema_valid"],
        "bbox_valid": counts["bbox_valid"],
        "action_match": counts["action_match"],
        "predicted_downlink_now": counts["predicted_downlink_now"],
        "expected_downlink_now": counts["expected_downlink_now"],
        "downlink_now_recall": round(downlink_recall, 4),
        "rows": rows,
    }


def check_lifeline_acceptance(base_summary: dict[str, Any], adapter_summary: dict[str, Any]) -> dict[str, Any]:
    """Return a simple base-vs-adapter acceptance decision."""
    failures: list[str] = []
    total = int(adapter_summary.get("total") or 0)
    adapter_schema_valid = int(adapter_summary.get("schema_valid") or 0)
    adapter_bbox_valid = int(adapter_summary.get("bbox_valid") or 0)
    adapter_recall = float(adapter_summary.get("downlink_now_recall") or 0.0)
    base_recall = float(base_summary.get("downlink_now_recall") or 0.0)
    adapter_downlinks = int(adapter_summary.get("predicted_downlink_now") or 0)

    if total <= 0:
        failures.append("adapter evaluation has no cases")
    if adapter_schema_valid != total:
        failures.append("adapter produced schema-invalid candidates")
    if adapter_bbox_valid != total:
        failures.append("adapter produced bbox-invalid candidates")
    if adapter_recall <= base_recall:
        failures.append("adapter did not improve downlink_now recall over baseline")
    if adapter_downlinks <= 0:
        failures.append("adapter produced no downlink_now decisions")

    return {
        "accepted": not failures,
        "base_downlink_now_recall": base_recall,
        "adapter_downlink_now_recall": adapter_recall,
        "failures": failures,
    }
