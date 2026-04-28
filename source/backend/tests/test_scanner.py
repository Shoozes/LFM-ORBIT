from core.scanner import _quality_gate_fallback_score, _rejection_reason_from_exception, _should_force_demo_anomaly


def test_rejection_reason_from_exception_preserves_qc_low_valid_pixels():
    reason = _rejection_reason_from_exception(
        ValueError("Scene Quality Rejected: Insufficient Valid Pixels")
    )

    assert reason == "insufficient_valid_pixels"


def test_rejection_reason_from_exception_defaults_to_scan_failure():
    assert _rejection_reason_from_exception(RuntimeError("provider unavailable")) == "scan_failure"


def test_quality_rejections_do_not_force_demo_anomalies():
    assert _should_force_demo_anomaly(1, 9, "insufficient_valid_pixels") is False
    assert _should_force_demo_anomaly(1, 9, "scene_quality_rejected") is False
    assert _should_force_demo_anomaly(1, 9, "scan_failure") is True


def test_quality_gate_fallback_score_blocks_alert_transmission():
    score = _quality_gate_fallback_score("insufficient_valid_pixels")

    assert score["change_score"] == 0.0
    assert score["confidence"] == 0.0
    assert "quality_gate_failed" in score["reason_codes"]
    assert "suspected_canopy_loss" not in score["reason_codes"]
