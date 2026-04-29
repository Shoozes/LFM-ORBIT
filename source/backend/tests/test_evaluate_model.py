import json

from scripts import evaluate_model

_DEFAULT = object()


def _record(
    *,
    sample_id: str,
    split: str = "eval",
    priority: str = "medium",
    change_score: float = 0.40,
    confidence: float = 0.81,
    before_window: dict | None | object = _DEFAULT,
    after_window: dict | None | object = _DEFAULT,
) -> dict:
    default_before = {
        "label": "2024-06",
        "quality": 0.9,
        "nir": 0.68,
        "red": 0.10,
        "swir": 0.18,
        "ndvi": 0.70,
        "nbr": 0.55,
        "evi2": 0.52,
        "ndmi": 0.31,
        "soil_ratio": 0.20,
        "flags": [],
    }
    default_after = {
        "label": "2025-06",
        "quality": 0.88,
        "nir": 0.42,
        "red": 0.14,
        "swir": 0.26,
        "ndvi": 0.36,
        "nbr": 0.28,
        "evi2": 0.25,
        "ndmi": 0.15,
        "soil_ratio": 0.38,
        "flags": [],
    }
    return {
        "sample_id": sample_id,
        "event_id": sample_id,
        "cell_id": f"{sample_id}_cell",
        "split": split,
        "priority": priority,
        "change_score": change_score,
        "confidence": confidence,
        "reason_codes": ["ndvi_drop"],
        "observation_source": "semi_real_loader_v1",
        "before_window": default_before if before_window is _DEFAULT else before_window,
        "after_window": default_after if after_window is _DEFAULT else after_window,
    }


def test_load_dataset_records_filters_split_from_samples_jsonl(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    records = [
        _record(sample_id="train_one", split="train"),
        _record(sample_id="eval_one", split="eval"),
    ]
    (dataset_dir / "samples.jsonl").write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    loaded = evaluate_model.load_dataset_records(dataset_dir, split="eval")

    assert len(loaded) == 1
    assert loaded[0]["sample_id"] == "eval_one"


def test_evaluate_records_normalizes_medium_to_moderate_and_skips_missing_windows():
    records = [
        _record(sample_id="match_medium", priority="medium", change_score=0.40),
        _record(sample_id="match_critical", priority="critical", change_score=0.70),
        _record(sample_id="skip_missing", before_window=None, after_window=None),
    ]

    summary, predictions = evaluate_model.evaluate_records(records)

    assert summary["total_records"] == 3
    assert summary["evaluated_records"] == 2
    assert summary["skipped_records"] == 1
    assert summary["exact_matches"] == 2
    assert summary["exact_severity_accuracy"] == 1.0
    assert summary["action_accuracy"] == 1.0
    assert summary["label_contract"]["preferred_source"] == "ground_truth_payload"
    assert summary["severity_confusion"]["moderate"]["moderate"] == 1
    assert summary["severity_confusion"]["critical"]["critical"] == 1
    skipped = next(row for row in predictions if row["sample_id"] == "skip_missing")
    assert skipped["status"] == "skipped"
    assert skipped["skip_reason"] == "missing_windows"


def test_evaluate_records_prefers_ground_truth_payload_for_controls():
    record = _record(
        sample_id="control_prune",
        priority="critical",
        change_score=0.15,
        confidence=0.20,
    )
    record["ground_truth_payload"] = {"action": "prune", "category": "none"}

    summary, predictions = evaluate_model.evaluate_records([record])

    assert summary["binary_confusion"]["true_negative"] == 1
    assert predictions[0]["label_source"] == "ground_truth_payload"
    assert predictions[0]["expected_action"] == "prune"
    assert predictions[0]["predicted_action"] == "prune"


def test_write_eval_artifacts_writes_summary_and_predictions(tmp_path):
    records = [_record(sample_id="artifact_eval", priority="high", change_score=0.50)]
    output_dir = tmp_path / "eval_artifacts"

    summary = evaluate_model.write_eval_artifacts(
        tmp_path / "dataset",
        records,
        split="eval",
        output_dir=output_dir,
    )

    assert summary["model"] == "offline_lfm_v1"
    assert summary["evaluated_records"] == 1
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "predictions.jsonl").exists()

    payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert payload["artifacts"]["summary"] == "summary.json"
    assert payload["artifacts"]["predictions"] == "predictions.jsonl"


def test_write_eval_artifacts_writes_promotion_comparison(tmp_path):
    records = [_record(sample_id="candidate_eval", priority="high", change_score=0.50)]
    output_dir = tmp_path / "eval_artifacts"
    baseline = {
        "format": "orbit_eval_v2",
        "model": "baseline",
        "evaluated_records": 1,
        "exact_severity_accuracy": 0.50,
        "positive_recall": 0.50,
        "action_accuracy": 0.50,
    }

    summary = evaluate_model.write_eval_artifacts(
        tmp_path / "dataset",
        records,
        split="eval",
        output_dir=output_dir,
        model_name="candidate",
        baseline_summary=baseline,
        promotion_thresholds={
            "min_exact_severity_accuracy": 0.5,
            "min_positive_recall": 0.5,
            "min_action_accuracy": 0.5,
            "max_exact_accuracy_regression": 0.02,
            "max_positive_recall_regression": 0.05,
        },
    )

    assert summary["artifacts"]["comparison"] == "comparison.json"
    comparison = json.loads((output_dir / "comparison.json").read_text(encoding="utf-8"))
    promotion = json.loads((output_dir / "promotion.json").read_text(encoding="utf-8"))
    assert comparison["format"] == "orbit_eval_comparison_v1"
    assert comparison["promotion_decision"] == "promote"
    assert promotion["format"] == "orbit_model_promotion_v1"
    assert promotion["decision"] == "promote"
