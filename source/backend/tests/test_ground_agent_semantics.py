from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from core.ground_agent_semantics import (
    load_ground_agent_semantic_examples,
    match_ground_agent_semantics,
)


client = TestClient(app)


def test_ground_agent_tool_semantics_jsonl_is_small_local_eval_fixture():
    examples = load_ground_agent_semantic_examples()

    assert 5 <= len(examples) <= 50
    ids = [row["id"] for row in examples]
    assert len(ids) == len(set(ids))
    for row in examples:
        assert set(row) >= {"id", "utterance", "intent", "tool", "arguments", "expected_proposal", "notes"}
        assert isinstance(row["utterance"], str) and row["utterance"].strip()
        assert row["tool"] in {"resolve_location", "load_replay", "start_mission_pack", "set_link_state"}
        expected = row["expected_proposal"]
        assert isinstance(expected, dict)
        assert "requires_confirmation" in expected
        assert "risk_level" in expected


def test_private_ground_agent_tool_semantics_jsonl_is_ignored():
    repo_root = Path(__file__).resolve().parents[3]
    ignore_text = (repo_root / ".gitignore").read_text(encoding="utf-8")

    assert "source/backend/data/*.local.jsonl" in ignore_text


def test_match_ground_agent_semantics_classifies_product_tool_routes():
    expectations = {
        "take me to the Bronx, ny": ("navigate_map_location", "resolve_location"),
        "show me the Suez canal": ("navigate_map_location", "resolve_location"),
        "scan the bronx for changes": ("prepare_location_mission", "resolve_location"),
        "load the manchar flood replay": ("load_replay", "load_replay"),
        "run the maritime mission pack": ("start_mission_pack", "start_mission_pack"),
        "restore the downlink": ("set_link_state", "set_link_state"),
        "take me to georgia": ("ambiguous_location", "resolve_location"),
        "show me one of the biggest garbage patches in the ocean and make a timelapse for every month in the last 10 years to current": ("prepare_location_mission", "resolve_location"),
        "check Lake Okeechobee for algae blooms": ("prepare_location_mission", "resolve_location"),
    }

    for utterance, (intent, tool) in expectations.items():
        match = match_ground_agent_semantics(utterance)
        assert match is not None, utterance
        assert match["intent"] == intent
        assert match["tool"] == tool


def test_ground_agent_semantics_examples_match_runtime_proposal_kinds(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    from core.agent_bus import init_bus
    from core.mission import init_missions

    init_bus(reset=True)
    init_missions(reset=True)

    expected_by_id = {
        "loc_nav_001": "navigate_map_location",
        "loc_nav_002": "navigate_map_location",
        "loc_nav_003": "navigate_map_location",
        "loc_nav_004": "navigate_map_location",
        "loc_nav_005": "navigate_map_location",
        "loc_nav_006": "start_custom_mission",
        "replay_001": "load_replay",
        "mission_001": "start_mission_pack",
        "mission_002": "start_custom_mission",
        "hab_001": "start_custom_mission",
        "link_001": "set_link_state",
    }

    for row in load_ground_agent_semantic_examples():
        if row["id"] == "ambiguous_001":
            response = client.post("/api/agent/chat", json={"messages": [{"role": "user", "content": row["utterance"]}]})
            assert response.status_code == 200
            payload = response.json()
            assert payload.get("proposals", []) == []
            assert "ambiguous" in payload["reply"].lower()
            continue

        response = client.post("/api/agent/chat", json={"messages": [{"role": "user", "content": row["utterance"]}]})

        assert response.status_code == 200, row["id"]
        payload = response.json()
        assert payload.get("proposals"), row["id"]
        proposal = payload["proposals"][0]
        assert proposal["kind"] == expected_by_id[row["id"]]
        assert proposal["risk_level"] == row["expected_proposal"]["risk_level"]
        assert proposal["details"].get("request") == row["utterance"]

        if proposal["kind"] == "navigate_map_location":
            assert len(proposal["details"]["preview_tiles"]) == 9
            assert proposal["details"]["bbox"]
            assert proposal["details"]["center"]
            assert proposal["details"]["confidence"] >= 0.55
