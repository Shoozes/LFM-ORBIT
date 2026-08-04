"""
Tests for core/satellite_agent.py — pure builder functions.
The async `run_satellite_agent` loop is not tested here (it requires a running
event loop and DB); only the message-builder helpers are covered.
"""
import pytest


def test_build_flag_message_structure():
    from core.satellite_agent import _build_flag_message
    score = {
        "change_score": 0.856,
        "confidence": 0.921,
        "reason_codes": ["ndvi_drop", "nir_drop"],
        "observation_source": "semi_real_loader_v1",
        "before_window": {"ndvi": 0.7},
        "after_window": {"ndvi": 0.4},
    }
    payload = _build_flag_message("cell_abc123", score)

    assert payload["change_score"] == pytest.approx(0.856, abs=1e-4)
    assert payload["confidence"] == pytest.approx(0.921, abs=1e-4)
    assert "ndvi_drop" in payload["reason_codes"]
    assert payload["observation_source"] == "semi_real_loader_v1"
    assert payload["before_window"] == {"ndvi": 0.7}
    assert payload["after_window"] == {"ndvi": 0.4}
    assert "event_id" in payload
    assert payload["event_id"].startswith("sat_")
    assert "note" in payload
    assert payload["review_boundary"] == "candidate_evidence_packet"
    assert "compact candidate evidence packet" in payload["note"]


def test_build_flag_message_event_id_unique():
    from core.satellite_agent import _build_flag_message
    score = {"change_score": 0.7, "confidence": 0.8, "reason_codes": []}
    p1 = _build_flag_message("cA", score)
    p2 = _build_flag_message("cB", score)
    assert p1["event_id"] != p2["event_id"]


def test_build_flag_message_with_mission_id():
    from core.satellite_agent import _build_flag_message
    score = {"change_score": 0.7, "confidence": 0.8, "reason_codes": []}
    payload = _build_flag_message("cellX", score, mission_id=5)
    assert payload["mission_id"] == 5


def test_build_flag_message_without_mission_id():
    from core.satellite_agent import _build_flag_message
    score = {"change_score": 0.7, "confidence": 0.8, "reason_codes": []}
    payload = _build_flag_message("cellY", score, mission_id=None)
    assert "mission_id" not in payload


def test_build_flag_message_scores_rounded_to_4dp():
    from core.satellite_agent import _build_flag_message
    score = {"change_score": 0.123456789, "confidence": 0.987654321, "reason_codes": []}
    payload = _build_flag_message("cellZ", score)
    # Should be 4 decimal places
    assert payload["change_score"] == pytest.approx(0.1235, abs=1e-4)
    assert payload["confidence"] == pytest.approx(0.9877, abs=1e-4)


def test_build_flag_message_with_llm_result():
    from core.satellite_agent import _build_flag_message
    score = {"change_score": 0.700, "confidence": 0.900, "reason_codes": []}

    llm_res = {
        "thinking": "Clear tree canopy removal observed mathematically.",
        "response": "Mathematical deforestation identified.",
        "tool_calls": []
    }

    payload = _build_flag_message("cellZ", score, llm_result=llm_res)
    assert payload["thinking"] == "Clear tree canopy removal observed mathematically."
    assert payload["response"] == "Mathematical deforestation identified."
    assert payload["tool_calls"] == []


def test_build_flag_message_default_observation_source():
    from core.satellite_agent import _build_flag_message
    score = {"change_score": 0.5, "confidence": 0.5, "reason_codes": []}
    # No observation_source in score dict
    payload = _build_flag_message("cellD", score)
    assert payload["observation_source"] == "semi_real_loader_v1"


def test_build_flag_message_empty_windows_default():
    from core.satellite_agent import _build_flag_message
    score = {"change_score": 0.5, "confidence": 0.5, "reason_codes": []}
    payload = _build_flag_message("cellE", score)
    assert payload["before_window"] == {}
    assert payload["after_window"] == {}


def test_build_heartbeat_message_structure():
    from core.satellite_agent import _build_heartbeat_message
    hb = _build_heartbeat_message(cells_scanned=45, total_cells=127, cycle=3)
    assert hb["cells_scanned"] == 45
    assert hb["total_cells"] == 127
    assert hb["cycle"] == 3
    assert hb["status"] == "scanning"
    assert "45/127" in hb["note"]
    assert "cycle 3" in hb["note"].lower()


def test_build_heartbeat_message_zero_cells():
    from core.satellite_agent import _build_heartbeat_message
    hb = _build_heartbeat_message(cells_scanned=0, total_cells=100, cycle=1)
    assert hb["cells_scanned"] == 0
    assert "0/100" in hb["note"]


def test_scan_features_for_mission_uses_mission_bbox():
    from core.grid import cell_to_latlng
    from core.satellite_agent import _scan_features_for_mission

    bbox = [-83.2, 29.0, -81.3, 30.7]
    features = _scan_features_for_mission({"bbox": bbox})

    assert features
    assert len(features) > 100
    sample_ids = [str(feature["id"]) for feature in features[:10]]
    assert all(cell_id.startswith("sq_") for cell_id in sample_ids)
    assert any(29.0 <= cell_to_latlng(str(feature["id"]))[0] <= 30.7 for feature in features)
    assert all(-84.0 < cell_to_latlng(str(feature["id"]))[1] < -80.0 for feature in features[:20])


def test_seeded_cache_promotion_is_deforestation_only():
    from core.satellite_agent import _seeded_cache_can_promote

    assert _seeded_cache_can_promote({"use_case_id": "deforestation", "target_pack_id": "deforestation"})
    assert not _seeded_cache_can_promote({"use_case_id": "wildfire", "target_pack_id": "fireline"})
    assert not _seeded_cache_can_promote(None)
