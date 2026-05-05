import asyncio
import json

import pytest
from fastapi import WebSocketDisconnect

from core.scanner import (
    _quality_gate_fallback_score,
    _rejection_reason_from_exception,
    _score_unavailable_fallback_score,
    stream_region_scan,
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


def test_telemetry_stream_stays_idle_without_active_mission(monkeypatch):
    messages = []

    class FakeWebSocket:
        async def send_text(self, payload: str):
            messages.append(json.loads(payload))
            if len(messages) >= 2:
                raise WebSocketDisconnect()

    monkeypatch.setattr("core.scanner.get_active_mission", lambda: None)

    def fail_score(_cell_id, _observer=None):
        raise AssertionError("scanner should not score cells without an active mission")

    monkeypatch.setattr("core.scanner.score_cell_change", fail_score)

    with pytest.raises(WebSocketDisconnect):
        asyncio.run(stream_region_scan(FakeWebSocket()))

    assert messages[0]["type"] == "grid_init"
    assert messages[0]["data"]["features"] == []
    assert messages[1] == {"type": "scan_complete"}
