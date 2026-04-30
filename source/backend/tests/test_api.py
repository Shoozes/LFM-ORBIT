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
    assert "note" in data


def test_analysis_status_endpoint_surfaces_manifest_metadata():
    """Analysis status should surface resolved manifest/repo details for the optional model."""
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
            "readme_path": "C:/tmp/README.md",
            "readme_present": True,
        },
    ):
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
    assert model["readme_path"] == "C:/tmp/README.md"
    assert model["readme_present"] is True


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
    """SimSat must remain first in the provider chain for judge demos."""
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
    assert payload["actions"][0]["name"] == "start_mission_pack"
    assert payload["actions"][0]["status"] == "ok"
    assert payload["actions"][0]["result"]["pack_id"] == "maritime_suez"


def test_ground_agent_chat_cautions_visual_evidence_candidates():
    response = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "Can CV find boats or dark smoke in the bbox?"}]},
    )

    assert response.status_code == 200
    reply = response.json()["reply"].lower()
    assert "candidate evidence" in reply
    assert "fallback vision never confirms" in reply


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
