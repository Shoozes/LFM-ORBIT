from scripts import decision_gate


def test_decision_gate_prints_rejection_breakdown(monkeypatch, capsys):
    monkeypatch.setattr(
        decision_gate,
        "read_metrics_summary",
        lambda: {
            "total_cells_scanned": 20,
            "pct_scenes_rejected": 0.45,
            "pct_low_valid_coverage": 0.30,
            "average_inference_latency_ms": 20.0,
            "peak_memory_mb": 5.0,
            "runtime_failures_by_stage": {},
            "runtime_rejections_by_reason": {
                "insufficient_valid_pixels": 3,
                "scene_quality_rejected": 1,
            },
        },
    )

    decision_gate.generate_decision_gate()

    output = capsys.readouterr().out
    assert "QC REJECTION BREAKDOWN" in output
    assert "insufficient valid pixels: 3 (75.0%)" in output
    assert "STATUS: OPTICAL PIPELINE BLOCKED BY CLOUDS" in output


def test_decision_gate_distinguishes_high_rejects_from_low_coverage(monkeypatch, capsys):
    monkeypatch.setattr(
        decision_gate,
        "read_metrics_summary",
        lambda: {
            "total_cells_scanned": 20,
            "pct_scenes_rejected": 0.45,
            "pct_low_valid_coverage": 0.10,
            "average_inference_latency_ms": 20.0,
            "peak_memory_mb": 5.0,
            "runtime_failures_by_stage": {},
            "runtime_rejections_by_reason": {"scan_failure": 5},
        },
    )

    decision_gate.generate_decision_gate()

    output = capsys.readouterr().out
    assert "STATUS: OPTICAL PIPELINE REJECTION RATE HIGH" in output
    assert "low-valid-coverage is not the dominant measured blocker" in output
