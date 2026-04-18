"""
Tests for core/agent_bus.py — message bus and map pin CRUD.
Uses a temp-file SQLite DB so each test run is isolated.
"""
import os
import tempfile
import pytest

# Point the bus at a throw-away path before importing anything that touches it
@pytest.fixture(autouse=True)
def isolated_bus(tmp_path, monkeypatch):
    db = str(tmp_path / "test_bus.sqlite")
    monkeypatch.setenv("AGENT_BUS_PATH", db)
    # Re-init for each test
    from core import agent_bus
    agent_bus.init_bus(reset=True)
    yield db


# ---------------------------------------------------------------------------
# init_bus
# ---------------------------------------------------------------------------

def test_init_bus_creates_tables(isolated_bus):
    import sqlite3
    conn = sqlite3.connect(isolated_bus)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "agent_messages" in tables
    assert "map_pins" in tables
    conn.close()


def test_init_bus_reset_clears_data(isolated_bus):
    from core.agent_bus import post_message, init_bus, get_bus_stats
    post_message("satellite", "ground", "flag", {"note": "test"}, cell_id="abc123")
    assert get_bus_stats()["total_messages"] == 1
    init_bus(reset=True)
    assert get_bus_stats()["total_messages"] == 0


# ---------------------------------------------------------------------------
# post_message / pull_messages
# ---------------------------------------------------------------------------

def test_post_message_returns_id():
    from core.agent_bus import post_message
    msg_id = post_message("satellite", "ground", "flag", {"score": 0.9}, cell_id="cell1")
    assert isinstance(msg_id, int)
    assert msg_id >= 1


def test_pull_messages_returns_unread_for_recipient():
    from core.agent_bus import post_message, pull_messages
    post_message("satellite", "ground", "flag", {"note": "a"}, cell_id="c1")
    post_message("satellite", "ground", "flag", {"note": "b"}, cell_id="c2")
    # Message for a different recipient shouldn't appear
    post_message("ground", "satellite", "confirmation", {"note": "c"})

    msgs = pull_messages("ground", limit=10, mark_read=False)
    assert len(msgs) == 2
    assert all(m["recipient"] == "ground" for m in msgs)


def test_pull_messages_marks_read():
    from core.agent_bus import post_message, pull_messages
    post_message("satellite", "ground", "flag", {"note": "x"})
    # First pull
    msgs = pull_messages("ground", mark_read=True)
    assert len(msgs) == 1
    # Second pull should be empty
    msgs2 = pull_messages("ground", mark_read=True)
    assert len(msgs2) == 0


def test_pull_messages_broadcast_received_by_all():
    from core.agent_bus import post_message, pull_messages
    post_message("ground", "broadcast", "status", {"note": "broadcast msg"})
    # Both ground and satellite can read broadcast
    for recipient in ("ground", "satellite"):
        msgs = pull_messages(recipient, mark_read=False)
        assert any(m["msg_type"] == "status" for m in msgs), f"{recipient} should see broadcast"


def test_pull_messages_respects_limit():
    from core.agent_bus import post_message, pull_messages
    for i in range(10):
        post_message("satellite", "ground", "flag", {"i": i})
    msgs = pull_messages("ground", limit=3, mark_read=False)
    assert len(msgs) == 3


def test_message_payload_round_trips():
    from core.agent_bus import post_message, pull_messages
    payload = {"change_score": 0.876, "reason_codes": ["ndvi_drop", "nir_drop"], "nested": {"k": 1}}
    post_message("satellite", "ground", "flag", payload, cell_id="hex1")
    msgs = pull_messages("ground", mark_read=False)
    assert msgs[0]["payload"] == payload
    assert msgs[0]["cell_id"] == "hex1"


# ---------------------------------------------------------------------------
# get_recent_dialogue
# ---------------------------------------------------------------------------

def test_get_recent_dialogue_returns_chronological():
    from core.agent_bus import post_message, get_recent_dialogue
    post_message("satellite", "ground", "flag", {"note": "first"})
    post_message("ground", "satellite", "confirmation", {"note": "second"})
    history = get_recent_dialogue(limit=10)
    assert len(history) == 2
    assert history[0]["payload"]["note"] == "first"
    assert history[1]["payload"]["note"] == "second"


