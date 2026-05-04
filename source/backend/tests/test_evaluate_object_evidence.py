import json

import pytest

from scripts.evaluate_object_evidence import evaluate_cases, main


def test_evaluate_cases_handles_empty_file():
    assert evaluate_cases([])["case_count"] == 0
    assert evaluate_cases([])["schema_valid_rate"] == 1.0


def test_evaluate_cases_reports_metrics():
    summary = evaluate_cases(
        [
            {
                "detection_summary": {
                    "counts_by_label": {"dark smoke": 1},
                    "top_boxes": [{"label": "dark smoke", "bbox": [0, 0.1, 0.4, 0.8]}],
                    "provenance": {"heuristic_fallback": False},
                },
                "expected_labels": ["dark smoke"],
                "expected_counts": {"dark smoke": 1},
                "expected_boxes": [{"label": "dark smoke", "bbox": [0.02, 0.1, 0.38, 0.8]}],
                "expected_action": "defer",
                "raw_payload_bytes": 1000,
                "alert_payload_bytes": 100,
            }
        ]
    )

    assert summary["case_count"] == 1
    assert summary["bbox_valid_rate"] == 1.0
    assert summary["label_recall"] == 1.0
    assert summary["grounding_iou_at_0_5"] == 1.0
    assert summary["grounding_mean_iou"] > 0.8
    assert summary["payload_reduction_ratio"] == 10.0


def test_evaluate_cases_penalizes_low_iou_grounding():
    summary = evaluate_cases(
        [
            {
                "detection_summary": {
                    "counts_by_label": {"ship": 1},
                    "top_boxes": [{"label": "ship", "bbox": [0.1, 0.1, 0.2, 0.2]}],
                    "provenance": {"heuristic_fallback": False},
                },
                "expected_labels": ["ship"],
                "expected_boxes": [{"label": "ship", "bbox": [0.7, 0.7, 0.8, 0.8]}],
                "expected_action": "defer",
            }
        ]
    )

    assert summary["grounding_iou_at_0_5"] == 0.0
    assert summary["grounding_mean_iou"] == 0.0


def test_evaluate_script_fails_clearly_on_invalid_json(tmp_path, monkeypatch):
    bad_file = tmp_path / "bad.jsonl"
    bad_file.write_text("{bad\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["evaluate_object_evidence.py", "--eval-file", str(bad_file)])

    with pytest.raises(ValueError, match="invalid JSON"):
        main()
