"""Batch object evidence helpers built on the visual grounding path."""

from __future__ import annotations

import math
import re
from typing import Any, Callable

from core.contracts import DetectionBox, DetectionSummary, ObjectTarget
from core.object_targets import normalize_object_targets
from core.vlm import explain_vlm_grounding


GroundingFn = Callable[[list[float], str], dict[str, Any]]

VALID_COLOR_KEYS = frozenset(
    {
        "aid",
        "cargo",
        "custom",
        "cryosphere",
        "environmental",
        "hazard",
        "industrial_surface",
        "infrastructure",
        "land_cover_change",
        "lifeline",
        "mobility",
        "structure",
        "surface_change",
        "vehicle",
        "vegetation",
        "vessel",
        "water",
        "water_industrial",
        "waterline",
    }
)

COLOR_KEY_ALIASES = {
    "excavation": "surface_change",
}

EXACT_OBJECT_CLASS_KEYS = frozenset({"cargo", "mobility", "structure", "vehicle", "vessel"})
MIN_CONFIDENCE_BY_CLASS = {
    "cargo": 0.72,
    "structure": 0.70,
    "vehicle": 0.72,
    "vessel": 0.72,
}


def _clamp_unit(value: Any) -> float:
    if not isinstance(value, (int, float)):
        return 0.0
    numeric = float(value)
    if not math.isfinite(numeric):
        return 0.0
    return min(1.0, max(0.0, numeric))


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return text or "object"


def color_key_for_class(class_key: str | None) -> str:
    key = (class_key or "").strip().lower()
    key = COLOR_KEY_ALIASES.get(key, key)
    if key in VALID_COLOR_KEYS:
        return key
    return "fallback"


def _read_provenance(provenance: dict[str, Any], key: str, fallback: str) -> str:
    value = provenance.get(key)
    return str(value).strip() if isinstance(value, str) and value.strip() else fallback


def _aggregate_provenance_value(records: list[dict[str, Any]], key: str, fallback: str) -> str:
    values = {
        str(record[key]).strip()
        for record in records
        if isinstance(record.get(key), str) and str(record[key]).strip()
    }
    if not values:
        return fallback
    if len(values) == 1:
        return next(iter(values))
    return "mixed"


def _normalize_bbox(raw_bbox: Any, bbox_format: str | None) -> list[float] | None:
    if not isinstance(raw_bbox, list) or len(raw_bbox) != 4:
        return None
    values = [_clamp_unit(entry) for entry in raw_bbox]
    if bbox_format == "unit_xyxy":
        xmin, ymin, xmax, ymax = values
    else:
        ymin, xmin, ymax, xmax = values
    left, right = sorted((xmin, xmax))
    top, bottom = sorted((ymin, ymax))
    if right <= left or bottom <= top:
        return None
    return [left, top, right, bottom]


def normalize_detection_box(
    raw_box: dict[str, Any],
    *,
    target: ObjectTarget,
    provenance: dict[str, Any],
    index: int,
    frame_ref: str | None = None,
) -> DetectionBox | None:
    raw_format = raw_box.get("bbox_format")
    bbox = _normalize_bbox(raw_box.get("bbox"), raw_format if isinstance(raw_format, str) else None)
    if bbox is None:
        return None
    confidence = raw_box.get("confidence", raw_box.get("score", 0.5))
    confidence_value = _clamp_unit(confidence)
    class_key = (target.get("class_key") or "").strip().lower()
    heuristic_fallback = bool(provenance.get("heuristic_fallback"))
    if heuristic_fallback and class_key in EXACT_OBJECT_CLASS_KEYS:
        return None
    if confidence_value < MIN_CONFIDENCE_BY_CLASS.get(class_key, 0.0):
        return None
    label = target["label"]
    box: DetectionBox = {
        "id": f"box_{_slug(label)}_{index:03d}",
        "label": label,
        "bbox": bbox,
        "bbox_format": "unit_xyxy",
        "confidence": confidence_value,
        "color_key": color_key_for_class(target.get("class_key")),
        "source_model": str(raw_box.get("source_model") or _read_provenance(provenance, "model", "unknown")),
        "prompt": target["prompt"],
        "runtime_truth_mode": str(raw_box.get("runtime_truth_mode") or _read_provenance(provenance, "runtime_truth_mode", "unknown")),
        "imagery_origin": str(raw_box.get("imagery_origin") or _read_provenance(provenance, "imagery_origin", "unknown")),
        "scoring_basis": str(raw_box.get("scoring_basis") or _read_provenance(provenance, "scoring_basis", "visual_only")),
    }
    if class_key == "vessel" or re.search(r"\b(area|zone|group|context|queue|yard|basin|cluster)\b", label, re.IGNORECASE):
        box["count_quality"] = "activity_region"
    if frame_ref:
        box["frame_ref"] = frame_ref
    return box


def summarize_detection_boxes(
    boxes: list[DetectionBox],
    *,
    target_pack_id: str | None = None,
    provenance: dict[str, str | bool] | None = None,
) -> DetectionSummary:
    counts: dict[str, int] = {}
    for box in boxes:
        counts[box["label"]] = counts.get(box["label"], 0) + 1
    top_boxes = sorted(boxes, key=lambda item: item["confidence"], reverse=True)[:12]
    return {
        "target_pack_id": target_pack_id,
        "total_boxes": len(boxes),
        "counts_by_label": counts,
        "top_boxes": top_boxes,
        "provenance": provenance or {},
    }


def run_object_evidence_batch(
    bbox: list[float],
    targets: list[dict[str, Any]],
    *,
    target_pack_id: str | None = None,
    frame_ref: str | None = None,
    grounding_fn: GroundingFn = explain_vlm_grounding,
) -> dict[str, Any]:
    normalized_targets = [target for target in normalize_object_targets(targets) if target["enabled"]]
    boxes: list[DetectionBox] = []
    provenance_records: list[dict[str, Any]] = []

    for target in normalized_targets:
        response = grounding_fn(bbox, target["prompt"])
        provenance = response.get("provenance") if isinstance(response.get("provenance"), dict) else {}
        provenance_records.append(dict(provenance))
        raw_results = response.get("results")
        if not isinstance(raw_results, list):
            continue
        for raw_box in raw_results:
            if not isinstance(raw_box, dict):
                continue
            box = normalize_detection_box(
                raw_box,
                target=target,
                provenance=provenance,
                index=len(boxes) + 1,
                frame_ref=frame_ref,
            )
            if box is not None:
                boxes.append(box)

    batch_provenance: dict[str, str | bool] = {
        "output_source": "object_evidence_batch",
        "heuristic_fallback": any(bool(item.get("heuristic_fallback")) for item in provenance_records),
    }
    if provenance_records:
        batch_provenance["runtime_truth_mode"] = _aggregate_provenance_value(
            provenance_records,
            "runtime_truth_mode",
            "unknown",
        )
        batch_provenance["imagery_origin"] = _aggregate_provenance_value(
            provenance_records,
            "imagery_origin",
            "unknown",
        )
        batch_provenance["scoring_basis"] = _aggregate_provenance_value(
            provenance_records,
            "scoring_basis",
            "visual_only",
        )
        batch_provenance["source_model"] = _aggregate_provenance_value(
            provenance_records,
            "model",
            "unknown",
        )

    summary = summarize_detection_boxes(
        boxes,
        target_pack_id=target_pack_id,
        provenance=batch_provenance,
    )
    return {
        "results": boxes,
        "summary": summary,
        "target_count": len(normalized_targets),
    }
