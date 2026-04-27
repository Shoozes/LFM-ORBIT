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


def _normalize_severity(value: str | None) -> str:
    label = str(value or "").strip().lower()
    if label == "medium":
        return "moderate"
    return label or "unknown"


def _positive_label(value: str | None) -> bool:
    return _normalize_severity(value) in {"moderate", "high", "critical"}


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
    expected_severity = _normalize_severity(record.get("expected_severity") or record.get("priority"))

    if not isinstance(before_window, dict) or not isinstance(after_window, dict):
        return {
            "sample_id": record.get("sample_id", ""),
            "cell_id": record.get("cell_id", ""),
            "event_id": record.get("event_id", ""),
            "split": record.get("split", ""),
            "status": "skipped",
            "skip_reason": "missing_windows",
            "expected_severity": expected_severity,
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
    exact_match = predicted_severity == expected_severity if expected_severity != "unknown" else None
    expected_positive = _positive_label(expected_severity)
    predicted_positive = _positive_label(predicted_severity)

    return {
        "sample_id": record.get("sample_id", ""),
        "cell_id": record.get("cell_id", ""),
        "event_id": record.get("event_id", ""),
        "split": record.get("split", ""),
        "status": "evaluated",
        "expected_severity": expected_severity,
        "predicted_severity": predicted_severity,
        "exact_match": exact_match,
        "expected_positive": expected_positive,
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
    positive_precision = (true_positive / (true_positive + false_positive)) if (true_positive + false_positive) else None
    positive_recall = (true_positive / (true_positive + false_negative)) if (true_positive + false_negative) else None

    summary = {
        "format": "orbit_eval_v1",
        "model": model_name,
        "total_records": len(records),
        "evaluated_records": evaluated_count,
        "skipped_records": len(skipped),
        "exact_matches": exact_matches,
        "exact_severity_accuracy": exact_accuracy,
        "positive_precision": positive_precision,
        "positive_recall": positive_recall,
        "binary_confusion": {
            "true_positive": true_positive,
            "true_negative": true_negative,
            "false_positive": false_positive,
            "false_negative": false_negative,
        },
        "severity_confusion": confusion,
        "notes": [
            "This first-pass harness replays Orbit-exported samples through the baseline offline analyzer.",
            "Current exact-match labels are derived from exported severity/priority fields, not an independent gold benchmark.",
            "Operator-reviewed controls and tuned-model comparison are tracked in docs/TODO.md.",
        ],
    }
    return summary, predictions


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

    (output_dir / "summary.json").write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    prediction_lines = [json.dumps(row, sort_keys=True) for row in predictions]
    (output_dir / "predictions.jsonl").write_text(
        "\n".join(prediction_lines) + ("\n" if prediction_lines else ""),
        encoding="utf-8",
    )
    return summary_payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Orbit-exported samples with the current baseline analyzer.")
    parser.add_argument("--dataset", type=Path, required=True, help="Dataset export directory or JSONL file.")
    parser.add_argument("--split", default="eval", choices=sorted(VALID_SPLITS), help="Dataset split to evaluate.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Directory for evaluation artifacts.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Logical model/backend name for the eval report.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    records = load_dataset_records(args.dataset, split=args.split)
    output_dir = args.output_dir or _default_output_dir(args.model)
    summary = write_eval_artifacts(
        args.dataset,
        records,
        split=args.split,
        output_dir=output_dir,
        model_name=args.model,
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
