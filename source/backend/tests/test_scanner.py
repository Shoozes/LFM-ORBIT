from core.scanner import _rejection_reason_from_exception


def test_rejection_reason_from_exception_preserves_qc_low_valid_pixels():
    reason = _rejection_reason_from_exception(
        ValueError("Scene Quality Rejected: Insufficient Valid Pixels")
    )

    assert reason == "insufficient_valid_pixels"


def test_rejection_reason_from_exception_defaults_to_scan_failure():
    assert _rejection_reason_from_exception(RuntimeError("provider unavailable")) == "scan_failure"
