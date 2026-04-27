import json

from fastapi.responses import JSONResponse

from api.main import mission_current, mission_stop, replay_catalog, replay_load
from core.agent_bus import get_recent_dialogue, get_recent_messages, list_pins
from core.gallery import list_gallery
from core.metrics import read_metrics_summary
from core.queue import get_recent_alerts
from core.runtime_state import reset_runtime_state

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
    assert all(item["timelapse_source"] == "seeded_replay" for item in gallery)
    assert all(item["context_thumb_source"] == "seeded_cache" for item in gallery)

    metrics = read_metrics_summary()
    assert metrics["region_id"] == "seeded_replay"
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
    assert "exited seeded replay" in dialogue[-1]["payload"]["note"].lower()


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
