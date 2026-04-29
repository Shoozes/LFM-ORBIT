"""Evaluate Orbit-exported samples with the current baseline analysis path.

This first-pass harness replays exported samples through the offline analyzer,
writes reproducible artifacts, and establishes the promotion/eval lane that
future tuned or multimodal backends can plug into.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.analyzer import analyze_alert
from core.paths import get_runtime_data_dir


DEFAULT_MODEL = "offline_lfm_v1"
VALID_SPLITS = {"train", "eval", "all"}
DEFAULT_PROMOTION_THRESHOLDS = {
    "min_exact_severity_accuracy": 0.70,
    "min_positive_recall": 0.70,
    "min_action_accuracy": 0.80,
    "max_exact_accuracy_regression": 0.02,
    "max_positive_recall_regression": 0.05,
}


def _normalize_severity(value: str | None) -> str:
    label = str(value or "").strip().lower()
    if label == "medium":
        return "moderate"
    return label or "unknown"


def _positive_label(value: str | None) -> bool:
    return _normalize_severity(value) in {"moderate", "high", "critical"}


def _expected_label(record: dict[str, Any]) -> dict[str, Any]:
    payload = record.get("ground_truth_payload") if isinstance(record.get("ground_truth_payload"), dict) else {}
    payload_action = str(payload.get("action") or "").strip().lower()
    target_action = str(record.get("target_action") or "").strip().lower()

    if payload_action in {"alert", "review", "prune"}:
        expected_action = "prune" if payload_action == "prune" else "alert"
        label_source = "ground_truth_payload"
    elif target_action in {"alert", "downlink_now", "review"}:
        expected_action = "alert"
        label_source = "target_action"
    elif target_action == "prune" or str(record.get("record_type") or "") == "control":
        expected_action = "prune"
        label_source = "target_action"
    else:
        expected_action = "alert" if _positive_label(record.get("expected_severity") or record.get("priority")) else "prune"
        label_source = "priority"

    expected_severity = _normalize_severity(record.get("expected_severity") or record.get("priority"))
    if expected_action == "prune" and expected_severity == "unknown":
        expected_severity = "none"
    return {
        "expected_action": expected_action,
        "expected_positive": expected_action == "alert",
        "expected_severity": expected_severity,
        "label_source": label_source,
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            records.append(payload)
    return records


def resolve_dataset_path(dataset: Path, split: str) -> Path:
    if dataset.is_file():
        return dataset

    if split in {"train", "eval"}:
        split_path = dataset / f"{split}.jsonl"
        if split_path.exists():
            return split_path

    samples_path = dataset / "samples.jsonl"
    if samples_path.exists():
        return samples_path

    raise FileNotFoundError(f"No dataset JSONL found under {dataset}")


def load_dataset_records(dataset: Path, split: str = "eval") -> list[dict[str, Any]]:
    dataset_path = resolve_dataset_path(dataset, split)
    records = _load_jsonl(dataset_path)
    if split in {"train", "eval"} and dataset_path.name == "samples.jsonl":
        return [record for record in records if str(record.get("split", "")).lower() == split]
    return records


def _evaluate_record(record: dict[str, Any]) -> dict[str, Any]:
    before_window = record.get("before_window")
    after_window = record.get("after_window")
    label = _expected_label(record)

    if not isinstance(before_window, dict) or not isinstance(after_window, dict):
        return {
            "sample_id": record.get("sample_id", ""),
            "cell_id": record.get("cell_id", ""),
            "event_id": record.get("event_id", ""),
            "split": record.get("split", ""),
            "status": "skipped",
            "skip_reason": "missing_windows",
            **label,
        }

    result = analyze_alert(
        change_score=float(record.get("change_score", 0.0)),
        confidence=float(record.get("confidence", 0.0)),
        reason_codes=list(record.get("reason_codes", [])),
        before_window=before_window,
        after_window=after_window,
        observation_source=str(record.get("observation_source", "unknown")),
        demo_forced_anomaly=bool(record.get("demo_forced_anomaly", False)),
    )
    predicted_severity = _normalize_severity(result.get("severity"))
    exact_match = predicted_severity == label["expected_severity"] if label["expected_severity"] != "unknown" else None
    predicted_positive = _positive_label(predicted_severity)
    predicted_action = "alert" if predicted_positive else "prune"
    action_match = predicted_action == label["expected_action"]

    return {
        "sample_id": record.get("sample_id", ""),
        "cell_id": record.get("cell_id", ""),
        "event_id": record.get("event_id", ""),
        "split": record.get("split", ""),
        "status": "evaluated",
        **label,
        "predicted_severity": predicted_severity,
        "predicted_action": predicted_action,
        "exact_match": exact_match,
        "action_match": action_match,
        "predicted_positive": predicted_positive,
        "model": result.get("model", DEFAULT_MODEL),
        "summary": result.get("summary", ""),
        "findings": list(result.get("findings", [])),
    }


def evaluate_records(records: list[dict[str, Any]], model_name: str = DEFAULT_MODEL) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    predictions = [_evaluate_record(record) for record in records]
    evaluated = [row for row in predictions if row["status"] == "evaluated"]
    skipped = [row for row in predictions if row["status"] != "evaluated"]

    exact_matches = sum(1 for row in evaluated if row.get("exact_match") is True)
    action_matches = sum(1 for row in evaluated if row.get("action_match") is True)
    true_positive = sum(1 for row in evaluated if row["expected_positive"] and row["predicted_positive"])
    true_negative = sum(1 for row in evaluated if not row["expected_positive"] and not row["predicted_positive"])
    false_positive = sum(1 for row in evaluated if not row["expected_positive"] and row["predicted_positive"])
    false_negative = sum(1 for row in evaluated if row["expected_positive"] and not row["predicted_positive"])

    confusion: dict[str, dict[str, int]] = {}
    for row in evaluated:
        expected = row["expected_severity"]
        predicted = row["predicted_severity"]
        confusion.setdefault(expected, {})
        confusion[expected][predicted] = confusion[expected].get(predicted, 0) + 1

    evaluated_count = len(evaluated)
    exact_accuracy = (exact_matches / evaluated_count) if evaluated_count else None
    action_accuracy = (action_matches / evaluated_count) if evaluated_count else None
    positive_precision = (true_positive / (true_positive + false_positive)) if (true_positive + false_positive) else None
    positive_recall = (true_positive / (true_positive + false_negative)) if (true_positive + false_negative) else None

    summary = {
        "format": "orbit_eval_v2",
        "model": model_name,
        "total_records": len(records),
        "evaluated_records": evaluated_count,
        "skipped_records": len(skipped),
        "exact_matches": exact_matches,
        "exact_severity_accuracy": exact_accuracy,
        "action_matches": action_matches,
        "action_accuracy": action_accuracy,
        "positive_precision": positive_precision,
        "positive_recall": positive_recall,
        "label_contract": {
            "preferred_source": "ground_truth_payload",
            "fallback_sources": ["target_action", "priority"],
            "positive_actions": ["alert", "review", "downlink_now"],
            "negative_action": "prune",
        },
        "binary_confusion": {
            "true_positive": true_positive,
            "true_negative": true_negative,
            "false_positive": false_positive,
            "false_negative": false_negative,
        },
        "severity_confusion": confusion,
        "notes": [
            "This first-pass harness replays Orbit-exported samples through the baseline offline analyzer.",
            "Labels prefer independent ground_truth_payload or target_action fields before falling back to priority.",
            "Tuned-model comparison is recorded through orbit_eval_comparison_v1 promotion artifacts.",
        ],
    }
    return summary, predictions


def load_eval_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Eval summary must be a JSON object: {path}")
    return payload


def _metric(summary: dict[str, Any], key: str) -> float | None:
    value = summary.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compare_eval_summaries(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    thresholds = {**DEFAULT_PROMOTION_THRESHOLDS, **(thresholds or {})}
    metric_keys = ["exact_severity_accuracy", "positive_recall", "positive_precision", "action_accuracy"]
    deltas: dict[str, float | None] = {}
    for key in metric_keys:
        baseline_value = _metric(baseline, key)
        candidate_value = _metric(candidate, key)
        deltas[key] = None if baseline_value is None or candidate_value is None else round(candidate_value - baseline_value, 6)

    blockers: list[str] = []
    candidate_exact = _metric(candidate, "exact_severity_accuracy")
    candidate_recall = _metric(candidate, "positive_recall")
    candidate_action = _metric(candidate, "action_accuracy")
    exact_delta = deltas["exact_severity_accuracy"]
    recall_delta = deltas["positive_recall"]

    if candidate_exact is None or candidate_exact < thresholds["min_exact_severity_accuracy"]:
        blockers.append("candidate exact severity accuracy is below threshold")
    if candidate_recall is None or candidate_recall < thresholds["min_positive_recall"]:
        blockers.append("candidate positive recall is below threshold")
    if candidate_action is None or candidate_action < thresholds["min_action_accuracy"]:
        blockers.append("candidate action accuracy is below threshold")
    if exact_delta is not None and exact_delta < -thresholds["max_exact_accuracy_regression"]:
        blockers.append("candidate exact severity accuracy regressed beyond tolerance")
    if recall_delta is not None and recall_delta < -thresholds["max_positive_recall_regression"]:
        blockers.append("candidate positive recall regressed beyond tolerance")

    return {
        "format": "orbit_eval_comparison_v1",
        "baseline_model": baseline.get("model", "baseline"),
        "candidate_model": candidate.get("model", "candidate"),
        "baseline_summary": {
            "evaluated_records": baseline.get("evaluated_records"),
            "exact_severity_accuracy": baseline.get("exact_severity_accuracy"),
            "positive_recall": baseline.get("positive_recall"),
            "action_accuracy": baseline.get("action_accuracy"),
        },
        "candidate_summary": {
            "evaluated_records": candidate.get("evaluated_records"),
            "exact_severity_accuracy": candidate.get("exact_severity_accuracy"),
            "positive_recall": candidate.get("positive_recall"),
            "action_accuracy": candidate.get("action_accuracy"),
        },
        "deltas": deltas,
        "thresholds": thresholds,
        "promotion_decision": "promote" if not blockers else "hold",
        "blockers": blockers,
    }


def _default_output_dir(model_name: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return get_runtime_data_dir() / "evals" / f"{stamp}-{model_name}"


def write_eval_artifacts(
    dataset: Path,
    records: list[dict[str, Any]],
    *,
    split: str,
    output_dir: Path,
    model_name: str = DEFAULT_MODEL,
    baseline_summary: dict[str, Any] | None = None,
    promotion_thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    summary, predictions = evaluate_records(records, model_name=model_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_payload = {
        **summary,
        "dataset": str(dataset),
        "split": split,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "artifacts": {
            "summary": "summary.json",
            "predictions": "predictions.jsonl",
        },
    }

    comparison: dict[str, Any] | None = None
    if baseline_summary is not None:
        comparison = compare_eval_summaries(
            baseline_summary,
            summary_payload,
            thresholds=promotion_thresholds,
        )
        summary_payload["artifacts"]["comparison"] = "comparison.json"
        summary_payload["artifacts"]["promotion"] = "promotion.json"

    (output_dir / "summary.json").write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    prediction_lines = [json.dumps(row, sort_keys=True) for row in predictions]
    (output_dir / "predictions.jsonl").write_text(
        "\n".join(prediction_lines) + ("\n" if prediction_lines else ""),
        encoding="utf-8",
    )
    if comparison is not None:
        (output_dir / "comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
        promotion_payload = {
            "format": "orbit_model_promotion_v1",
            "generated_at": summary_payload["generated_at"],
            "dataset": str(dataset),
            "split": split,
            "candidate_model": comparison["candidate_model"],
            "baseline_model": comparison["baseline_model"],
            "decision": comparison["promotion_decision"],
            "blockers": comparison["blockers"],
            "comparison_artifact": "comparison.json",
        }
        (output_dir / "promotion.json").write_text(json.dumps(promotion_payload, indent=2), encoding="utf-8")
    return summary_payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Orbit-exported samples with the current baseline analyzer.")
    parser.add_argument("--dataset", type=Path, required=True, help="Dataset export directory or JSONL file.")
    parser.add_argument("--split", default="eval", choices=sorted(VALID_SPLITS), help="Dataset split to evaluate.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Directory for evaluation artifacts.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Logical model/backend name for the eval report.")
    parser.add_argument("--baseline-summary", type=Path, default=None, help="Optional baseline summary.json for promotion comparison.")
    parser.add_argument("--min-exact-accuracy", type=float, default=DEFAULT_PROMOTION_THRESHOLDS["min_exact_severity_accuracy"])
    parser.add_argument("--min-positive-recall", type=float, default=DEFAULT_PROMOTION_THRESHOLDS["min_positive_recall"])
    parser.add_argument("--min-action-accuracy", type=float, default=DEFAULT_PROMOTION_THRESHOLDS["min_action_accuracy"])
    parser.add_argument("--max-exact-regression", type=float, default=DEFAULT_PROMOTION_THRESHOLDS["max_exact_accuracy_regression"])
    parser.add_argument("--max-recall-regression", type=float, default=DEFAULT_PROMOTION_THRESHOLDS["max_positive_recall_regression"])
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    records = load_dataset_records(args.dataset, split=args.split)
    output_dir = args.output_dir or _default_output_dir(args.model)
    baseline_summary = load_eval_summary(args.baseline_summary) if args.baseline_summary else None
    thresholds = {
        "min_exact_severity_accuracy": args.min_exact_accuracy,
        "min_positive_recall": args.min_positive_recall,
        "min_action_accuracy": args.min_action_accuracy,
        "max_exact_accuracy_regression": args.max_exact_regression,
        "max_positive_recall_regression": args.max_recall_regression,
    }
    summary = write_eval_artifacts(
        args.dataset,
        records,
        split=args.split,
        output_dir=output_dir,
        model_name=args.model,
        baseline_summary=baseline_summary,
        promotion_thresholds=thresholds,
    )
    print(
        "[Orbit] Evaluated {evaluated_records}/{total_records} records with {model}. Artifacts: {path}".format(
            path=output_dir,
            **summary,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
