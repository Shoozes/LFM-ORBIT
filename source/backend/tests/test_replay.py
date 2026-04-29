import json

from fastapi.responses import JSONResponse

from api.main import mission_current, mission_stop, replay_catalog, replay_load, replay_rescan
from core.agent_bus import get_recent_dialogue, get_recent_messages, list_pins
from core.gallery import list_gallery
from core.metrics import read_metrics_summary
from core.queue import get_recent_alerts
from core.replay_snapshot import SNAPSHOT_FORMAT, export_replay_snapshot, import_replay_snapshot
from core.runtime_state import reset_runtime_state

EXPECTED_REPLAY_IDS = {
    "rondonia_frontier_judge",
    "manchar_flood_replay",
    "atacama_mining_replay",
    "singapore_maritime_replay",
    "georgia_wildfire_replay",
    "delhi_urban_replay",
    "greenland_ice_snow_extent_replay",
}

MULTISPECTRAL_REPLAY_IDS = {"greenland_ice_snow_extent_replay"}
METADATA_ONLY_REPLAY_IDS = {"greenland_ice_snow_extent_replay"}


def _json_response_payload(response: JSONResponse) -> dict:
    return json.loads(response.body.decode("utf-8"))


def _reset_runtime_state() -> None:
    reset_runtime_state()


