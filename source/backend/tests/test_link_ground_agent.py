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


def test_operator_query_ack_reports_ground_model(monkeypatch):
    from core.ground_agent import _build_operator_query_ack

    monkeypatch.setattr(
        "core.ground_agent.ground_model_status",
        lambda: {"model": "LFM2.5-VL-450M-Q4_0.gguf"},
    )

    ack = _build_operator_query_ack("  check   sat/gnd bus  ")

    assert ack["status"] == "acknowledged"
    assert ack["model"] == "LFM2.5-VL-450M-Q4_0.gguf"
    assert ack["message"] == "check sat/gnd bus"
    assert "Ground Validator received" in ack["note"]


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


@pytest.mark.asyncio
async def test_ground_agent_bus_query_round_trip(tmp_path, monkeypatch):
    import asyncio

    from core.agent_bus import get_recent_messages, init_bus, post_message
    from core.ground_agent import run_ground_agent

    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setattr("core.ground_agent._POLL_INTERVAL", 0.01)
    monkeypatch.setattr("core.ground_agent.get_active_mission", lambda: None)
    monkeypatch.setattr(
        "core.ground_agent.warm_ground_model",
        lambda: {
            "model": "LFM2.5-VL-450M-Q4_0.gguf",
            "shared_gguf_model": "LFM2.5-VL-450M-Q4_0.gguf",
            "shared_with_satellite": True,
            "runtime_inference_mode": "text_evidence_packet",
        },
    )
    monkeypatch.setattr(
        "core.ground_agent.ground_model_status",
        lambda: {
            "model": "LFM2.5-VL-450M-Q4_0.gguf",
            "shared_gguf_model": "LFM2.5-VL-450M-Q4_0.gguf",
            "shared_with_satellite": True,
            "runtime_inference_mode": "text_evidence_packet",
        },
    )

    init_bus(reset=True)
    stop_event = asyncio.Event()
    task = asyncio.create_task(run_ground_agent(stop_event))
    try:
        post_message(
            "satellite",
            "ground",
            "query",
            {"message": "check SAT/GND link"},
            cell_id="sq_test_001",
        )

        ack = None
        for _ in range(80):
            for msg in get_recent_messages(limit=20, sender="ground", msg_type="status"):
                payload = msg["payload"]
                if payload.get("status") == "acknowledged":
                    ack = msg
                    break
            if ack:
                break
            await asyncio.sleep(0.02)

        assert ack is not None
        assert ack["cell_id"] == "sq_test_001"
        assert ack["payload"]["model"] == "LFM2.5-VL-450M-Q4_0.gguf"
        assert "Ground Validator received" in ack["payload"]["note"]
    finally:
        stop_event.set()
        await asyncio.wait_for(task, timeout=1)


@pytest.mark.asyncio
async def test_ground_agent_confirms_satellite_flag_to_satellite(tmp_path, monkeypatch):
    import asyncio

    from core.agent_bus import get_recent_messages, init_bus, post_message
    from core.ground_agent import run_ground_agent

    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("ORBIT_GROUND_GGUF_ANALYSIS", "false")
    monkeypatch.setattr("core.ground_agent._POLL_INTERVAL", 0.01)
    monkeypatch.setattr("core.ground_agent.get_active_mission", lambda: None)
    monkeypatch.setattr(
        "core.ground_agent.warm_ground_model",
        lambda: {
            "model": "offline_lfm_v1",
            "shared_gguf_model": "LFM2.5-VL-450M-Q4_0.gguf",
            "shared_with_satellite": False,
            "runtime_inference_mode": "text_evidence_packet",
        },
    )
    monkeypatch.setattr(
        "core.ground_agent.analyze_alert",
        lambda **kwargs: {
            "model": "offline_lfm_v1",
            "severity": "high",
            "summary": "Candidate evidence packet is review-worthy.",
            "findings": ["strong temporal signal"],
            "confidence_note": "test",
            "source_note": "test",
        },
    )
    monkeypatch.setattr(
        "core.ground_agent._generate_cell_timelapse",
        lambda cell_id, mission=None: (None, "Temporal context reviewed.", "test_cache"),
    )
    monkeypatch.setattr("core.ground_agent.cell_to_latlng", lambda cell_id: (28.5, -81.5))
    monkeypatch.setattr("core.ground_agent.upsert_pin", lambda **kwargs: None)
    monkeypatch.setattr("core.ground_agent.add_gallery_item", lambda **kwargs: None)

    init_bus(reset=True)
    stop_event = asyncio.Event()
    task = asyncio.create_task(run_ground_agent(stop_event))
    try:
        post_message(
            "satellite",
            "ground",
            "flag",
            {
                "change_score": 0.86,
                "confidence": 0.91,
                "reason_codes": ["burn_scar_candidate"],
                "before_window": {"ndvi": 0.72},
                "after_window": {"ndvi": 0.35},
                "observation_source": "simsat_fireline",
            },
            cell_id="sq_flag_001",
        )

        confirmation = None
        for _ in range(80):
            matches = get_recent_messages(limit=20, sender="ground", recipient="satellite", msg_type="confirmation")
            if matches:
                confirmation = matches[-1]
                break
            await asyncio.sleep(0.02)

        assert confirmation is not None
        assert confirmation["cell_id"] == "sq_flag_001"
        assert confirmation["payload"]["model"] == "offline_lfm_v1"
        assert confirmation["payload"]["severity"] == "high"
        assert "CONFIRM" in confirmation["payload"]["action"]
    finally:
        stop_event.set()
        await asyncio.wait_for(task, timeout=1)
