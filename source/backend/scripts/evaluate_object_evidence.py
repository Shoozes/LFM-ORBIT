"""Evaluate frozen Object Evidence Mode fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_EVAL_PATH = Path(__file__).resolve().parent.parent / "assets" / "evals" / "object_evidence_gold.jsonl"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on line {lineno}: {path}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"eval row must be an object on line {lineno}: {path}")
        rows.append(payload)
    return rows


def _valid_bbox(box: dict[str, Any]) -> bool:
    bbox = box.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        return False
    return all(isinstance(value, (int, float)) and 0.0 <= float(value) <= 1.0 for value in bbox)


def _coerce_bbox(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        bbox = [float(entry) for entry in value]
    except (TypeError, ValueError):
        return None
    x1, y1, x2, y2 = bbox
    if not all(0.0 <= entry <= 1.0 for entry in bbox):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return bbox


def _bbox_iou(left: list[float], right: list[float]) -> float:
    lx1, ly1, lx2, ly2 = left
    rx1, ry1, rx2, ry2 = right
    ix1 = max(lx1, rx1)
    iy1 = max(ly1, ry1)
    ix2 = min(lx2, rx2)
    iy2 = min(ly2, ry2)
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    left_area = (lx2 - lx1) * (ly2 - ly1)
    right_area = (rx2 - rx1) * (ry2 - ry1)
    union = left_area + right_area - intersection
    if union <= 0.0:
        return 0.0
    return intersection / union


def _best_iou_for_expected_box(expected_box: dict[str, Any], predicted_boxes: list[dict[str, Any]]) -> float:
    expected_bbox = _coerce_bbox(expected_box.get("bbox"))
    if expected_bbox is None:
        return 0.0
    expected_label = str(expected_box.get("label") or "").strip().lower()
    best_iou = 0.0
    for predicted_box in predicted_boxes:
        predicted_bbox = _coerce_bbox(predicted_box.get("bbox"))
        if predicted_bbox is None:
            continue
        predicted_label = str(predicted_box.get("label") or "").strip().lower()
        if expected_label and predicted_label and predicted_label != expected_label:
            continue
        best_iou = max(best_iou, _bbox_iou(expected_bbox, predicted_bbox))
    return best_iou


def evaluate_cases(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "format": "orbit_object_evidence_eval_v1",
            "case_count": 0,
            "schema_valid_rate": 1.0,
            "bbox_valid_rate": 1.0,
            "label_recall": 1.0,
            "count_error_mae": 0.0,
            "action_match": 1.0,
            "false_downlink_rate": 0.0,
            "fallback_rate": 0.0,
            "grounding_iou_at_0_5": 1.0,
            "grounding_mean_iou": 1.0,
            "payload_reduction_ratio": 0.0,
        }

    schema_valid = 0
    bbox_valid = 0
    bbox_total = 0
    recalled_labels = 0
    expected_label_total = 0
    count_error_total = 0.0
    count_error_n = 0
    action_matches = 0
    false_downlinks = 0
    fallback_count = 0
    iou_matches = 0
    iou_total = 0
    iou_sum = 0.0
    reduction_ratios: list[float] = []

    for row in rows:
        summary = row.get("detection_summary")
        expected_labels = [str(item) for item in row.get("expected_labels", [])]
        expected_counts = row.get("expected_counts") if isinstance(row.get("expected_counts"), dict) else {}
        counts = summary.get("counts_by_label") if isinstance(summary, dict) and isinstance(summary.get("counts_by_label"), dict) else {}
        boxes = summary.get("top_boxes") if isinstance(summary, dict) and isinstance(summary.get("top_boxes"), list) else []
        provenance = summary.get("provenance") if isinstance(summary, dict) and isinstance(summary.get("provenance"), dict) else {}

        if isinstance(summary, dict) and isinstance(counts, dict) and isinstance(boxes, list):
            schema_valid += 1

        bbox_total += len(boxes)
        bbox_valid += sum(1 for box in boxes if isinstance(box, dict) and _valid_bbox(box))

        found_labels = {str(label) for label, count in counts.items() if int(count or 0) > 0}
        expected_label_total += len(expected_labels)
        recalled_labels += sum(1 for label in expected_labels if label in found_labels)

        for label, expected_count in expected_counts.items():
            count_error_total += abs(int(counts.get(label, 0) or 0) - int(expected_count or 0))
            count_error_n += 1

        expected_action = str(row.get("expected_action") or "")
        predicted_action = str(row.get("predicted_action") or expected_action)
        if predicted_action == expected_action:
            action_matches += 1
        if predicted_action == "downlink_now" and expected_action != "downlink_now":
            false_downlinks += 1

        if bool(provenance.get("heuristic_fallback")):
            fallback_count += 1

        expected_boxes = row.get("expected_boxes")
        if isinstance(expected_boxes, list):
            for expected_box in expected_boxes:
                if not isinstance(expected_box, dict):
                    continue
                best_iou = _best_iou_for_expected_box(expected_box, [box for box in boxes if isinstance(box, dict)])
                iou_total += 1
                iou_sum += best_iou
                if best_iou >= 0.5:
                    iou_matches += 1

        raw_payload = int(row.get("raw_payload_bytes") or 0)
        alert_payload = int(row.get("alert_payload_bytes") or 0)
        if raw_payload > 0 and alert_payload > 0:
            reduction_ratios.append(raw_payload / alert_payload)

    return {
        "format": "orbit_object_evidence_eval_v1",
        "case_count": len(rows),
        "schema_valid_rate": schema_valid / len(rows),
        "bbox_valid_rate": (bbox_valid / bbox_total) if bbox_total else 1.0,
        "label_recall": (recalled_labels / expected_label_total) if expected_label_total else 1.0,
        "count_error_mae": (count_error_total / count_error_n) if count_error_n else 0.0,
        "action_match": action_matches / len(rows),
        "false_downlink_rate": false_downlinks / len(rows),
        "fallback_rate": fallback_count / len(rows),
        "grounding_iou_at_0_5": (iou_matches / iou_total) if iou_total else 1.0,
        "grounding_mean_iou": round(iou_sum / iou_total, 4) if iou_total else 1.0,
        "payload_reduction_ratio": round(sum(reduction_ratios) / len(reduction_ratios), 2) if reduction_ratios else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate frozen object evidence fixtures.")
    parser.add_argument("--eval-file", type=Path, default=DEFAULT_EVAL_PATH)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    rows = _read_jsonl(args.eval_file) if args.eval_file.exists() else []
    summary = evaluate_cases(rows)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
