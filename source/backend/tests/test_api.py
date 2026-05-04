"""Tests for API endpoint responses.

These tests verify that all REST endpoints return expected data
and comply with the locked contract schemas.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import (
    _cors_allow_origins,
    _is_windows_transport_disconnect_noise,
    _require_local_request,
    _should_run_agent_pair_on_boot,
    app,
)
from core.depth_anything import clear_depth_anything_runtime_override

client = TestClient(app)


def test_agent_pair_boot_can_be_disabled_for_recorded_demos(monkeypatch):
    monkeypatch.setenv("RUN_AGENT_PAIR_ON_BOOT", "false")
    assert _should_run_agent_pair_on_boot() is False

    monkeypatch.setenv("RUN_AGENT_PAIR_ON_BOOT", "true")
    assert _should_run_agent_pair_on_boot() is True


def test_windows_transport_disconnect_filter_is_narrow():
    context = {
        "exception": ConnectionResetError("closed by browser"),
        "handle": "<Handle _ProactorBasePipeTransport._call_connection_lost(None)>",
    }
    assert _is_windows_transport_disconnect_noise(context) is True
    assert _is_windows_transport_disconnect_noise({"exception": RuntimeError("boom"), "handle": context["handle"]}) is False
    assert _is_windows_transport_disconnect_noise({"exception": ConnectionResetError("boom"), "handle": "other"}) is False


def test_cors_defaults_to_localhost_allowlist(monkeypatch):
    monkeypatch.delenv("ORBIT_CORS_ALLOW_ORIGINS", raising=False)

    origins = _cors_allow_origins()

    assert "*" not in origins
    assert "http://127.0.0.1:5173" in origins
    assert "http://localhost:5173" in origins


def test_watchlist_endpoints_start_mission_from_asset(tmp_path, monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "watchlist.sqlite"))

    listing = client.get("/api/watchlists")
    assert listing.status_code == 200
    assert any(item["watchlist_id"] == "southeast_fire_lifeline_watch" for item in listing.json()["watchlists"])

    detail = client.get("/api/watchlists/southeast_fire_lifeline_watch")
    assert detail.status_code == 200
    assert detail.json()["watchlist"]["display_name"] == "Southeast Fireline Watch"

    started = client.post(
        "/api/watchlists/southeast_fire_lifeline_watch/assets/ga_highway82_fire_candidate/start-mission"
    )
    assert started.status_code == 200
    mission = started.json()["mission"]
    assert mission["target_pack_id"] == "fireline"
    assert mission["bbox"] == [-81.916, 31.143, -81.756, 31.303]

    missing = client.get("/api/watchlists/missing")
    assert missing.status_code == 404


def test_local_only_guard_rejects_remote_control_requests():
    class Client:
        host = "203.0.113.10"

    class Request:
        client = Client()

    try:
        _require_local_request(Request())
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
    else:
        raise AssertionError("remote control request should be rejected")


def test_control_endpoint_rejects_remote_testclient():
    remote_client = TestClient(app, client=("203.0.113.10", 1234))

    response = remote_client.post("/api/link/state", json={"connected": True})

    assert response.status_code == 403


def test_health_endpoint_returns_ok_status():
    """Health endpoint must return ok status."""
    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert "region_id" in data
    assert "display_name" in data


def test_cold_start_runtime_supports_object_missions_without_external_api(monkeypatch, tmp_path):
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(tmp_path / "runtime-data"))

    from core.runtime_state import ensure_runtime_state, reset_runtime_state

    reset_summary = reset_runtime_state(archive_missions=False)
    assert reset_summary["after"]["missions"] == 0
    assert ensure_runtime_state()["missions"] == 0

    packs_response = client.get("/api/object-targets/packs")
    assert packs_response.status_code == 200
    assert any(pack["id"] == "fireline" for pack in packs_response.json()["packs"])

    mission_response = client.post(
        "/api/mission/start",
        json={"task_text": "Cold start Fireline Watch", "target_pack_id": "fireline"},
    )
    assert mission_response.status_code == 200
    mission = mission_response.json()
    assert mission["target_pack_id"] == "fireline"
    assert any(target["label"] == "dark smoke" for target in mission["object_targets"])


def test_object_target_packs_endpoint_returns_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(tmp_path))

    response = client.get("/api/object-targets/packs")

    assert response.status_code == 200
    pack_ids = {pack["id"] for pack in response.json()["packs"]}
    assert {"fireline", "camp", "port", "plastic", "urban_expansion", "lifeline"} <= pack_ids


def test_object_target_pack_endpoint_handles_missing_pack(monkeypatch, tmp_path):
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(tmp_path))

    response = client.get("/api/object-targets/packs/missing")

    assert response.status_code == 404
    assert response.json()["error"] == "Target pack not found"


def test_object_target_custom_pack_create_and_delete(monkeypatch, tmp_path):
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(tmp_path))

    create_response = client.post(
        "/api/object-targets/packs",
        json={
            "id": "disaster_mobility",
            "name": "Disaster Mobility",
            "description": "Custom mobility evidence terms.",
            "targets": [
                {
                    "label": "vehicle queue",
                    "prompt": "Find vehicle queues",
                    "class_key": "mobility",
                    "enabled": True,
                }
            ],
        },
    )

    assert create_response.status_code == 200
    assert create_response.json()["pack"]["targets"][0]["label"] == "vehicle queue"
    assert client.get("/api/object-targets/packs/disaster_mobility").status_code == 200

    delete_response = client.delete("/api/object-targets/packs/disaster_mobility")

    assert delete_response.status_code == 200
    assert client.get("/api/object-targets/packs/disaster_mobility").status_code == 404


def test_object_target_custom_pack_rejects_unsafe_label(monkeypatch, tmp_path):
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(tmp_path))

    response = client.post(
        "/api/object-targets/packs",
        json={
            "id": "unsafe_pack",
            "name": "Unsafe Pack",
            "targets": [{"label": "person", "prompt": "Find person", "class_key": "unsafe"}],
        },
    )

    assert response.status_code == 400
    assert "outside the civilian evidence scope" in response.json()["error"]


def test_mission_target_endpoints_edit_active_mission(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    from core.agent_bus import init_bus
    from core.mission import init_missions

    init_bus(reset=True)
    init_missions(reset=True)

    start_response = client.post(
        "/api/mission/start",
        json={"task_text": "Run fireline watch", "target_pack_id": "fireline"},
    )

    assert start_response.status_code == 200
    mission = start_response.json()
    assert mission["target_pack_id"] == "fireline"
    assert any(target["label"] == "dark smoke" for target in mission["object_targets"])

    add_response = client.post(
        "/api/mission/targets/add",
        json={"targets": [{"label": "vehicle queue", "class_key": "mobility"}]},
    )

    assert add_response.status_code == 200
    assert any(target["label"] == "vehicle queue" for target in add_response.json()["object_targets"])

    remove_response = client.post(
        "/api/mission/targets/remove",
        json={"labels": ["DARK SMOKE"]},
    )

    assert remove_response.status_code == 200
    assert "dark smoke" not in {target["label"] for target in remove_response.json()["object_targets"]}

    set_pack_response = client.post(
        "/api/mission/targets/set-pack",
        json={"target_pack_id": "port"},
    )

    assert set_pack_response.status_code == 200
    assert set_pack_response.json()["target_pack_id"] == "port"
    assert any(target["label"] == "docked-vessel group" for target in set_pack_response.json()["object_targets"])

    clear_response = client.post("/api/mission/targets/clear", json={})

    assert clear_response.status_code == 200
    assert clear_response.json()["target_pack_id"] is None
    assert clear_response.json()["object_targets"] == []


def test_mission_target_endpoints_report_missing_active_mission(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    from core.agent_bus import init_bus
    from core.mission import init_missions

    init_bus(reset=True)
    init_missions(reset=True)

    response = client.get("/api/mission/targets")

    assert response.status_code == 404
    assert response.json()["error"] == "Mission not found"


def test_vlm_grounding_batch_endpoint_calls_object_evidence(monkeypatch):
    def fake_batch(bbox, targets, *, target_pack_id=None, frame_ref=None):
        return {
            "results": [],
            "summary": {
                "target_pack_id": target_pack_id,
                "total_boxes": 0,
                "counts_by_label": {},
                "top_boxes": [],
                "provenance": {"output_source": "test"},
            },
            "target_count": len(targets),
            "frame_ref": frame_ref,
        }

    monkeypatch.setattr("api.main.run_object_evidence_batch", fake_batch)

    response = client.post(
        "/api/vlm/grounding/batch",
        json={
            "bbox": [-60.50, -3.50, -60.40, -3.40],
            "target_pack_id": "fireline",
            "frame_ref": "current",
            "targets": [{"label": "dark smoke", "class_key": "hazard"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["target_count"] == 1
    assert payload["summary"]["target_pack_id"] == "fireline"
    assert payload["frame_ref"] == "current"


def test_health_endpoint_includes_alert_counts():
    """Health endpoint must include alert count metrics."""
    response = client.get("/api/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "total_alerts" in data
    assert "total_payload_bytes" in data
    assert isinstance(data["total_alerts"], int)
    assert isinstance(data["total_payload_bytes"], int)
    assert data["demo_mode_enabled"] is False


def test_recent_alerts_endpoint_returns_list():
    """Recent alerts endpoint must return structured list."""
    response = client.get("/api/alerts/recent")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "region_id" in data
    assert "alerts" in data
    assert isinstance(data["alerts"], list)


def test_recent_alerts_endpoint_respects_limit():
    """Recent alerts endpoint must respect limit parameter."""
    response = client.get("/api/alerts/recent?limit=5")
    
    assert response.status_code == 200
    data = response.json()
    
    # May be less than limit if DB doesn't have enough alerts
    assert len(data["alerts"]) <= 5


def test_metrics_summary_endpoint_returns_structure():
    """Metrics summary endpoint must return complete structure."""
    response = client.get("/api/metrics/summary")
    
    assert response.status_code == 200
    data = response.json()
    
    # Required fields
    assert "region_id" in data
    assert "total_cycles_completed" in data
    assert "total_cells_scanned" in data
    assert "total_alerts_emitted" in data
    assert "total_payload_bytes" in data
    assert "total_bandwidth_saved_mb" in data
    assert "latest_discard_ratio" in data
    assert "runtime_rejections_by_reason" in data
    assert "flagged_examples" in data

    assert isinstance(data["runtime_rejections_by_reason"], dict)
    assert isinstance(data["flagged_examples"], list)



def test_health_endpoint_shows_observation_mode():
    """Health endpoint must include observation mode for transparency."""
    response = client.get("/api/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "observation_mode" in data
    assert "runtime_truth_mode" in data
    assert "imagery_origin" in data
    assert "scoring_basis" in data
    # Observation mode should be a non-empty string describing the loader
    assert isinstance(data["observation_mode"], str)
    assert len(data["observation_mode"]) > 0
    assert data["runtime_truth_mode"] in {"realtime", "replay", "fallback", "unknown"}


def test_invalid_limit_returns_validation_error():
    """Invalid limit parameter must return validation error."""
    # Limit below minimum
    response = client.get("/api/alerts/recent?limit=0")
    assert response.status_code == 422
    
    # Limit above maximum
    response = client.get("/api/alerts/recent?limit=500")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Analysis endpoint tests
# ---------------------------------------------------------------------------


def test_analysis_status_endpoint_returns_model_info():
    """Analysis status endpoint must return model availability info."""
    response = client.get("/api/analysis/status")

    assert response.status_code == 200
    data = response.json()

    assert "default_model" in data
    assert data["default_model"] == "offline_lfm_v1"
    assert "satellite_inference_loaded" in data
    assert isinstance(data["satellite_inference_loaded"], bool)
    assert "models" in data
    assert "offline_lfm_v1" in data["models"]
    assert data["models"]["offline_lfm_v1"]["available"] is True
    assert data["runtime_inference_mode"] == "text_evidence_packet"
    assert data["image_conditioned_runtime_enabled"] is False
    assert isinstance(data["image_training_verified"], bool)
    assert "runtime_capabilities" in data
    assert "note" in data


def test_analysis_status_endpoint_surfaces_manifest_metadata():
    """Analysis status should surface resolved manifest/repo details for the optional model."""
    runtime_payload = {
        "runtime_inference_mode": "text_evidence_packet",
        "image_conditioned_runtime_enabled": False,
        "image_conditioned_runtime_reason": "mmproj not present",
        "runtime_backend": "none",
        "mmproj_present": False,
    }
    with patch(
        "api.main.llm_model_status",
        return_value={
            "name": "LFM2.5-VL-450M-Q4_0.gguf",
            "loaded": False,
            "path": "C:/tmp/model.gguf",
            "repo_id": "jc816/lfm-orbit-satellite",
            "revision": "main",
            "source": "huggingface",
            "manifest_path": "C:/tmp/model_manifest.json",
            "mmproj_path": "C:/tmp/mmproj.gguf",
            "source_handoff_path": "C:/tmp/source_handoff.json",
            "source_handoff_present": True,
            "training_result_manifest": "training_result_manifest.json",
            "training_result_manifest_path": "C:/tmp/training_result_manifest.json",
            "training_result_manifest_present": True,
            "training_method": "vlm_sft",
            "training_base_model": "LiquidAI/LFM2.5-VL-450M",
            "training_modality": "image_text",
            "image_training_verified": True,
            "training_train_rows": 32,
            "training_multimodal_rows": 32,
            "training_image_blocks": 44,
            "training_eval_rows": 0,
            "hf_checkpoint_path": "C:/tmp/hf-checkpoint",
            "hf_checkpoint_present": True,
            "lora_adapter_path": "C:/tmp/lora-adapter",
            "lora_adapter_present": True,
            "readme_path": "C:/tmp/README.md",
            "readme_present": True,
        },
    ), patch("api.main.runtime_capabilities", return_value=runtime_payload):
        response = client.get("/api/analysis/status")

    assert response.status_code == 200
    data = response.json()
    model = data["models"]["LFM2.5-VL-450M-Q4_0.gguf"]

    assert model["repo_id"] == "jc816/lfm-orbit-satellite"
    assert model["revision"] == "main"
    assert model["source"] == "huggingface"
    assert model["manifest_path"] == "C:/tmp/model_manifest.json"
    assert model["mmproj_path"] == "C:/tmp/mmproj.gguf"
    assert model["source_handoff_path"] == "C:/tmp/source_handoff.json"
    assert model["source_handoff_present"] is True
    assert model["training_result_manifest"] == "training_result_manifest.json"
    assert model["training_result_manifest_path"] == "C:/tmp/training_result_manifest.json"
    assert model["training_result_manifest_present"] is True
    assert model["training_method"] == "vlm_sft"
    assert model["training_modality"] == "image_text"
    assert model["image_training_verified"] is True
    assert model["training_multimodal_rows"] == 32
    assert model["training_image_blocks"] == 44
    assert model["hf_checkpoint_present"] is True
    assert model["lora_adapter_present"] is True
    assert model["runtime_inference_mode"] == "text_evidence_packet"
    assert model["image_conditioned_runtime_enabled"] is False
    assert model["image_conditioned_runtime_reason"] == "mmproj not present"
    assert data["image_training_verified"] is True
    assert data["training_train_rows"] == 32
    assert data["training_multimodal_rows"] == 32
    assert data["training_image_blocks"] == 44
    assert data["training_eval_rows"] == 0
    assert data["runtime_capabilities"]["runtime_backend"] == "none"
    assert model["readme_path"] == "C:/tmp/README.md"
    assert model["readme_present"] is True


def test_inference_status_surfaces_runtime_capabilities():
    with patch(
        "api.main.llm_model_status",
        return_value={"name": "model.gguf", "loaded": False, "path": "C:/tmp/model.gguf"},
    ), patch(
        "api.main.runtime_capabilities",
        return_value={
            "runtime_inference_mode": "text_evidence_packet",
            "image_conditioned_runtime_enabled": False,
            "image_conditioned_runtime_reason": "feature disabled",
        },
    ):
        response = client.get("/api/inference/status")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "model.gguf"
    assert data["runtime_capabilities"]["runtime_inference_mode"] == "text_evidence_packet"
    assert data["runtime_capabilities"]["image_conditioned_runtime_enabled"] is False


def test_image_inference_endpoint_returns_status_safe_unavailable_payload():
    response = client.post(
        "/api/inference/image",
        json={
            "prompt": "Inspect this retained evidence frame.",
            "image_b64": "data:image/png;base64,AAAA",
            "cell_id": "8928308280fffff",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["available"] is False
    assert data["image_conditioned"] is False
    assert data["response"] == ""
    assert data["provenance"]["image_b64_present"] is True
    assert data["provenance"]["cell_id"] == "8928308280fffff"


def test_image_inference_endpoint_rejects_missing_image_payload():
    response = client.post(
        "/api/inference/image",
        json={"prompt": "Inspect this retained evidence frame."},
    )

    assert response.status_code == 422


def test_analysis_alert_endpoint_returns_offline_result():
    """Analysis alert endpoint must return offline LFM result for valid input."""
    response = client.post(
        "/api/analysis/alert",
        json={
            "change_score": 0.55,
            "confidence": 0.80,
            "reason_codes": ["ndvi_drop", "nir_drop"],
            "before_window": {
                "label": "2024-06",
                "ndvi": 0.72,
                "nbr": 0.55,
                "nir": 0.68,
                "red": 0.10,
                "swir": 0.18,
                "quality": 0.92,
                "flags": [],
            },
            "after_window": {
                "label": "2025-06",
                "ndvi": 0.38,
                "nbr": 0.30,
                "nir": 0.42,
                "red": 0.15,
                "swir": 0.24,
                "quality": 0.88,
                "flags": [],
            },
            "observation_source": "sentinelhub_direct_imagery",
            "demo_forced_anomaly": False,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["model"] == "offline_lfm_v1"
    assert data["severity"] in ("low", "moderate", "high", "critical")
    assert isinstance(data["summary"], str)
    assert len(data["summary"]) > 0
    assert isinstance(data["findings"], list)
    assert "confidence_note" in data
    assert "source_note" in data


def test_analysis_alert_validates_change_score_range():
    """Analysis alert endpoint must reject out-of-range change_score."""
    response = client.post(
        "/api/analysis/alert",
        json={
            "change_score": 1.5,  # out of range
            "confidence": 0.80,
        },
    )
    assert response.status_code == 422


def test_analysis_alert_handles_empty_windows():
    """Analysis alert endpoint handles empty before/after window dicts."""
    response = client.post(
        "/api/analysis/alert",
        json={
            "change_score": 0.40,
            "confidence": 0.70,
            "reason_codes": [],
            "before_window": {},
            "after_window": {},
            "observation_source": "test",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "offline_lfm_v1"
    assert isinstance(data["findings"], list)


def test_provider_status_endpoint_returns_structure():
    """Provider status endpoint must return full provider info."""
    response = client.get("/api/provider/status")

    assert response.status_code == 200
    data = response.json()

    assert "active_provider" in data
    assert "providers" in data
    assert "sentinel_credential_source" in data
    assert "fallback_order" in data
    assert isinstance(data["fallback_order"], list)
    assert "simsat_mapbox" in data["providers"]
    assert "nasa_api_direct" in data["providers"]


def test_provider_status_keeps_simsat_as_primary_hackathon_path():
    """SimSat must remain first in the provider chain for recorded demos."""
    response = client.get("/api/provider/status")

    assert response.status_code == 200
    data = response.json()
    assert data["fallback_order"][0] == "simsat_sentinel"
    assert data["providers"]["sentinelhub_direct"]["description"] == "Direct Sentinel Hub access"


def test_simsat_status_endpoint_includes_mapbox_metadata():
    """SimSat status should expose optional Mapbox readiness without leaking the token."""
    response = client.get("/api/simsat/status")

    assert response.status_code == 200
    data = response.json()
    assert "mapbox_token_configured" in data
    assert "mapbox_current" in data["endpoints"]
    assert "mapbox_historical" in data["endpoints"]


def test_simsat_status_tolerates_invalid_timeout_env(monkeypatch):
    """Operator typos in .env should not break the Settings panel."""
    monkeypatch.setenv("SIMSAT_TIMEOUT", "bad-timeout")

    response = client.get("/api/simsat/status")

    assert response.status_code == 200
    assert response.json()["timeout_seconds"] == 30.0


def test_link_dtn_proof_uses_agent_bus_queue(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    import api.main as main
    from core.agent_bus import get_bus_stats, init_bus
    from core.link_state import set_link_state

    main._DTN_PROOF_MESSAGE_IDS = []
    init_bus(reset=True)
    set_link_state(True)

    offline = client.post("/api/link/dtn-proof", json={"phase": "offline", "count": 4})

    assert offline.status_code == 200
    offline_payload = offline.json()
    assert offline_payload["link_state_before"] == "offline"
    assert offline_payload["queued_alerts_before_restore"] == 4
    assert offline_payload["queue_source"] == "agent_bus_unread_messages"
    assert get_bus_stats()["unread_messages"] >= 4

    restored = client.post("/api/link/dtn-proof", json={"phase": "restore"})

    assert restored.status_code == 200
    restored_payload = restored.json()
    assert restored_payload["link_state_before"] == "offline"
    assert restored_payload["link_state_after"] == "restored"
    assert restored_payload["flushed_alerts"] == 4
    assert restored_payload["queued_alerts_after_restore"] == 0
    set_link_state(True)


def test_ground_agent_chat_lists_replay_tools():
    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "list replays"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "reply" in payload
    assert payload["actions"][0]["name"] == "list_replays"
    assert payload["actions"][0]["status"] == "ok"
    assert payload["actions"][0]["result"]["replays"]
    assert payload.get("proposals", []) == []


def test_ground_agent_chat_proposes_link_offline_before_mutating(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    from core.agent_bus import init_bus
    from core.link_state import is_link_connected, set_link_state

    init_bus(reset=True)
    set_link_state(True)

    try:
        response = client.post(
            "/api/agent/chat",
            json={"messages": [{"role": "user", "content": "set link offline"}]},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["actions"] == []
        proposal = payload["proposals"][0]
        assert proposal["id"] == "proposal_set_link_state_offline"
        assert proposal["kind"] == "set_link_state"
        assert proposal["details"]["connected"] is False
        assert proposal["details"]["target_state"] == "offline"
        assert is_link_connected() is True

        confirm = client.post("/api/agent/action/confirm", json={"proposal": proposal})

        assert confirm.status_code == 200
        confirmed = confirm.json()
        assert confirmed["actions"][0]["name"] == "set_link_state"
        assert confirmed["actions"][0]["status"] == "ok"
        assert confirmed["actions"][0]["result"]["connected"] is False
        assert is_link_connected() is False
    finally:
        set_link_state(True)


def test_ground_agent_chat_proposes_bull_creek_camera_with_stop(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    from core.agent_bus import init_bus
    from core.mission import get_active_mission, init_missions, start_mission

    init_bus(reset=True)
    init_missions(reset=True)
    mission = start_mission(
        "Scan active mission before operator redirects camera.",
        bbox=[-63.15, -10.15, -62.85, -9.85],
        start_date="2024-01-01",
        end_date="2024-12-31",
        use_case_id="deforestation",
    )

    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "cancel the current mission and take us to bull creek fl"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["actions"] == []
    proposal = payload["proposals"][0]
    assert proposal["kind"] == "navigate_map_location"
    assert proposal["details"]["location_id"] == "bull_creek_fl"
    assert proposal["details"]["stop_active_mission"] is True
    assert proposal["details"]["bbox"] == [-81.07, 28.02, -80.86, 28.18]
    assert proposal["details"]["camera"]["pitch"] >= 55
    assert proposal["details"]["location_type"] == "wetland / pine-flatwoods context"
    assert "low_relief_terrain" in proposal["details"]["semantic_tags"]
    assert "road or trail corridor" in proposal["details"]["suggested_targets"]
    assert "3D view is a spatial context aid only" in proposal["details"]["evidence_guidance"]
    assert get_active_mission()["id"] == mission["id"]

    confirm = client.post("/api/agent/action/confirm", json={"proposal": proposal})

    assert confirm.status_code == 200
    confirmed = confirm.json()
    action_names = [action["name"] for action in confirmed["actions"]]
    assert action_names == ["stop_mission", "navigate_map"]
    assert confirmed["actions"][0]["result"]["stopped_mission_id"] == mission["id"]
    assert confirmed["actions"][1]["result"]["label"] == "Bull Creek, FL"
    assert confirmed["actions"][1]["result"]["center"] == [-80.965, 28.095]
    assert confirmed["actions"][1]["result"]["location_type"] == "wetland / pine-flatwoods context"
    assert "water_vegetation_boundary" in confirmed["actions"][1]["result"]["semantic_tags"]
    assert "surface moisture context" in confirmed["actions"][1]["result"]["suggested_targets"]
    assert get_active_mission() is None


def test_ground_agent_chat_asks_before_redirecting_active_mission_to_destination(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    from core.agent_bus import init_bus
    from core.mission import get_active_mission, init_missions, start_mission

    init_bus(reset=True)
    init_missions(reset=True)
    mission = start_mission(
        "Run Florida Fire/Drought Readiness Watch over a North Florida corridor.",
        bbox=[-83.2, 29.0, -81.3, 30.7],
        start_date="2026-04-15",
        end_date="2026-04-25",
        use_case_id="wildfire",
        target_pack_id="fireline",
    )

    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "take me to giza pyramid"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "active mission" in payload["reply"].lower()
    assert "review before" in payload["reply"].lower()
    assert payload["actions"] == []
    proposal = payload["proposals"][0]
    assert proposal["kind"] == "navigate_map_location"
    assert proposal["details"]["location_id"] == "giza_pyramid_complex"
    assert proposal["details"]["stop_active_mission"] is True
    assert proposal["details"]["active_mission_id"] == mission["id"]
    assert proposal["details"]["bbox"] == [31.118, 29.965, 31.152, 29.993]
    assert proposal["details"]["location_type"] == "archaeological heritage site context"
    assert get_active_mission()["id"] == mission["id"]

    confirm = client.post("/api/agent/action/confirm", json={"proposal": proposal})

    assert confirm.status_code == 200
    confirmed = confirm.json()
    action_names = [action["name"] for action in confirmed["actions"]]
    assert action_names == ["stop_mission", "navigate_map"]
    assert confirmed["actions"][0]["result"]["stopped_mission_id"] == mission["id"]
    assert confirmed["actions"][1]["result"]["label"] == "Giza Pyramid Complex"
    assert confirmed["actions"][1]["result"]["center"] == [31.1342, 29.9792]
    assert get_active_mission() is None


def test_ground_agent_chat_proposes_bronx_map_navigation_without_active_mission(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    from core.agent_bus import init_bus
    from core.mission import get_active_mission, init_missions

    init_bus(reset=True)
    init_missions(reset=True)

    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "tKe me to the bronx, ny"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "Bronx, NY" in payload["reply"]
    assert payload["actions"] == []
    proposal = payload["proposals"][0]
    assert proposal["kind"] == "navigate_map_location"
    assert proposal["confirm_label"] == "Fly Map"
    assert proposal["details"]["location_id"] == "bronx_ny"
    assert proposal["details"]["provider"] == "local_registry"
    assert proposal["details"]["feature_type"] == "urban borough context"
    assert proposal["details"]["confidence"] >= 0.8
    assert len(proposal["details"]["preview_tiles"]) == 9
    assert proposal["details"]["stop_active_mission"] is False
    assert proposal["details"]["bbox"] == [-73.9339, 40.7857, -73.7654, 40.9153]
    assert proposal["details"]["center"] == [-73.8648, 40.8448]
    assert proposal["details"]["location_type"] == "urban borough context"
    assert "transport corridor" in proposal["details"]["suggested_targets"]
    assert get_active_mission() is None

    confirm = client.post("/api/agent/action/confirm", json={"proposal": proposal})

    assert confirm.status_code == 200
    confirmed = confirm.json()
    assert [action["name"] for action in confirmed["actions"]] == ["navigate_map"]
    assert confirmed["actions"][0]["result"]["label"] == "Bronx, NY"
    assert confirmed["actions"][0]["result"]["center"] == [-73.8648, 40.8448]
    assert confirmed["actions"][0]["result"]["location_type"] == "urban borough context"
    assert get_active_mission() is None


def test_location_resolve_returns_bronx_candidate_with_preview_tiles():
    response = client.post(
        "/api/location/resolve",
        json={"query": "Bronx, ny", "country": "US", "limit": 3},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "Bronx, ny"
    candidate = payload["candidates"][0]
    assert candidate["location_id"] == "bronx_ny"
    assert candidate["label"] == "Bronx, NY"
    assert candidate["provider"] == "local_registry"
    assert candidate["bbox"] == [-73.9339, 40.7857, -73.7654, 40.9153]
    assert len(candidate["preview_tiles"]) == 9
    assert all(tile["url"].startswith("https://server.arcgisonline.com/") for tile in candidate["preview_tiles"])


def test_location_resolve_returns_davenport_semantic_construction_candidate():
    response = client.post(
        "/api/location/resolve",
        json={"query": "Davenport Florida new construction", "country": "US", "limit": 3},
    )

    assert response.status_code == 200
    candidate = response.json()["candidates"][0]
    assert candidate["location_id"] == "davenport_fl"
    assert candidate["label"] == "Davenport, FL"
    assert candidate["provider"] == "local_registry"
    assert candidate["feature_type"] == "suburban growth / construction context"
    assert candidate["bbox"] == [-81.7, 28.08, -81.48, 28.28]
    assert candidate["confidence"] >= 0.8
    assert len(candidate["preview_tiles"]) == 9


def test_location_resolve_returns_north_pacific_debris_candidate():
    response = client.post(
        "/api/location/resolve",
        json={"query": "Great Pacific Garbage Patch", "limit": 3},
    )

    assert response.status_code == 200
    candidate = response.json()["candidates"][0]
    assert candidate["location_id"] == "north_pacific_debris_context"
    assert candidate["label"] == "North Pacific Debris Convergence Review Window"
    assert candidate["provider"] == "local_registry"
    assert candidate["feature_type"] == "open-ocean debris convergence context"
    assert candidate["bbox"] == [-146.0, 34.0, -145.0, 35.0]
    assert candidate["confidence"] >= 0.8
    assert len(candidate["preview_tiles"]) == 9


def test_ground_agent_chat_reports_unknown_destination_without_stopping_mission(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    from core.agent_bus import init_bus
    from core.mission import get_active_mission, init_missions, start_mission

    init_bus(reset=True)
    init_missions(reset=True)
    mission = start_mission("Keep current mission active.")

    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "go to imaginary test destination"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["actions"][0]["name"] == "navigate_map"
    assert payload["actions"][0]["status"] == "error"
    assert "known destinations" in payload["reply"].lower()
    assert "Giza Pyramid Complex" in payload["reply"]
    assert "Bronx, NY" in payload["reply"]
    assert payload.get("proposals", []) == []
    assert get_active_mission()["id"] == mission["id"]


def test_ground_agent_chat_proposes_stop_mission_without_location(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    from core.agent_bus import init_bus
    from core.mission import get_active_mission, init_missions, start_mission

    init_bus(reset=True)
    init_missions(reset=True)
    mission = start_mission("Mission to stop")

    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "stop the current mission"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    proposal = payload["proposals"][0]
    assert proposal["kind"] == "stop_mission"
    assert proposal["details"]["mission_id"] == mission["id"]

    confirm = client.post("/api/agent/action/confirm", json={"proposal": proposal})

    assert confirm.status_code == 200
    confirmed = confirm.json()
    assert confirmed["actions"][0]["name"] == "stop_mission"
    assert confirmed["actions"][0]["status"] == "ok"
    assert confirmed["actions"][0]["result"]["stopped_mission_id"] == mission["id"]
    assert get_active_mission() is None


def test_ground_agent_chat_proposes_florida_fire_drought_pack(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    from core.agent_bus import init_bus
    from core.mission import get_active_mission, init_missions

    init_bus(reset=True)
    init_missions(reset=True)

    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "run florida fire drought mission"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["actions"] == []
    proposal = payload["proposals"][0]
    assert proposal["kind"] == "start_mission_pack"
    assert proposal["details"]["pack_id"] == "florida_fire_drought_watch"
    assert proposal["details"]["target_pack_id"] == "fireline"
    assert proposal["details"]["bbox"] == [-83.2, 29.0, -81.3, 30.7]
    assert "candidate evidence" in proposal["details"]["task_text"]

    confirm = client.post("/api/agent/action/confirm", json={"proposal": proposal})

    assert confirm.status_code == 200
    confirmed = confirm.json()
    assert confirmed["actions"][0]["name"] == "start_mission_pack"
    assert confirmed["actions"][0]["status"] == "ok"
    assert confirmed["actions"][0]["result"]["mission"]["use_case_id"] == "wildfire"
    assert confirmed["actions"][0]["result"]["mission"]["target_pack_id"] == "fireline"
    assert get_active_mission()["target_pack_id"] == "fireline"


def test_ground_agent_chat_agentic_planner_matches_flexible_pack_request(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    from core.agent_bus import init_bus
    from core.mission import init_missions

    init_bus(reset=True)
    init_missions(reset=True)

    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "try looking for recent drought conditions and wildfires in florida"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "Planning pass complete" in payload["reply"]
    assert payload["actions"] == []
    proposal = payload["proposals"][0]
    assert proposal["kind"] == "start_mission_pack"
    assert proposal["details"]["pack_id"] == "florida_fire_drought_watch"
    assert proposal["details"]["planner_result"] == "curated_mission_pack_ready"
    assert proposal["details"]["workflow_mode"] == "agentic_prompt_workflow"
    assert proposal["details"]["target_pack_id"] == "fireline"
    assert "No protected wildlife counts" in " ".join(proposal["details"]["evidence_limits"])


def test_ground_agent_chat_agentic_planner_builds_custom_mission(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    from core.agent_bus import init_bus
    from core.mission import get_active_mission, init_missions

    init_bus(reset=True)
    init_missions(reset=True)

    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "plan a mission to monitor bridge access disruption around a civilian corridor"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "Final result:" in payload["reply"]
    proposal = payload["proposals"][0]
    assert proposal["kind"] == "start_custom_mission"
    assert proposal["details"]["workflow_mode"] == "agentic_prompt_workflow"
    assert proposal["details"]["use_case_id"] == "civilian_lifeline_disruption"
    assert proposal["details"]["target_pack_id"] == "lifeline"
    assert proposal["details"]["bbox"] is None
    assert "planner_attempts" in proposal["details"]

    confirm = client.post("/api/agent/action/confirm", json={"proposal": proposal})

    assert confirm.status_code == 200
    confirmed = confirm.json()
    assert confirmed["actions"][0]["name"] == "start_custom_mission"
    assert confirmed["actions"][0]["status"] == "ok"
    mission = confirmed["actions"][0]["result"]["mission"]
    assert mission["use_case_id"] == "civilian_lifeline_disruption"
    assert mission["target_pack_id"] == "lifeline"
    assert get_active_mission()["id"] == mission["id"]


def test_ground_agent_chat_plans_semantic_construction_timelapse_for_named_area(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    from core.agent_bus import init_bus
    from core.mission import get_active_mission, init_missions

    init_bus(reset=True)
    init_missions(reset=True)

    response = client.post(
        "/api/agent/chat",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": "show me a timelapse of new construction in the last 10 years of Davenport Florida",
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "Planning pass complete" in payload["reply"]
    assert payload["actions"] == []
    proposal = payload["proposals"][0]
    assert proposal["kind"] == "start_custom_mission"
    details = proposal["details"]
    assert details["workflow_mode"] == "agentic_prompt_workflow"
    assert details["use_case_id"] == "urban_expansion"
    assert details["target_pack_id"] == "urban_expansion"
    assert [target["label"] for target in details["object_targets"]][:3] == [
        "construction footprint",
        "new subdivision region",
        "road expansion corridor",
    ]
    assert details["region_label"] == "Davenport, FL"
    assert details["region_source"] == "known_location"
    assert details["bbox"] == [-81.7, 28.08, -81.48, 28.28]
    assert details["location_provider"] == "local_registry"
    assert details["location_confidence"] >= 0.8
    assert "construction_progression" in details["semantic_tags"]
    assert "construction footprint" in details["suggested_targets"]
    assert "Use dated multi-frame imagery" in details["evidence_guidance"]
    assert int(details["end_date"][:4]) - int(details["start_date"][:4]) == 10
    assert "new construction" in details["task_text"]
    assert "permit claims" in " ".join(details["evidence_limits"])

    confirm = client.post("/api/agent/action/confirm", json={"proposal": proposal})

    assert confirm.status_code == 200
    confirmed = confirm.json()
    assert confirmed["actions"][0]["name"] == "start_custom_mission"
    mission = confirmed["actions"][0]["result"]["mission"]
    assert mission["use_case_id"] == "urban_expansion"
    assert mission["target_pack_id"] == "urban_expansion"
    assert mission["bbox"] == [-81.7, 28.08, -81.48, 28.28]
    assert get_active_mission()["id"] == mission["id"]


def test_ground_agent_chat_plans_garbage_patch_as_debris_candidate_mission(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    from core.agent_bus import init_bus
    from core.mission import get_active_mission, init_missions

    init_bus(reset=True)
    init_missions(reset=True)

    response = client.post(
        "/api/agent/chat",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": "show me one of the biggest garbage patches in the ocean and make a timelapse for every month in the last 10 years to current",
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "Planning pass complete" in payload["reply"]
    assert payload["actions"] == []
    proposal = payload["proposals"][0]
    assert proposal["kind"] == "start_custom_mission"
    details = proposal["details"]
    assert details["workflow_mode"] == "agentic_prompt_workflow"
    assert details["target_pack_id"] == "plastic"
    assert [target["label"] for target in details["object_targets"]][:3] == [
        "coastal debris candidate",
        "slick candidate area",
        "foam line region",
    ]
    assert details["region_label"] == "North Pacific Debris Convergence Review Window"
    assert details["region_source"] == "known_location"
    assert details["bbox"] == [-145.6, 34.4, -145.4, 34.6]
    assert details["location_context_bbox"] == [-146.0, 34.0, -145.0, 35.0]
    assert details["location_provider"] == "local_registry"
    assert details["location_confidence"] >= 0.8
    assert details["temporal_cadence"] == "monthly"
    assert details["requested_frame_count"] >= 120
    assert "marine_debris_candidate" in details["semantic_tags"]
    assert "slick candidate area" in details["suggested_targets"]
    assert "Do not claim Great Pacific Garbage Patch mass" in details["evidence_guidance"]
    assert int(details["end_date"][:4]) - int(details["start_date"][:4]) == 10
    assert "candidate" in details["task_text"].lower()
    assert "garbage-patch mass" in " ".join(details["evidence_limits"])

    confirm = client.post("/api/agent/action/confirm", json={"proposal": proposal})

    assert confirm.status_code == 200
    confirmed = confirm.json()
    assert confirmed["actions"][0]["name"] == "start_custom_mission"
    mission = confirmed["actions"][0]["result"]["mission"]
    assert mission["target_pack_id"] == "plastic"
    assert mission["bbox"] == [-145.6, 34.4, -145.4, 34.6]
    assert get_active_mission()["id"] == mission["id"]


def test_ground_agent_chat_plans_lake_okeechobee_algae_bloom_candidate_mission(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    from core.agent_bus import init_bus
    from core.mission import get_active_mission, init_missions

    init_bus(reset=True)
    init_missions(reset=True)

    response = client.post(
        "/api/agent/chat",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": "check Lake Okeechobee for algae blooms",
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "Planning pass complete" in payload["reply"]
    assert payload["actions"] == []
    proposal = payload["proposals"][0]
    assert proposal["kind"] == "start_custom_mission"
    details = proposal["details"]
    assert details["workflow_mode"] == "agentic_prompt_workflow"
    assert details["use_case_id"] == "harmful_algal_bloom"
    assert details["target_pack_id"] == "algae_bloom"
    assert [target["label"] for target in details["object_targets"]][:3] == [
        "probable surface bloom",
        "high chlorophyll signal",
        "cyanobacteria-like signal",
    ]
    assert details["region_label"] == "Lake Okeechobee, FL"
    assert details["region_source"] == "known_location"
    assert details["bbox"] == [-81.16, 26.64, -80.55, 27.24]
    assert details["location_provider"] == "local_registry"
    assert details["location_confidence"] >= 0.7
    assert "harmful_algal_bloom_candidate" in details["semantic_tags"]
    assert "probable surface bloom" in details["suggested_targets"]
    assert "Do not claim toxicity" in details["evidence_guidance"]
    assert "probable bloom" in details["task_text"].lower()
    assert "NOAA/FDEP or field confirmation" in " ".join(details["evidence_limits"])

    confirm = client.post("/api/agent/action/confirm", json={"proposal": proposal})

    assert confirm.status_code == 200
    confirmed = confirm.json()
    assert confirmed["actions"][0]["name"] == "start_custom_mission"
    mission = confirmed["actions"][0]["result"]["mission"]
    assert mission["target_pack_id"] == "algae_bloom"
    assert mission["use_case_id"] == "harmful_algal_bloom"
    assert mission["bbox"] == [-81.16, 26.64, -80.55, 27.24]
    assert get_active_mission()["id"] == mission["id"]


def test_ground_agent_chat_reframes_manatee_population_request(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    from core.agent_bus import init_bus
    from core.mission import init_missions

    init_bus(reset=True)
    init_missions(reset=True)

    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "try looking for manatee populations in florida"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    reply = payload["reply"].lower()
    assert "cannot count or locate manatee populations" in reply
    assert "habitat/access proxy review" in reply
    assert "do not box individual animals" in reply
    proposal = payload["proposals"][0]
    assert proposal["kind"] == "start_mission_pack"
    assert proposal["details"]["pack_id"] == "florida_manatee_habitat_review"
    assert proposal["details"]["workflow_mode"] == "protected_wildlife_proxy_workflow"
    assert proposal["details"]["planner_result"] == "protected wildlife habitat proxy ready"
    assert proposal["details"]["target_pack_id"] == "waterline"
    assert "Do not count or locate individual animals" in proposal["details"]["task_text"]

    confirm = client.post("/api/agent/action/confirm", json={"proposal": proposal})

    assert confirm.status_code == 200
    confirmed = confirm.json()
    assert confirmed["actions"][0]["name"] == "start_mission_pack"
    assert confirmed["actions"][0]["status"] == "ok"
    mission = confirmed["actions"][0]["result"]["mission"]
    assert mission["use_case_id"] == "temporal_change_generic"
    assert mission["target_pack_id"] == "waterline"


def test_ground_agent_chat_handles_hard_manatee_water_search_by_region(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    from core.agent_bus import init_bus
    from core.mission import get_active_mission, init_missions

    init_bus(reset=True)
    init_missions(reset=True)

    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "try looking for manatees in water around Banana River in winter"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    reply = payload["reply"].lower()
    assert "hard protected-wildlife" in reply
    assert "habitat/access proxy review" in reply
    assert "banana river lagoon context" in reply
    proposal = payload["proposals"][0]
    assert proposal["kind"] == "start_custom_mission"
    assert proposal["details"]["workflow_mode"] == "agentic_prompt_workflow"
    assert proposal["details"]["planner_result"] == "protected wildlife habitat proxy ready"
    assert proposal["details"]["region_label"] == "Banana River lagoon context"
    assert proposal["details"]["target_pack_id"] == "waterline"
    assert proposal["details"]["bbox"] == [-80.78, 28.16, -80.55, 28.58]
    assert "Do not count or locate individual animals" in proposal["details"]["task_text"]

    confirm = client.post("/api/agent/action/confirm", json={"proposal": proposal})

    assert confirm.status_code == 200
    confirmed = confirm.json()
    assert confirmed["actions"][0]["name"] == "start_custom_mission"
    mission = confirmed["actions"][0]["result"]["mission"]
    assert mission["target_pack_id"] == "waterline"
    assert mission["bbox"] == [-80.78, 28.16, -80.55, 28.58]
    assert get_active_mission()["id"] == mission["id"]


def test_ground_agent_chat_launches_context_mission_pack(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    from core.agent_bus import init_bus
    from core.mission import init_missions, start_mission

    init_bus(reset=True)
    init_missions(reset=True)
    start_mission(
        "Review maritime vessel queueing near the Suez channel.",
        bbox=[32.5, 29.88, 32.58, 29.96],
        start_date="2025-03-01",
        end_date="2025-12-15",
        use_case_id="maritime_activity",
    )

    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "run mission pack based on context"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["actions"] == []
    assert payload["proposals"][0]["kind"] == "start_mission_pack"
    assert payload["proposals"][0]["details"]["pack_id"] == "maritime_suez"

    confirm = client.post(
        "/api/agent/action/confirm",
        json={"proposal": payload["proposals"][0]},
    )

    assert confirm.status_code == 200
    confirmed = confirm.json()
    assert confirmed["actions"][0]["name"] == "start_mission_pack"
    assert confirmed["actions"][0]["status"] == "ok"
    assert confirmed["actions"][0]["result"]["pack_id"] == "maritime_suez"
    assert confirmed["actions"][0]["result"]["mission"]["target_pack_id"] == "port"


def test_ground_agent_chat_proposes_and_applies_object_target_edits(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))

    from core.agent_bus import init_bus
    from core.mission import init_missions, start_mission

    init_bus(reset=True)
    init_missions(reset=True)
    mission = start_mission("Object edit mission")

    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "Add dark smoke and road obstruction to the current mission."}]},
    )

    assert response.status_code == 200
    payload = response.json()
    proposal = payload["proposals"][0]
    assert proposal["kind"] == "update_mission_targets"
    assert proposal["details"]["mission_id"] == mission["id"]
    assert proposal["details"]["add"] == ["dark smoke", "road obstruction"]

    confirm = client.post("/api/agent/action/confirm", json={"proposal": proposal})

    assert confirm.status_code == 200
    confirmed = confirm.json()
    assert confirmed["actions"][0]["name"] == "update_mission_targets"
    labels = {target["label"] for target in confirmed["actions"][0]["result"]["mission"]["object_targets"]}
    assert {"dark smoke", "road obstruction"} <= labels


def test_ground_agent_chat_proposes_target_pack_switch_and_save(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    from core.agent_bus import init_bus
    from core.mission import init_missions, start_mission

    init_bus(reset=True)
    init_missions(reset=True)
    start_mission("Port target mission", target_pack_id="fireline")

    switch = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "Switch this mission to the port target pack."}]},
    )

    assert switch.status_code == 200
    switch_proposal = switch.json()["proposals"][0]
    assert switch_proposal["kind"] == "set_target_pack"
    assert switch_proposal["details"]["target_pack_id"] == "port"

    confirmed_switch = client.post("/api/agent/action/confirm", json={"proposal": switch_proposal}).json()
    assert confirmed_switch["actions"][0]["status"] == "ok"
    assert confirmed_switch["actions"][0]["result"]["mission"]["target_pack_id"] == "port"

    save = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "Save these objects as a new target pack called Disaster Mobility."}]},
    )

    assert save.status_code == 200
    save_proposal = save.json()["proposals"][0]
    assert save_proposal["kind"] == "save_target_pack"

    confirmed_save = client.post("/api/agent/action/confirm", json={"proposal": save_proposal}).json()
    assert confirmed_save["actions"][0]["status"] == "ok"
    assert confirmed_save["actions"][0]["result"]["pack"]["id"] == "disaster_mobility"


def test_ground_agent_chat_proposes_wildfire_replay_before_loading():
    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "replay a wildfire mission"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["actions"] == []
    proposal = payload["proposals"][0]
    assert proposal["kind"] == "load_replay"
    assert proposal["title"] == "Load replay: Highway 82 Wildfire Candidate Replay"
    assert proposal["confirm_label"] == "Run Replay"
    assert proposal["details"]["replay_id"] == "georgia_wildfire_replay"
    assert proposal["details"]["runtime_truth_mode"] == "replay"
    assert proposal["details"]["imagery_origin"] == "cached_api"


def test_ground_agent_chat_proposes_rondonia_replay_with_proxy_band_basis():
    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "load the Rondonia deforestation replay"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["actions"] == []
    proposal = payload["proposals"][0]
    assert proposal["kind"] == "load_replay"
    assert proposal["details"]["replay_id"] == "rondonia_frontier_showcase"
    assert proposal["details"]["use_case_id"] == "deforestation"
    assert proposal["details"]["runtime_truth_mode"] == "replay"
    assert proposal["details"]["imagery_origin"] == "cached_api"
    assert proposal["details"]["scoring_basis"] == "proxy_bands"


def test_ground_agent_chat_proposes_maritime_replay_from_traffic_request():
    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "load the short term maritime traffic replay"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["actions"] == []
    proposal = payload["proposals"][0]
    assert proposal["kind"] == "load_replay"
    assert proposal["title"] == "Load replay: Singapore Strait Maritime Replay"
    assert proposal["confirm_label"] == "Run Replay"
    assert proposal["details"]["replay_id"] == "singapore_maritime_replay"
    assert proposal["details"]["use_case_id"] == "maritime_activity"
    assert proposal["details"]["runtime_truth_mode"] == "replay"
    assert proposal["details"]["imagery_origin"] == "cached_api"


def test_ground_agent_chat_proposes_wildfire_mission_pack_without_replay_keyword():
    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "run wildfire mission"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["actions"] == []
    proposal = payload["proposals"][0]
    assert proposal["kind"] == "start_mission_pack"
    assert proposal["title"] == "Launch Mission Pack: Highway 82 wildfire"
    assert proposal["confirm_label"] == "Launch Mission"
    assert proposal["details"]["pack_id"] == "wildfire_highway82"
    assert proposal["details"]["use_case_id"] == "wildfire"


def test_ground_agent_chat_proposes_rescan_before_runtime_reset(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))

    from core.agent_bus import init_bus

    init_bus(reset=True)

    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "rescan georgia wildfire replay with current runtime"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["actions"] == []
    proposal = payload["proposals"][0]
    assert proposal["kind"] == "rescan_replay"
    assert proposal["confirm_label"] == "Start Rescan"
    assert proposal["details"]["replay_id"] == "georgia_wildfire_replay"
    assert proposal["details"]["runtime_truth_mode"] == "realtime"
    assert proposal["details"]["imagery_origin"] == "provider_chain"

    confirm = client.post("/api/agent/action/confirm", json={"proposal": proposal})

    assert confirm.status_code == 200
    confirmed = confirm.json()
    assert confirmed["actions"][0]["name"] == "rescan_replay"
    assert confirmed["actions"][0]["status"] == "ok"
    assert confirmed["actions"][0]["result"]["source_replay_id"] == "georgia_wildfire_replay"
    assert confirmed["actions"][0]["result"]["mission"]["mission_mode"] == "live"


def test_ground_agent_action_confirm_rejects_unknown_action():
    response = client.post(
        "/api/agent/action/confirm",
        json={"proposal": {"kind": "delete_everything", "details": {}}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["actions"][0]["status"] == "error"
    assert "whitelist" in payload["reply"].lower()


def test_ground_agent_action_confirm_rejects_missing_replay_id():
    response = client.post(
        "/api/agent/action/confirm",
        json={"proposal": {"kind": "load_replay", "details": {}}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["actions"][0]["name"] == "load_replay"
    assert payload["actions"][0]["status"] == "error"
    assert payload["actions"][0]["result"]["error"] == "Missing replay_id."
    assert "did not include a replay id" in payload["reply"]


def test_ground_agent_action_confirm_rejects_non_boolean_link_state():
    response = client.post(
        "/api/agent/action/confirm",
        json={"proposal": {"kind": "set_link_state", "details": {"connected": "false"}}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["actions"][0]["name"] == "set_link_state"
    assert payload["actions"][0]["status"] == "error"
    assert payload["actions"][0]["result"]["error"] == "Missing boolean connected state."
    assert "boolean connected value" in payload["reply"]


def test_ground_agent_action_confirm_rejects_whitelisted_but_unimplemented_action(monkeypatch):
    from core import ground_agent_knowledge

    monkeypatch.setattr(
        ground_agent_knowledge,
        "ALLOWED_AGENT_ACTIONS",
        {*ground_agent_knowledge.ALLOWED_AGENT_ACTIONS, "future_action"},
    )

    response = client.post(
        "/api/agent/action/confirm",
        json={"proposal": {"kind": "future_action", "details": {"connected": True}}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["actions"][0]["name"] == "confirm_proposal"
    assert payload["actions"][0]["status"] == "error"
    assert "dispatcher" in payload["reply"].lower()


def test_ground_agent_chat_cautions_visual_evidence_candidates():
    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "Can CV find boats or dark smoke in the bbox?"}]},
    )

    assert response.status_code == 200
    reply = response.json()["reply"].lower()
    assert "candidate evidence" in reply
    assert "fallback vision never confirms" in reply


def test_ground_agent_chat_returns_operator_playbook():
    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "show operator playbook"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    reply = payload["reply"].lower()
    assert "operator playbook" in reply
    assert "mission object targets" in reply
    assert "proof mode" in reply
    assert "proposal-based" in reply
    assert "Run Florida fire drought mission" in payload["suggestions"]
    assert "List replays" in payload["suggestions"]


def test_ground_agent_chat_returns_agent_status(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))

    from core.agent_bus import init_bus, post_message
    from core.link_state import set_link_state
    from core.metrics import seed_metrics_summary

    init_bus(reset=True)
    set_link_state(False)
    seed_metrics_summary(
        {
            "total_cells_scanned": 12,
            "latest_discard_ratio": 0.75,
        }
    )
    post_message(
        sender="satellite",
        recipient="ground",
        msg_type="flag",
        payload={"note": "queued while offline"},
    )

    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "agent status"}]},
    )

    assert response.status_code == 200
    reply = response.json()["reply"].lower()
    assert "satellite pruner" in reply
    assert "ground validator" in reply
    assert "link: offline" in reply
    assert "12 cell evaluations" in reply

    set_link_state(True)


def test_temporal_use_cases_endpoint_returns_examples():
    """Temporal use-case endpoint should expose examples for scan setup and dataset prep."""
    response = client.get("/api/temporal/use-cases")

    assert response.status_code == 200
    data = response.json()
    by_id = {item["id"]: item for item in data["use_cases"]}
    assert "wildfire" in by_id
    assert "maritime_activity" in by_id
    assert "civilian_lifeline_disruption" in by_id
    assert "ice_snow_extent" in by_id
    assert "ice_cap_growth" in by_id
    assert by_id["wildfire"]["examples"]


def test_temporal_classify_endpoint_auto_decides_use_case():
    """Temporal classifier endpoint should choose a use case from mission-style payloads."""
    response = client.post(
        "/api/temporal/classify",
        json={
            "task_text": "Review glacier ice cap growth across same-season frames.",
            "reason_codes": ["ice_extent_growth", "albedo_change"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "ice_cap_growth"
    assert data["examples"]


def test_temporal_classify_endpoint_prefers_ndsi_ice_snow_lane():
    response = client.post(
        "/api/temporal/classify",
        json={
            "task_text": "Review Greenland snow versus clouds with Sentinel-2 L2A NDSI and SCL support.",
            "reason_codes": ["ndsi_increase", "multi_frame_persistence", "cloud_rejected"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "ice_snow_extent"
    assert "snow_ice_scl_support" in data["signals"]


def test_lifeline_assets_endpoint_returns_seed_assets():
    """Lifeline assets endpoint should expose seeded before/after monitor targets."""
    response = client.get("/api/lifelines/assets")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 3
    assert any(asset["asset_id"] == "orbit_bridge_corridor" for asset in data["assets"])


def test_lifeline_monitor_endpoint_downlinks_high_confidence_disruption(tmp_path, monkeypatch):
    """Lifeline monitor should turn valid high-confidence before/after changes into downlinks."""
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(tmp_path / "runtime-data"))

    response = client.post(
        "/api/lifelines/monitor",
        json={
            "asset_id": "orbit_bridge_corridor",
            "baseline_frame": {
                "label": "before",
                "date": "2025-01-01",
                "source": "seeded_fixture",
                "asset_ref": "before.png",
            },
            "current_frame": {
                "label": "after",
                "date": "2025-01-15",
                "source": "seeded_fixture",
                "asset_ref": "after.png",
            },
            "candidate": {
                "event_type": "probable_access_obstruction",
                "severity": "high",
                "confidence": 0.88,
                "bbox": [0.2, 0.25, 0.65, 0.75],
                "civilian_impact": "public_mobility_disruption",
                "why": "The current frame shows a bridge approach obstruction.",
                "action": "downlink_now",
            },
            "task_text": "Before/after lifeline bridge disruption review.",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "orbit_lifeline_monitoring_v1"
    assert data["decision"]["action"] == "downlink_now"
    assert data["frames"]["pair_state"]["distinct_contextual_frames"] is True
    assert data["use_case"]["id"] == "civilian_lifeline_disruption"
    assert data["persistence"]["path"].endswith(".json")
    assert (tmp_path / "runtime-data" / "monitor-reports" / data["persistence"]["filename"]).exists()


def test_lifeline_monitor_endpoint_holds_downlink_without_frame_evidence(tmp_path, monkeypatch):
    """High-confidence candidates still need distinct before/after frame context."""
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(tmp_path / "runtime-data"))

    response = client.post(
        "/api/lifelines/monitor",
        json={
            "asset_id": "orbit_bridge_corridor",
            "baseline_frame": {"label": "before"},
            "current_frame": {"label": "after"},
            "candidate": {
                "event_type": "probable_access_obstruction",
                "severity": "high",
                "confidence": 0.88,
                "bbox": [0.2, 0.25, 0.65, 0.75],
                "civilian_impact": "public_mobility_disruption",
                "why": "The current frame shows a bridge approach obstruction.",
                "action": "downlink_now",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["frames"]["pair_state"]["distinct_contextual_frames"] is False
    assert data["decision"]["action"] == "defer"
    assert data["decision"]["priority"] == "needs_context"
    assert data["persistence"]["filename"].endswith(".json")


def test_lifeline_monitor_endpoint_rejects_unknown_asset_id():
    """Unknown seeded asset IDs should fail without running monitor work."""
    response = client.post(
        "/api/lifelines/monitor",
        json={"asset_id": "missing_asset", "candidate": {}},
    )

    assert response.status_code == 400
    assert "unknown lifeline asset_id" in response.json()["detail"]


def test_lifeline_evaluate_endpoint_returns_metrics():
    """Lifeline eval endpoint should expose schema and downlink recall metrics."""
    response = client.post(
        "/api/lifelines/evaluate",
        json={
            "cases": [
                {
                    "candidate": {
                        "event_type": "probable_large_scale_disruption",
                        "severity": "high",
                        "confidence": 0.93,
                        "bbox": [0.1, 0.1, 0.5, 0.6],
                        "civilian_impact": "shipping_or_aid_disruption",
                        "why": "Current frame shows severe access loss at the logistics hub.",
                        "action": "downlink_now",
                    },
                    "expected_action": "downlink_now",
                }
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["schema_valid"] == 1
    assert data["downlink_now_recall"] == 1.0


def test_lifeline_evaluate_endpoint_requires_cases():
    """Empty eval payloads should fail fast instead of producing misleading metrics."""
    response = client.post("/api/lifelines/evaluate", json={"cases": []})

    assert response.status_code == 422


def test_ice_snow_score_endpoint_returns_multispectral_contract():
    response = client.post(
        "/api/ice-snow/score",
        json={
            "frames": [
                {
                    "label": "2024-01-15",
                    "bands": {"green": 0.66, "swir1": 0.24, "nir": 0.49},
                    "valid_pixel_ratio": 0.9,
                    "cloud_pixel_ratio": 0.02,
                    "snow_ice_ratio": 0.42,
                    "snow_ice_scl_ratio": 0.30,
                },
                {
                    "label": "2024-02-15",
                    "bands": {"green": 0.67, "swir1": 0.23, "nir": 0.49},
                    "valid_pixel_ratio": 0.9,
                    "cloud_pixel_ratio": 0.02,
                    "snow_ice_ratio": 0.43,
                    "snow_ice_scl_ratio": 0.31,
                },
                {
                    "label": "2025-01-15",
                    "bands": {"green": 0.73, "swir1": 0.20, "nir": 0.52},
                    "valid_pixel_ratio": 0.88,
                    "cloud_pixel_ratio": 0.03,
                    "snow_ice_ratio": 0.57,
                    "snow_ice_scl_ratio": 0.39,
                },
                {
                    "label": "2025-02-15",
                    "bands": {"green": 0.74, "swir1": 0.20, "nir": 0.52},
                    "valid_pixel_ratio": 0.88,
                    "cloud_pixel_ratio": 0.03,
                    "snow_ice_ratio": 0.58,
                    "snow_ice_scl_ratio": 0.40,
                },
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["runtime_truth_mode"] == "replay"
    assert data["imagery_origin"] == "cached_api"
    assert data["scoring_basis"] == "multispectral_bands"
    assert data["use_case"] == "ice_snow_extent"
    assert "ndsi_increase" in data["reason_codes"]


def test_maritime_monitor_endpoint_returns_offline_investigation_plan(tmp_path, monkeypatch):
    """Maritime endpoint should return Orbit-native investigation planning."""
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(tmp_path / "runtime-data"))

    response = client.post(
        "/api/maritime/monitor",
        json={
            "lat": 29.92,
            "lon": 32.54,
            "timestamp": "2025-03-15",
            "task_text": "Review canal blockage and vessel queueing near a shipping lane.",
            "anomaly_description": "dense vessel queue near a narrow channel",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "orbit_maritime_monitoring_v1"
    assert data["use_case"]["id"] == "maritime_activity"
    assert data["stac"]["disabled"] is True
    assert len(data["investigation"]["directions"]) == 4
    assert data["orbit_integration"]["separate_streamlit_app_required"] is False
    assert (tmp_path / "runtime-data" / "monitor-reports" / data["persistence"]["filename"]).exists()


def test_maritime_monitor_endpoint_validates_coordinates():
    """Invalid target coordinates should fail before any provider work starts."""
    response = client.post(
        "/api/maritime/monitor",
        json={
            "lat": 120,
            "lon": 32.54,
            "timestamp": "2025-03-15",
        },
    )

    assert response.status_code == 422

# ---------------------------------------------------------------------------
# Timelapse endpoint tests
# ---------------------------------------------------------------------------

def test_timelapse_generate_endpoint_returns_webm():
    """Timelapse generation endpoint must return base64 WEBM structure."""
    with patch("core.timelapse._read_cache", return_value=None), \
         patch("core.timelapse._write_cache"), \
         patch("core.timelapse._fetch_gee_frames") as mock_fetch:
        import numpy as np
        mock_frame = np.zeros((960, 1280, 3), dtype=np.uint8)
        mock_fetch.return_value = [(mock_frame, "iso1"), (mock_frame.copy(), "iso2")]
        
        response = client.post(
            "/api/timelapse/generate",
            json={
                "bbox": [-60.50, -3.50, -60.40, -3.40],
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "steps": 5
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "video_b64" in data
        assert "frames_count" in data
        assert data["format"] == "webm"
        assert data["provenance"]["kind"] == "live_fetch"
        assert data["video_b64"].startswith("data:video/webm;base64,")


def test_analysis_timelapse_endpoint_returns_text_evaluation():
    """Agent Video Evaluation endpoint must return analysis text."""
    response = client.post(
        "/api/analysis/timelapse",
        json={
            "bbox": [-60.50, -3.50, -60.40, -3.40]
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "analysis" in data
    assert isinstance(data["analysis"], str)
    assert len(data["analysis"]) > 0

def test_analysis_timelapse_endpoint_validates_bbox():
    """Agent Video Evaluation endpoint validates bbox field."""
    response = client.post(
        "/api/analysis/timelapse",
        json={
            "bbox": [-60.50, -3.50]  # Missing coords
        }
    )

    assert response.status_code == 422


def test_timelapse_generate_endpoint_validates_bbox_shape():
    """Timelapse generation endpoint rejects malformed bbox payloads before provider work."""
    response = client.post(
        "/api/timelapse/generate",
        json={
            "bbox": [-60.50, -3.50],
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "steps": 5,
        },
    )

    assert response.status_code == 422


def test_timelapse_generate_endpoint_validates_date_order():
    """Timelapse generation endpoint rejects reversed date windows."""
    response = client.post(
        "/api/timelapse/generate",
        json={
            "bbox": [-60.50, -3.50, -60.40, -3.40],
            "start_date": "2025-01-01",
            "end_date": "2024-12-31",
            "steps": 5,
        },
    )

    assert response.status_code == 422


def test_mission_start_endpoint_validates_bbox_order():
    """Mission start rejects bbox bounds that would break grid generation."""
    response = client.post(
        "/api/mission/start",
        json={
            "task_text": "Scan invalid area",
            "bbox": [-60.40, -3.50, -60.50, -3.40],
        },
    )

    assert response.status_code == 422


def test_mission_start_endpoint_validates_date_order():
    """Mission start rejects reversed temporal windows."""
    response = client.post(
        "/api/mission/start",
        json={
            "task_text": "Scan reversed window",
            "bbox": [-60.50, -3.50, -60.40, -3.40],
            "start_date": "2025-01-01",
            "end_date": "2024-01-01",
        },
    )

    assert response.status_code == 422


def test_vlm_endpoint_validates_bbox_shape():
    """VLM helper endpoints share the strict bbox validator."""
    response = client.post(
        "/api/vlm/caption",
        json={
            "bbox": [-60.50, -3.50],
        },
    )

    assert response.status_code == 422


def test_vlm_grounding_endpoint_requires_operator_prompt():
    """Grounding should fail on blank prompt text before returning vague fallback boxes."""
    response = client.post(
        "/api/vlm/grounding",
        json={
            "bbox": [-60.50, -3.50, -60.40, -3.40],
            "prompt": "   ",
        },
    )

    assert response.status_code == 422


def test_vlm_vqa_endpoint_requires_operator_question():
    """VQA should fail on blank question text before returning vague fallback answers."""
    response = client.post(
        "/api/vlm/vqa",
        json={
            "bbox": [-60.50, -3.50, -60.40, -3.40],
            "question": "",
        },
    )

    assert response.status_code == 422


def test_settings_credentials_reject_blank_values():
    """Credential writes should not replace a local secret file with blank values."""
    response = client.post(
        "/api/settings/credentials",
        json={
            "client_id": "   ",
            "client_secret": "secret",
        },
    )

    assert response.status_code == 422


def test_cell_imagery_rejects_unsupported_cell_ids():
    """Imagery endpoint should not silently resolve unknown cell IDs to 0,0."""
    response = client.get("/api/imagery/cell/not-a-cell")

    assert response.status_code == 400
    assert response.json()["error"] == "Unsupported or invalid cell_id"


def test_depth_status_defaults_to_disabled(monkeypatch):
    clear_depth_anything_runtime_override()
    monkeypatch.delenv("DEPTH_ANYTHING_V3_ENABLED", raising=False)
    monkeypatch.delenv("DEPTH_ANYTHING_V3_MODEL", raising=False)
    monkeypatch.delenv("DEPTH_ANYTHING_V3_DEVICE", raising=False)

    response = client.get("/api/depth/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["feature"] == "depth_anything_v3"
    assert payload["enabled"] is False
    assert payload["available"] is False
    assert payload["model_id"]
    assert payload["package"] == "depth_anything_3"
    assert payload["requested_device"] == "auto"
    assert payload["device"] in {"cpu", "cuda"}


def test_depth_toggle_is_runtime_scoped_and_nonfatal():
    clear_depth_anything_runtime_override()

    response = client.post("/api/depth/settings", json={"enabled": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["source"] == "runtime"
    assert "install_hint" in payload

    response = client.post("/api/depth/settings", json={"enabled": False})
    assert response.status_code == 200
    assert response.json()["enabled"] is False

    clear_depth_anything_runtime_override()


def test_depth_estimate_returns_clear_error_when_disabled():
    clear_depth_anything_runtime_override()

    response = client.post("/api/depth/estimate", json={"image_b64": "not-image"})

    assert response.status_code == 409
    payload = response.json()
    assert "Depth Anything V3 is disabled" in payload["error"]
    assert payload["status"]["enabled"] is False


def test_depth_estimate_rejects_malformed_image_before_model_load(monkeypatch):
    clear_depth_anything_runtime_override()
    monkeypatch.setenv("DEPTH_ANYTHING_V3_ENABLED", "true")

    from core import depth_anything

    monkeypatch.setattr(depth_anything, "_package_available", lambda: True)

    def fail_model_load(config):
        raise AssertionError("model should not load before image payload validation")

    monkeypatch.setattr(depth_anything, "_get_model", fail_model_load)

    response = client.post("/api/depth/estimate", json={"image_b64": "not-image"})

    assert response.status_code == 400
    assert "valid base64 image data" in response.json()["error"]

    clear_depth_anything_runtime_override()


def test_runtime_reset_endpoint_clears_mutable_runtime_state(tmp_path, monkeypatch):
    """Runtime reset endpoint should clear alerts, missions, bus state, gallery, and metrics."""
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(tmp_path / "alerts.sqlite"))
    monkeypatch.setenv("AGENT_BUS_PATH", str(tmp_path / "agent_bus.sqlite"))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))

    from core.agent_bus import init_bus, post_message, upsert_pin
    from core.gallery import add_gallery_item
    from core.metrics import seed_metrics_summary
    from core.mission import start_mission
    from core.queue import init_db, push_alert

    init_db(reset=True)
    init_bus(reset=True)

    start_mission("Seeded runtime state")
    post_message(
        sender="satellite",
        recipient="ground",
        msg_type="flag",
        cell_id="sq_-10.0_-63.0",
        payload={"note": "Runtime reset test."},
    )
    upsert_pin(
        pin_type="satellite",
        cell_id="sq_-10.0_-63.0",
        lat=-10.0,
        lng=-63.0,
        label="SAT ◆ sq_-10.0",
        note="Reset me.",
    )
    push_alert(
        event_id="evt_reset",
        region_id="replay",
        cell_id="sq_-10.0_-63.0",
        change_score=0.82,
        confidence=0.94,
        priority="critical",
        reason_codes=["ndvi_drop", "soil_exposure_spike"],
        payload_bytes=123,
        observation_source="replay",
    )
    add_gallery_item(
        cell_id="sq_-10.0_-63.0",
        lat=-10.0,
        lng=-63.0,
        severity="critical",
        change_score=0.82,
        mission_id=1,
        fetch_thumb=False,
        context_thumb="data:image/png;base64,stub",
    )
    seed_metrics_summary(
        {
            "total_cells_scanned": 4,
            "total_alerts_emitted": 1,
            "total_cycles_completed": 1,
        }
    )

    response = client.post("/api/runtime/reset")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "reset"
    assert payload["before"]["alerts"] == 1
    assert payload["before"]["agent_messages"] == 1
    assert payload["before"]["map_pins"] == 1
    assert payload["before"]["gallery_items"] == 1
    assert payload["before"]["missions"] == 1
    assert payload["before"]["metrics_total_cells_scanned"] == 4
    assert payload["before"]["metrics_total_alerts_emitted"] == 1
    assert payload["after"]["alerts"] == 0
    assert payload["after"]["agent_messages"] == 0
    assert payload["after"]["map_pins"] == 0
    assert payload["after"]["gallery_items"] == 0
    assert payload["after"]["missions"] == 0
    assert payload["after"]["metrics_total_cells_scanned"] == 0
    assert payload["after"]["metrics_total_alerts_emitted"] == 0


def test_map_pin_endpoint_rejects_out_of_range_coordinates():
    response = client.post(
        "/api/map/pins",
        json={"lat": 91.0, "lng": -60.0, "note": "invalid latitude"},
    )

    assert response.status_code == 422

    response = client.post(
        "/api/map/pins",
        json={"lat": -3.0, "lng": -181.0, "note": "invalid longitude"},
    )

    assert response.status_code == 422
