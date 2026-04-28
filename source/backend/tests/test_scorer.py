import pytest
from core.scorer import score_cell_change, _to_window_payload
from core.config import DETECTION
from unittest.mock import patch

def test_to_window_payload_calculates_all_indices():
    mock_window = {
        "label": "2024-08",
        "quality": 0.95,
        "flags": [],
        "bands": {
            "nir": 0.65,
            "red": 0.08,
            "swir": 0.15
        }
    }
    payload = _to_window_payload(mock_window)

    assert "ndvi" in payload
    assert "evi2" in payload
    assert "nbr" in payload
    assert "ndmi" in payload
    assert "soil_ratio" in payload

    # Check baseline index calculations hold
    assert payload["soil_ratio"] > 0
    assert payload["ndvi"] > 0
    assert payload["label"] == "2024-08"

@patch("core.scorer.load_temporal_observations")
def test_score_cell_healthy_vegetation(mock_loader):
    # Setup mock to return two healthy arrays (no change)
    healthy_bands = {"nir": 0.65, "red": 0.05, "swir": 0.10}
    mock_loader.return_value = {
        "source": "mock",
        "before": {"label": "Before", "quality": 1.0, "flags": [], "bands": healthy_bands.copy()},
        "after": {"label": "After", "quality": 1.0, "flags": [], "bands": healthy_bands.copy()}
    }

    score = score_cell_change("mock_cell")

    assert score["change_score"] == 0.0
    assert "stable_vegetation" in score["reason_codes"]
    assert "suspected_canopy_loss" not in score["reason_codes"]
    assert score["confidence"] > 0.0

@patch("core.scorer.load_temporal_observations")
def test_score_cell_single_index_penalty(mock_loader):
    # Setup mock where NBR drops due to moisture change but vegetation indices are stable
    before_bands = {"nir": 0.65, "red": 0.05, "swir": 0.10}

    # SWIR spikes (causes NBR drop), but RED/NIR stay identical (NDVI/EVI2 stable)
    after_bands = {"nir": 0.65, "red": 0.05, "swir": 0.35}

    mock_loader.return_value = {
        "source": "mock",
        "before": {"label": "Before", "quality": 1.0, "flags": [], "bands": before_bands},
        "after": {"label": "After", "quality": 1.0, "flags": [], "bands": after_bands}
    }

    score = score_cell_change("mock_cell")

    assert "nbr_drop" in score["reason_codes"]
    assert "multi_index_consensus" not in score["reason_codes"]

    # Because there's no multi_index_consensus, the change_score remains too low
    # to trigger suspected_canopy_loss, perfectly validating the intent
    assert "suspected_canopy_loss" not in score["reason_codes"]

@patch("core.scorer.load_temporal_observations")
def test_score_cell_structural_deforestation(mock_loader):
    before_bands = {"nir": 0.65, "red": 0.05, "swir": 0.20}

    # Complete structural clearance: SWIR overtakes NIR
    after_bands = {"nir": 0.30, "red": 0.35, "swir": 0.60}

    mock_loader.return_value = {
        "source": "mock",
        "before": {"label": "Before", "quality": 1.0, "flags": [], "bands": before_bands},
        "after": {"label": "After", "quality": 1.0, "flags": [], "bands": after_bands}
    }

    score = score_cell_change("mock_cell")

    assert "ndvi_drop" in score["reason_codes"]
    assert "evi2_drop" in score["reason_codes"]
    assert "ndmi_drop" in score["reason_codes"]
    assert "soil_exposure_spike" in score["reason_codes"]
    assert "multi_index_consensus" in score["reason_codes"]

    assert score["change_score"] >= DETECTION.critical_severity_threshold


@patch("core.scorer.load_temporal_observations")
def test_score_cell_cloud_degraded_window_abstains_even_with_large_raw_change(mock_loader):
    before_bands = {"nir": 0.65, "red": 0.05, "swir": 0.20}
    after_bands = {"nir": 0.20, "red": 0.35, "swir": 0.70}

    mock_loader.return_value = {
        "source": "mock",
        "before": {"label": "Before", "quality": 1.0, "flags": [], "bands": before_bands},
        "after": {"label": "After", "quality": 0.2, "flags": ["cloud_degraded"], "bands": after_bands}
    }

    score = score_cell_change("mock_cell")

    assert score["raw_change_score"] >= DETECTION.critical_severity_threshold
    assert score["change_score"] == 0.0
    assert score["confidence"] <= 0.25
    assert "quality_gate_failed" in score["reason_codes"]
    assert "abstained_cloud_coverage" in score["reason_codes"]
    assert "suspected_canopy_loss" not in score["reason_codes"]
