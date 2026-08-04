import json

import pytest

from fastapi.responses import JSONResponse

from api.main import mission_current, mission_stop, replay_catalog, replay_load, replay_rescan
from core.agent_bus import get_recent_dialogue, get_recent_messages, list_pins
from core.gallery import list_gallery
from core.metrics import read_metrics_summary
from core.object_targets import get_target_pack
from core.queue import get_recent_alerts
from core.replay_snapshot import SNAPSHOT_FORMAT, _coerce_bool, export_replay_snapshot, import_replay_snapshot


def test_replay_snapshot_bool_coercion_handles_text_values():
    assert _coerce_bool("true") is True
    assert _coerce_bool("false") is False
    assert _coerce_bool("0") is False
    assert _coerce_bool("unexpected") is False


def test_replay_snapshot_rejects_malformed_rows_before_reset(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()
    replay_load("rondonia_frontier_showcase")
    before = get_recent_alerts(limit=20)["alerts"]

    malformed = export_replay_snapshot(limit=50)
    malformed["alerts"][0]["payload_bytes"] = "not-an-integer"

    with pytest.raises(ValueError, match="payload_bytes"):
        import_replay_snapshot(malformed)

    assert len(get_recent_alerts(limit=20)["alerts"]) == len(before)


def test_replay_snapshot_preserves_confirmation_policy(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()

    from core.mission import get_active_mission, start_mission

    start_mission("Single acquisition snapshot", confirmation_policy="single_acquisition")
    snapshot = export_replay_snapshot(limit=20)

    import_replay_snapshot(snapshot)

    restored = get_active_mission()
    assert restored is not None
    assert restored["confirmation_policy"] == "single_acquisition"
from core.runtime_state import reset_runtime_state

EXPECTED_REPLAY_IDS = {
    "rondonia_frontier_showcase",
    "manchar_flood_replay",
    "atacama_mining_replay",
    "singapore_maritime_replay",
    "georgia_wildfire_replay",
    "pineland_road_wildfire_replay",
    "spain_larouco_wildfire_replay",
    "florida_sr26_wildfire_replay",
    "delhi_urban_replay",
    "greenland_ice_snow_extent_replay",
    "southeast_fireline_object_replay",
    "camp_shelter_count_replay",
    "port_supply_chain_replay",
    "plastic_pollution_candidate_replay",
}

MULTISPECTRAL_REPLAY_IDS = {"greenland_ice_snow_extent_replay"}
PROXY_REPLAY_IDS = {"rondonia_frontier_showcase"}
BURN_SCAR_REPLAY_IDS = {
    "florida_sr26_wildfire_replay",
    "georgia_wildfire_replay",
    "pineland_road_wildfire_replay",
    "spain_larouco_wildfire_replay",
}
METADATA_ONLY_REPLAY_IDS = {"greenland_ice_snow_extent_replay"}
OBJECT_FIXTURE_REPLAY_IDS = {
    "southeast_fireline_object_replay",
    "camp_shelter_count_replay",
    "port_supply_chain_replay",
    "plastic_pollution_candidate_replay",
}


def _json_response_payload(response: JSONResponse) -> dict:
    return json.loads(response.body.decode("utf-8"))


def _reset_runtime_state() -> None:
    reset_runtime_state()


def test_replay_catalog_lists_seeded_showcase_pack(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()

    payload = replay_catalog()

    assert "replays" in payload
    replay = next(item for item in payload["replays"] if item["replay_id"] == "rondonia_frontier_showcase")
    assert replay["title"] == "Rondonia Frontier Showcase Replay"
    assert replay["primary_cell_id"] == "sq_-10.0_-63.0"
    assert replay["alert_count"] == 4

    replay_ids = {item["replay_id"] for item in payload["replays"]}
    assert EXPECTED_REPLAY_IDS.issubset(replay_ids)
    assert any(item["source_kind"] == "seeded_cache" for item in payload["replays"])
    assert next(item for item in payload["replays"] if item["replay_id"] == "greenland_ice_snow_extent_replay")["use_case_id"] == "ice_snow_extent"
    assert "seeded_cache_sh_cc0e95b7" not in replay_ids


def test_replay_rescan_returns_additive_prior_current_comparison(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()

    payload = replay_rescan("atacama_mining_replay")
    comparison = payload["comparison"]

    assert comparison["mode"] == "additive"
    assert comparison["source_replay_id"] == "atacama_mining_replay"
    assert comparison["current_scoring_basis"] == "cached_rescan_current_model"
    assert comparison["prior_alert_count"] == comparison["current_alert_count"] == 1
    assert comparison["changed_count"] + comparison["unchanged_count"] == 1
    assert {row["status"] for row in comparison["rows"]} <= {"changed", "unchanged"}
    assert all(row["cell_id"] for row in comparison["rows"])
    assert "Original replay proof remains unchanged" in comparison["note"]


def test_curated_replays_expose_use_case_metadata():
    payload = replay_catalog()
    curated = [item for item in payload["replays"] if item["source_kind"] == "curated_replay"]

    assert curated
    assert [item["replay_id"] for item in curated if not item.get("use_case_id")] == []
    assert next(item for item in curated if item["replay_id"] == "atacama_mining_replay")["target_pack_id"] == "critical_minerals"


def test_replay_load_seeds_runtime_surfaces(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()

    payload = replay_load("rondonia_frontier_showcase")

    assert isinstance(payload, dict)
    assert payload["replay_id"] == "rondonia_frontier_showcase"
    assert payload["primary_cell_id"] == "sq_-10.0_-63.0"
    assert payload["alerts_loaded"] == 4
    assert payload["mission"]["mission_mode"] == "replay"
    assert payload["mission"]["summary"]
    assert payload["mission"]["target_pack_id"] == "deforestation"
    assert {target["label"] for target in payload["mission"]["object_targets"]} >= {
        "clearing candidate",
        "road expansion",
        "canopy-loss boundary",
    }

    current = mission_current()
    assert current["mission"] is not None
    assert current["mission"]["mission_mode"] == "replay"
    assert current["mission"]["replay_id"] == "rondonia_frontier_showcase"

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
    assert metrics["scoring_basis"] == "proxy_bands"
    assert metrics["total_cells_scanned"] == 9
    assert metrics["total_alerts_emitted"] == 4

    center_alert = next(alert for alert in recent_alerts if alert["cell_id"] == "sq_-10.0_-63.0")
    assert center_alert["detection_summary"]["target_pack_id"] == "deforestation"
    assert center_alert["detection_summary"]["counts_by_label"]["clearing candidate"] == 2
    assert center_alert["object_deltas"][0]["label"] == "clearing candidate"

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


def test_florida_wildfire_replay_loads_real_seeded_timelapse(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()

    payload = replay_load("florida_sr26_wildfire_replay")

    assert payload["mission"]["use_case_id"] == "wildfire"
    assert payload["mission"]["target_pack_id"] == "fireline"
    assert payload["primary_cell_id"] == "wildfire_florida_sr26_candidate"
    assert payload["alerts_loaded"] == 1

    recent_alerts = get_recent_alerts(limit=5)["alerts"]
    assert recent_alerts[0]["cell_id"] == "wildfire_florida_sr26_candidate"
    assert recent_alerts[0]["observation_source"] == "seeded_sentinelhub_replay"
    assert recent_alerts[0]["scoring_basis"] == "sentinelhub_burn_scar_composite"

    gallery = list_gallery(limit=5)
    assert len(gallery) == 1
    assert gallery[0]["has_timelapse"] == 1
    assert gallery[0]["timelapse_source"] == "replay"


def test_pineland_wildfire_replay_loads_smoke_cloud_review_seeded_timelapse(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()

    payload = replay_load("pineland_road_wildfire_replay")

    assert payload["mission"]["use_case_id"] == "wildfire"
    assert payload["mission"]["target_pack_id"] == "fireline"
    assert payload["primary_cell_id"] == "wildfire_pineland_road_candidate"
    assert payload["alerts_loaded"] == 1

    alert = get_recent_alerts(limit=5)["alerts"][0]
    assert alert["cell_id"] == "wildfire_pineland_road_candidate"
    assert alert["observation_source"] == "seeded_sentinelhub_replay"
    assert alert["scoring_basis"] == "sentinelhub_burn_scar_composite"
    assert alert["wildfire_assessment"]["target_action"] == "defer"
    assert "smoke_or_cloud_review" in alert["after_window"]["flags"]

    gallery = list_gallery(limit=5)
    assert len(gallery) == 1
    assert gallery[0]["has_timelapse"] == 1
    assert gallery[0]["timelapse_source"] == "replay"


def test_spain_larouco_wildfire_replay_loads_real_burn_scar_proof(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()

    payload = replay_load("spain_larouco_wildfire_replay")

    assert payload["mission"]["use_case_id"] == "wildfire"
    assert payload["mission"]["target_pack_id"] == "fireline"
    assert payload["primary_cell_id"] == "wildfire_spain_larouco_candidate"
    assert payload["alerts_loaded"] == 1

    alert = get_recent_alerts(limit=5)["alerts"][0]
    assert alert["cell_id"] == "wildfire_spain_larouco_candidate"
    assert alert["observation_source"] == "seeded_sentinelhub_replay"
    assert alert["scoring_basis"] == "sentinelhub_burn_scar_composite"
    assert alert["wildfire_assessment"]["target_action"] == "review"
    assert "dnbr_burn_support" in alert["wildfire_assessment"]["reason_codes"]
    assert "burn_scar_candidate" in alert["after_window"]["flags"]

    gallery = list_gallery(limit=5)
    assert len(gallery) == 1
    assert gallery[0]["has_timelapse"] == 1
    assert gallery[0]["timelapse_source"] == "replay"


def test_object_evidence_replay_loads_targets_and_detection_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()

    payload = replay_load("southeast_fireline_object_replay")

    assert payload["mission"]["target_pack_id"] == "fireline"
    assert {target["label"] for target in payload["mission"]["object_targets"]} >= {"dark smoke", "road obstruction"}

    alert = get_recent_alerts(limit=1)["alerts"][0]
    assert alert["detection_summary"]["target_pack_id"] == "fireline"
    assert alert["detection_summary"]["counts_by_label"]["dark smoke"] == 1
    assert alert["object_deltas"][0]["label"] == "dark smoke"


def test_object_evidence_replay_target_packs_and_top_boxes_are_consistent(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()

    for replay_id in sorted(OBJECT_FIXTURE_REPLAY_IDS):
        payload = replay_load(replay_id)
        mission = payload["mission"]
        pack_id = mission["target_pack_id"]
        pack = get_target_pack(pack_id)
        assert pack is not None
        assert {target["label"] for target in mission["object_targets"]} == {
            target["label"] for target in pack["targets"]
        }

        alert = get_recent_alerts(limit=1)["alerts"][0]
        summary = alert["detection_summary"]
        assert summary["target_pack_id"] == pack_id
        if summary["total_boxes"] <= 12:
            assert len(summary["top_boxes"]) == summary["total_boxes"]


def test_port_replay_matches_approved_docs_story_plate_bbox_and_labels(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()

    payload = replay_load("port_supply_chain_replay")

    assert payload["mission"]["bbox"] == [32.515, 29.9, 32.575, 29.955]
    assert payload["mission"]["target_pack_id"] == "port"
    assert {target["label"] for target in payload["mission"]["object_targets"]} == {
        "shipping container cluster",
        "container yard cluster",
        "docked-vessel group",
        "berth basin context",
    }
    alert = get_recent_alerts(limit=1)["alerts"][0]
    summary = alert["detection_summary"]
    assert summary["counts_by_label"] == {
        "shipping container cluster": 1,
        "container yard cluster": 1,
        "docked-vessel group": 1,
        "berth basin context": 1,
    }
    assert all(box["count_quality"] == "activity_region" for box in summary["top_boxes"])
    assert not any("channel vessel" in box["label"] for box in summary["top_boxes"])


def test_maritime_replay_uses_area_level_activity_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()

    payload = replay_load("singapore_maritime_replay")

    assert payload["mission"]["target_pack_id"] == "port"
    alert = get_recent_alerts(limit=1)["alerts"][0]
    summary = alert["detection_summary"]
    assert summary["counts_by_label"]["vessel queue area"] == 2
    assert summary["provenance"]["exact_object_count"] is False
    assert all(box["count_quality"] == "activity_region" for box in summary["top_boxes"])


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
        if replay["replay_id"] in PROXY_REPLAY_IDS:
            expected_scoring_basis = "proxy_bands"
        if replay["replay_id"] in BURN_SCAR_REPLAY_IDS:
            expected_scoring_basis = "sentinelhub_burn_scar_composite"
        expected_observation_source = (
            "seeded_sentinelhub_multispectral_replay"
            if replay["replay_id"] in MULTISPECTRAL_REPLAY_IDS
            else "replay_fixture"
            if replay["replay_id"] in OBJECT_FIXTURE_REPLAY_IDS
            else "seeded_sentinelhub_replay"
        )
        expected_has_timelapse = replay["replay_id"] not in METADATA_ONLY_REPLAY_IDS | OBJECT_FIXTURE_REPLAY_IDS

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

    replay_load("rondonia_frontier_showcase")

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
    assert rescan_payload["mission"]["mission_mode"] == "replay"
    assert rescan_payload["mission"]["replay_id"] == seeded["replay_id"]
    assert rescan_payload["mission"]["bbox"] == seeded["bbox"]
    assert "Same retained frames and evidence" in rescan_payload["mission"]["summary"]
    assert rescan_payload["primary_cell_id"] == seeded["primary_cell_id"]
    assert rescan_payload["alerts_loaded"] == 1
    assert rescan_payload["review_metadata"]["review_model_filename"].endswith(".gguf")
    assert rescan_payload["review_metadata"]["review_model_revision"]
    assert rescan_payload["review_metadata"]["reviewed_at"].endswith("Z")
    assert "model_path" not in rescan_payload["review_metadata"]
    rescanned_alerts = get_recent_alerts(limit=5)["alerts"]
    assert len(rescanned_alerts) == 1
    assert rescanned_alerts[0]["runtime_truth_mode"] == "replay"
    assert rescanned_alerts[0]["imagery_origin"] == "cached_api"
    assert rescanned_alerts[0]["scoring_basis"] == "cached_rescan_current_model"
    assert "cached_rescan_current_model" in rescanned_alerts[0]["reason_codes"]
    assert list_gallery(limit=5)[0]["timelapse_source"] == "replay"
    assert read_metrics_summary()["scoring_basis"] == "cached_rescan_current_model"
    assert read_metrics_summary()["flagged_examples"][0]["scoring_basis"] == "cached_rescan_current_model"
    assert "cached_rescan_current_model" in read_metrics_summary()["flagged_examples"][0]["reason_codes"]
    assert rescan_payload["analysis_results"][0]["model"]


def test_replay_snapshot_export_import_round_trips_runtime_surfaces(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    _reset_runtime_state()

    replay_load("rondonia_frontier_showcase")
    snapshot = export_replay_snapshot(limit=50)

    assert snapshot["format"] == SNAPSHOT_FORMAT
    assert len(snapshot["alerts"]) == 4
    assert len(snapshot["gallery"]) == 4
    assert snapshot["active_mission"]["mission_mode"] == "replay"

    snapshot["active_mission"]["target_pack_id"] = "fireline"
    snapshot["active_mission"]["object_targets"] = [
        {
            "label": "dark smoke",
            "prompt": "Find dark smoke",
            "class_key": "hazard",
            "enabled": True,
        }
    ]

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
    current = mission_current()["mission"]
    assert current["target_pack_id"] == "fireline"
    assert current["object_targets"][0]["label"] == "dark smoke"