def test_get_recent_dialogue_limit():
    from core.agent_bus import post_message, get_recent_dialogue
    for i in range(20):
        post_message("satellite", "ground", "flag", {"i": i})
    history = get_recent_dialogue(limit=5)
    assert len(history) == 5


# ---------------------------------------------------------------------------
# get_bus_stats
# ---------------------------------------------------------------------------

def test_get_bus_stats_counts():
    from core.agent_bus import post_message, pull_messages, get_bus_stats
    post_message("satellite", "ground", "flag", {})
    post_message("satellite", "ground", "flag", {})
    post_message("ground", "satellite", "confirmation", {})
    # Mark one as read
    pull_messages("ground", limit=1, mark_read=True)

    stats = get_bus_stats()
    assert stats["total_messages"] == 3
    assert stats["from_satellite"] == 2
    assert stats["from_ground"] == 1
    assert stats["unread_messages"] == 2  # 1 sat read, 1 sat + 1 gnd still unread


# ---------------------------------------------------------------------------
# Map pin CRUD
# ---------------------------------------------------------------------------

def test_upsert_pin_creates_new():
    from core.agent_bus import upsert_pin, list_pins
    pin_id = upsert_pin("satellite", 1.23, 4.56, label="SAT pin", cell_id="abc")
    assert isinstance(pin_id, int)
    pins = list_pins()
    assert len(pins) == 1
    assert pins[0]["pin_type"] == "satellite"
    assert pins[0]["lat"] == pytest.approx(1.23)
    assert pins[0]["lng"] == pytest.approx(4.56)
    assert pins[0]["label"] == "SAT pin"


def test_upsert_pin_updates_existing_same_type_cell():
    from core.agent_bus import upsert_pin, list_pins
    upsert_pin("ground", 1.0, 2.0, label="first", cell_id="cell99")
    upsert_pin("ground", 3.0, 4.0, label="second", cell_id="cell99")
    pins = list_pins()
    assert len(pins) == 1  # updated in-place, not duplicated
    assert pins[0]["label"] == "second"
    assert pins[0]["lat"] == pytest.approx(3.0)


def test_upsert_pin_no_cell_id_always_inserts():
    from core.agent_bus import upsert_pin, list_pins
    upsert_pin("operator", 1.0, 2.0, label="op1")
    upsert_pin("operator", 3.0, 4.0, label="op2")
    # Without cell_id, each call is a fresh insert
    assert len(list_pins()) == 2


def test_delete_pin_removes_record():
    from core.agent_bus import upsert_pin, delete_pin, list_pins
    pin_id = upsert_pin("operator", 0.0, 0.0, label="to delete")
    assert delete_pin(pin_id) is True
    assert list_pins() == []


def test_delete_pin_missing_returns_false():
    from core.agent_bus import delete_pin
    assert delete_pin(99999) is False


def test_clear_pins_by_type():
    from core.agent_bus import upsert_pin, clear_pins_by_type, list_pins
    upsert_pin("satellite", 1.0, 1.0, label="s1", cell_id="c1")
    upsert_pin("satellite", 2.0, 2.0, label="s2", cell_id="c2")
    upsert_pin("operator", 3.0, 3.0, label="op")
    removed = clear_pins_by_type("satellite")
    assert removed == 2
    pins = list_pins()
    assert len(pins) == 1
    assert pins[0]["pin_type"] == "operator"


def test_pin_severity_stored():
    from core.agent_bus import upsert_pin, list_pins
    upsert_pin("ground", 0.0, 0.0, label="crit", severity="critical", cell_id="xcell")
    pins = list_pins()
    assert pins[0]["severity"] == "critical"


def test_pin_note_defaults_empty_string():
    from core.agent_bus import upsert_pin, list_pins
    upsert_pin("operator", 0.0, 0.0, label="no note")
    pins = list_pins()
    assert pins[0]["note"] == ""
