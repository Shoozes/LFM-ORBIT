"""
Tests for core/mission.py — mission lifecycle and persistence.
Uses a temp SQLite DB via the AGENT_BUS_PATH env var (same DB as agent_bus).
"""
import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "test_mission.sqlite"))
    from core import agent_bus
    agent_bus.init_bus(reset=True)
    yield


# ---------------------------------------------------------------------------
# start_mission
# ---------------------------------------------------------------------------

def test_start_mission_returns_dict():
    from core.mission import start_mission
    m = start_mission("Scan Amazonas sector")
    assert m["id"] >= 1
    assert m["task_text"] == "Scan Amazonas sector"
    assert m["status"] == "active"
    assert m["bbox"] is None


def test_start_mission_with_bbox():
    from core.mission import start_mission
    bbox = [-62.0, -4.0, -60.0, -2.0]
    m = start_mission("Focus area", bbox=bbox)
    assert m["bbox"] == bbox


def test_start_mission_rejects_empty_task_text():
    from core.mission import start_mission
    with pytest.raises(ValueError, match="task_text"):
        start_mission("   ")


def test_start_mission_rejects_invalid_bbox():
    from core.mission import start_mission
    with pytest.raises(ValueError, match="west < east"):
        start_mission("Bad bounds", bbox=[-60.0, -4.0, -62.0, -2.0])


def test_start_mission_rejects_invalid_mode():
    from core.mission import start_mission
    with pytest.raises(ValueError, match="mission_mode"):
        start_mission("Bad mode", mission_mode="demo")


def test_start_mission_with_dates():
    from core.mission import start_mission
    m = start_mission("Temporal scan", start_date="2024-01-01", end_date="2024-06-30")
    assert m["start_date"] == "2024-01-01"
    assert m["end_date"] == "2024-06-30"


def test_start_mission_auto_classifies_temporal_use_case():
    from core.mission import start_mission
    m = start_mission("Scan maritime vessel wakes near the harbor for AIS mismatch")
    assert m["use_case_id"] == "maritime_activity"
    assert m["use_case_confidence"] > 0
    assert m["use_case_decision"]["target_task"] == "maritime_temporal_monitoring"


def test_start_mission_deactivates_previous():
    from core.mission import start_mission, get_mission
    m1 = start_mission("First mission")
    m2 = start_mission("Second mission")
    # First should now be complete
    updated_m1 = get_mission(m1["id"])
    assert updated_m1["status"] == "complete"
    assert updated_m1["completed_at"] is not None
    assert m2["status"] == "active"


# ---------------------------------------------------------------------------
# get_active_mission
# ---------------------------------------------------------------------------

def test_get_active_mission_returns_none_when_empty():
    from core.mission import get_active_mission
    assert get_active_mission() is None


def test_get_active_mission_returns_current():
    from core.mission import start_mission, get_active_mission
    start_mission("Active one", bbox=[-60.0, -3.0, -59.0, -2.0])
    active = get_active_mission()
    assert active is not None
    assert active["status"] == "active"
    assert active["task_text"] == "Active one"


def test_get_active_mission_none_after_stop():
    from core.mission import start_mission, stop_mission, get_active_mission
    start_mission("Will be stopped")
    stop_mission()
    assert get_active_mission() is None


# ---------------------------------------------------------------------------
# stop_mission
# ---------------------------------------------------------------------------

def test_stop_mission_marks_complete():
    from core.mission import start_mission, stop_mission, list_missions
    start_mission("To stop")
    stop_mission()
    missions = list_missions()
    assert missions[0]["status"] == "complete"
    assert missions[0]["completed_at"] is not None


def test_stop_mission_no_op_when_none_active():
    from core.mission import stop_mission
    # Should not raise
    stop_mission()


# ---------------------------------------------------------------------------
# get_mission / list_missions
# ---------------------------------------------------------------------------

def test_get_mission_returns_none_for_missing():
    from core.mission import get_mission
    assert get_mission(99999) is None


def test_list_missions_returns_newest_first():
    from core.mission import start_mission, list_missions
    start_mission("First")
    start_mission("Second")
    start_mission("Third")
    missions = list_missions()
    assert missions[0]["task_text"] == "Third"
    assert missions[-1]["task_text"] == "First"


def test_list_missions_limit():
    from core.mission import start_mission, list_missions
    for i in range(5):
        start_mission(f"Mission {i}")
    assert len(list_missions(limit=3)) == 3


# ---------------------------------------------------------------------------
# update_mission_progress
# ---------------------------------------------------------------------------

def test_update_mission_progress():
    from core.mission import start_mission, update_mission_progress, get_mission
    m = start_mission("Progress test")
    update_mission_progress(m["id"], cells_scanned=42, flags_found=3)
    updated = get_mission(m["id"])
    assert updated["cells_scanned"] == 42
    assert updated["flags_found"] == 3


# ---------------------------------------------------------------------------
# bbox round-trip
# ---------------------------------------------------------------------------

def test_bbox_serializes_and_deserializes_correctly():
    from core.mission import start_mission, get_mission
    bbox = [-62.5, -3.9, -60.1, -1.5]
    m = start_mission("Bbox test", bbox=bbox)
    loaded = get_mission(m["id"])
    assert loaded["bbox"] == pytest.approx(bbox)