def test_replay_catalog_lists_seeded_judge_pack(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()

    payload = replay_catalog()

    assert "replays" in payload
    replay = next(item for item in payload["replays"] if item["replay_id"] == "rondonia_frontier_judge")
    assert replay["title"] == "Rondonia Frontier Judge Replay"
    assert replay["primary_cell_id"] == "sq_-10.0_-63.0"
    assert replay["alert_count"] == 4

    replay_ids = {item["replay_id"] for item in payload["replays"]}
    assert EXPECTED_REPLAY_IDS.issubset(replay_ids)
    assert any(item["source_kind"] == "seeded_cache" for item in payload["replays"])
    assert next(item for item in payload["replays"] if item["replay_id"] == "greenland_ice_snow_extent_replay")["use_case_id"] == "ice_snow_extent"
    assert "seeded_cache_sh_cc0e95b7" not in replay_ids


def test_replay_load_seeds_runtime_surfaces(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()

    payload = replay_load("rondonia_frontier_judge")

    assert isinstance(payload, dict)
    assert payload["replay_id"] == "rondonia_frontier_judge"
    assert payload["primary_cell_id"] == "sq_-10.0_-63.0"
    assert payload["alerts_loaded"] == 4
    assert payload["mission"]["mission_mode"] == "replay"
    assert payload["mission"]["summary"]

    current = mission_current()
    assert current["mission"] is not None
    assert current["mission"]["mission_mode"] == "replay"
    assert current["mission"]["replay_id"] == "rondonia_frontier_judge"

    recent_alerts = get_recent_alerts(limit=10)["alerts"]
    assert len(recent_alerts) == 4
    assert all(alert["downlinked"] is True for alert in recent_alerts)
    assert all(alert["observation_source"] == "seeded_sentinelhub_replay" for alert in recent_alerts)

    gallery = list_gallery(limit=10)
    assert len(gallery) == 4
    assert all(item["has_timelapse"] == 1 for item in gallery)
    assert all(item["timelapse_source"] == "replay" for item in gallery)
    assert all(item["context_thumb_source"] == "seeded_cache" for item in gallery)

    metrics = read_metrics_summary()
    assert metrics["region_id"] == "replay"
    assert metrics["runtime_truth_mode"] == "replay"
    assert metrics["imagery_origin"] == "cached_api"
    assert metrics["scoring_basis"] == "visual_only"
    assert metrics["total_cells_scanned"] == 9
    assert metrics["total_alerts_emitted"] == 4

    pins = list_pins()
    assert len(pins) == 8

    dialogue = get_recent_dialogue(limit=20)
    assert any(msg["msg_type"] == "flag" and msg["cell_id"] == "sq_-10.0_-63.0" for msg in dialogue)
    assert any(msg["msg_type"] == "confirmation" and msg["cell_id"] == "sq_-10.0_-63.0" for msg in dialogue)

    flag_messages = get_recent_messages(msg_type="flag", limit=10)
    confirmation_messages = get_recent_messages(msg_type="confirmation", limit=10)
    assert flag_messages
    assert confirmation_messages
    assert all(msg["read"] is True for msg in flag_messages)
    assert all(msg["read"] is True for msg in confirmation_messages)


def test_each_bundled_replay_loads_runtime_surfaces(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()

    catalog = replay_catalog()["replays"]
    assert catalog

    for replay in catalog:
        payload = replay_load(replay["replay_id"])
        expected_scoring_basis = (
            "multispectral_bands" if replay["replay_id"] in MULTISPECTRAL_REPLAY_IDS else "visual_only"
        )
        expected_observation_source = (
            "seeded_sentinelhub_multispectral_replay"
            if replay["replay_id"] in MULTISPECTRAL_REPLAY_IDS
            else "seeded_sentinelhub_replay"
        )
        expected_has_timelapse = replay["replay_id"] not in METADATA_ONLY_REPLAY_IDS

        assert isinstance(payload, dict)
        assert payload["replay_id"] == replay["replay_id"]
        assert payload["alerts_loaded"] == replay["alert_count"]
        assert payload["mission"]["mission_mode"] == "replay"
        assert payload["mission"]["replay_id"] == replay["replay_id"]

        recent_alerts = get_recent_alerts(limit=20)["alerts"]
        assert len(recent_alerts) == replay["alert_count"]
        assert all(alert["downlinked"] is True for alert in recent_alerts)
        assert all(alert["observation_source"] == expected_observation_source for alert in recent_alerts)
        assert all(alert["scoring_basis"] == expected_scoring_basis for alert in recent_alerts)

        gallery = list_gallery(limit=20)
        assert len(gallery) == replay["alert_count"]
        if expected_has_timelapse:
            assert all(item["has_timelapse"] == 1 for item in gallery)
            assert all(item["timelapse_source"] == "replay" for item in gallery)
        else:
            assert all(item["has_timelapse"] == 0 for item in gallery)

        metrics = read_metrics_summary()
        assert metrics["region_id"] == "replay"
        assert metrics["runtime_truth_mode"] == "replay"
        assert metrics["imagery_origin"] == "cached_api"
        assert metrics["scoring_basis"] == expected_scoring_basis
        assert metrics["total_cells_scanned"] == replay["cells_scanned"]
        assert metrics["total_alerts_emitted"] == replay["alert_count"]

        pins = list_pins()
        assert len(pins) == replay["alert_count"] * 2

        dialogue = get_recent_dialogue(limit=20)
        assert any(msg["msg_type"] == "flag" for msg in dialogue)
        assert any(msg["msg_type"] == "confirmation" for msg in dialogue)


def test_replay_stop_restores_live_mode_note(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()

    replay_load("rondonia_frontier_judge")

    payload = mission_stop()

    assert payload == {"status": "stopped"}
    assert mission_current()["mission"] is None

    dialogue = get_recent_dialogue(limit=5)
    assert dialogue[-1]["msg_type"] == "mission"
    assert "exited replay" in dialogue[-1]["payload"]["note"].lower()


def test_replay_load_returns_400_for_unknown_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()

    response = replay_load("missing_replay")

    assert isinstance(response, JSONResponse)
    assert response.status_code == 400
    payload = _json_response_payload(response)
    assert "Unknown replay_id" in payload["error"]


def test_seeded_cache_replay_loads_and_rescans(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()

    seeded = next(item for item in replay_catalog()["replays"] if item["source_kind"] == "seeded_cache")
    replay_payload = replay_load(seeded["replay_id"])

    assert isinstance(replay_payload, dict)
    assert replay_payload["replay_id"] == seeded["replay_id"]
    assert replay_payload["mission"]["mission_mode"] == "replay"
    assert replay_payload["alerts_loaded"] == 1
    assert list_gallery(limit=5)[0]["timelapse_source"] == "replay"

    rescan_payload = replay_rescan(seeded["replay_id"])

    assert isinstance(rescan_payload, dict)
    assert rescan_payload["source_replay_id"] == seeded["replay_id"]
    assert rescan_payload["mission"]["mission_mode"] == "live"
    assert rescan_payload["mission"]["bbox"] == seeded["bbox"]
    assert "current runtime/model stack" in rescan_payload["mission"]["summary"]
    assert get_recent_alerts(limit=5)["alerts"] == []


def test_replay_snapshot_export_import_round_trips_runtime_surfaces(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()

    replay_load("rondonia_frontier_judge")
    snapshot = export_replay_snapshot(limit=50)

    assert snapshot["format"] == SNAPSHOT_FORMAT
    assert len(snapshot["alerts"]) == 4
    assert len(snapshot["gallery"]) == 4
    assert snapshot["active_mission"]["mission_mode"] == "replay"

    _reset_runtime_state()
    payload = import_replay_snapshot(snapshot)

    assert payload["status"] == "imported"
    assert payload["alerts_imported"] == 4
    assert payload["gallery_imported"] == 4
    assert payload["pins_imported"] == 8
    assert payload["messages_imported"] >= 2
    assert len(get_recent_alerts(limit=10)["alerts"]) == 4
    assert len(list_gallery(limit=10)) == 4
    assert read_metrics_summary()["runtime_truth_mode"] == "replay"
