"""Tests for API endpoint responses.

These tests verify that all REST endpoints return expected data
and comply with the locked contract schemas.
"""
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_endpoint_returns_ok_status():
    """Health endpoint must return ok status."""
    response = client.get("/api/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "ok"
    assert "region_id" in data
    assert "display_name" in data
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
    assert "region_id" in data
    assert "total_cycles_completed" in data
    assert "total_cells_scanned" in data
    assert "total_alerts_emitted" in data
    assert "total_payload_bytes" in data
    assert "total_bandwidth_saved_mb" in data
    assert "latest_discard_ratio" in data
    assert "flagged_examples" in data
    
    assert isinstance(data["flagged_examples"], list)



def test_health_endpoint_shows_observation_mode():
    """Health endpoint must include observation mode for transparency."""
    response = client.get("/api/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "observation_mode" in data
    # Observation mode should be a non-empty string describing the loader
    assert isinstance(data["observation_mode"], str)
    assert len(data["observation_mode"]) > 0


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

# ---------------------------------------------------------------------------
# Timelapse endpoint tests
# ---------------------------------------------------------------------------

from unittest.mock import patch

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
    
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
