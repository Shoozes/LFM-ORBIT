"""
Tests for core/link_state.py and core/ground_agent.py builder functions.
"""
import pytest


# ---------------------------------------------------------------------------
# link_state
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_link_state():
    """Ensure link state is restored to connected after each test."""
    from core.link_state import set_link_state
    set_link_state(True)
    yield
    set_link_state(True)


def test_link_connected_by_default():
    from core.link_state import is_link_connected
    assert is_link_connected() is True


def test_set_link_state_severed():
    from core.link_state import set_link_state, is_link_connected
    set_link_state(False)
    assert is_link_connected() is False


def test_set_link_state_restored():
    from core.link_state import set_link_state, is_link_connected
    set_link_state(False)
    set_link_state(True)
    assert is_link_connected() is True


def test_set_link_state_idempotent(caplog):
    """Setting the same state twice should not log a change the second time."""
    import logging
    from core.link_state import set_link_state
    with caplog.at_level(logging.WARNING, logger="core.link_state"):
        set_link_state(False)  # changes: connected→severed → logs
        caplog.clear()
        set_link_state(False)  # no change — should not log
    assert len(caplog.records) == 0


def test_set_link_state_logs_change(caplog):
    import logging
    from core.link_state import set_link_state
    with caplog.at_level(logging.WARNING, logger="core.link_state"):
        set_link_state(False)
    assert any("SEVERED" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# ground_agent — builder functions (pure logic, no async)
# ---------------------------------------------------------------------------

def test_severity_to_action_critical():
    from core.ground_agent import _severity_to_action
    action = _severity_to_action("critical")
    assert "ESCALATE" in action


def test_severity_to_action_high():
    from core.ground_agent import _severity_to_action
    action = _severity_to_action("high")
    assert "CONFIRM" in action


def test_severity_to_action_moderate():
    from core.ground_agent import _severity_to_action
    action = _severity_to_action("moderate")
    assert "MONITOR" in action


def test_severity_to_action_low_fallback():
    from core.ground_agent import _severity_to_action
    action = _severity_to_action("low")
    assert "ARCHIVE" in action


def test_build_confirmation_structure():
    from core.ground_agent import _build_confirmation
    analysis = {
        "severity": "high",
        "model": "offline_lfm_v1",
        "summary": "Vegetation loss detected.",
        "findings": ["ndvi_drop"],
    }
    flag_payload = {
        "change_score": 0.82,
        "confidence": 0.91,
        "reason_codes": ["ndvi_drop", "nir_drop"],
    }
    confirmation = _build_confirmation("cell_abc123", analysis, flag_payload)

    assert confirmation["severity"] == "high"
    assert confirmation["model"] == "offline_lfm_v1"
    assert confirmation["change_score"] == pytest.approx(0.82)
    assert confirmation["confidence"] == pytest.approx(0.91)
    assert "ndvi_drop" in confirmation["reason_codes"]
    assert "cell_abc123" in confirmation["note"]
    assert "HIGH" in confirmation["note"]
    assert confirmation["action"]  # non-empty


def test_build_confirmation_uses_action_for_severity():
    from core.ground_agent import _build_confirmation
    analysis = {"severity": "critical", "model": "m", "summary": "s", "findings": []}
    flag_payload = {"change_score": 0.95, "confidence": 0.99, "reason_codes": []}
    c = _build_confirmation("crit_cell", analysis, flag_payload)
    assert "ESCALATE" in c["action"]


def test_build_reject_structure():
    from core.ground_agent import _build_reject
    reject = _build_reject(
        "cell_xyz",
        "composite score too low",
        {
            "change_score": 0.22,
            "confidence": 0.41,
            "reason_codes": ["low_signal"],
            "observation_source": "seeded_cache",
        },
    )
    assert reject["severity"] == "rejected"
    assert "REJECT" in reject["action"]
    assert "cell_xyz" in reject["note"]
    assert "composite score too low" in reject["note"]
    assert reject["reason"] == "composite score too low"
    assert reject["change_score"] == pytest.approx(0.22)
    assert reject["confidence"] == pytest.approx(0.41)
    assert reject["reason_codes"] == ["low_signal"]
    assert reject["observation_source"] == "seeded_cache"


def test_build_confirmation_missing_payload_fields_defaults():
    """Should not raise even if flag_payload is empty."""
    from core.ground_agent import _build_confirmation
    analysis = {"severity": "moderate", "model": "m", "summary": "s", "findings": []}
    c = _build_confirmation("empty_cell", analysis, {})
    assert c["change_score"] == pytest.approx(0.0)
    assert c["confidence"] == pytest.approx(0.0)
    assert c["reason_codes"] == []
