from core.scanner import (
    _quality_gate_fallback_score,
    _rejection_reason_from_exception,
    _score_unavailable_fallback_score,
)


def test_rejection_reason_from_exception_preserves_qc_low_valid_pixels():
    reason = _rejection_reason_from_exception(
        ValueError("Scene Quality Rejected: Insufficient Valid Pixels")
    )

    assert reason == "insufficient_valid_pixels"


def test_rejection_reason_from_exception_defaults_to_scan_failure():
    assert _rejection_reason_from_exception(RuntimeError("provider unavailable")) == "scan_failure"


def test_provider_failures_do_not_force_positive_alerts():
    score = _score_unavailable_fallback_score("scan_failure")

    assert score["change_score"] == 0.0
    assert score["confidence"] == 0.0
    assert "score_unavailable" in score["reason_codes"]
    assert "suspected_canopy_loss" not in score["reason_codes"]


def test_quality_gate_fallback_score_blocks_alert_transmission():
    score = _quality_gate_fallback_score("insufficient_valid_pixels")

    assert score["change_score"] == 0.0
    assert score["confidence"] == 0.0
    assert "quality_gate_failed" in score["reason_codes"]
    assert "suspected_canopy_loss" not in score["reason_codes"]
