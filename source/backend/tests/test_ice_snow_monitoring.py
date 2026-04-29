import numpy as np
import pytest

from core.ice_snow_monitoring import score_ice_snow_extent, summarize_ice_snow_frame


def _frame(label: str, snow_ratio: float, ndsi: float, *, cloud: float = 0.02) -> dict:
    green = 0.62 + ndsi * 0.12
    swir1 = green * (1 - ndsi) / (1 + ndsi)
    return {
        "label": label,
        "bands": {
            "green": green,
            "swir1": swir1,
            "nir": 0.48,
        },
        "valid_pixel_ratio": 0.92 - cloud,
        "cloud_pixel_ratio": cloud,
        "snow_ice_ratio": snow_ratio,
        "snow_ice_scl_ratio": max(0.0, snow_ratio - 0.12),
        "water_ratio": 0.04,
    }


def test_score_ice_snow_extent_reports_ndsi_increase_and_provenance():
    frames = [
        _frame("2024-01-15", 0.40, 0.46),
        _frame("2024-02-15", 0.42, 0.47),
        _frame("2024-03-15", 0.43, 0.48),
        _frame("2025-01-15", 0.55, 0.57),
        _frame("2025-02-15", 0.58, 0.59),
        _frame("2025-03-15", 0.60, 0.60),
        _frame("2025-04-15", 0.60, 0.60, cloud=0.50),
    ]

    result = score_ice_snow_extent(frames)

    assert result["runtime_truth_mode"] == "replay"
    assert result["imagery_origin"] == "cached_api"
    assert result["scoring_basis"] == "multispectral_bands"
    assert result["use_case"] == "ice_snow_extent"
    assert result["accepted_frames"] == 6
    assert result["rejected_cloud_frames"] == 1
    assert result["baseline_snow_ice_ratio"] == pytest.approx(0.4167, abs=0.0001)
    assert result["current_snow_ice_ratio"] == pytest.approx(0.5767, abs=0.0001)
    assert result["delta_ratio"] == pytest.approx(0.16, abs=0.0001)
    assert "ndsi_increase" in result["reason_codes"]
    assert "multi_frame_persistence" in result["reason_codes"]
    assert "snow_ice_scl_support" in result["reason_codes"]
    assert "cloud_rejected" in result["reason_codes"]
    assert result["confidence"] > 0.7


def test_rgb_only_frame_abstains_instead_of_fabricating_ndsi():
    summary = summarize_ice_snow_frame(
        {
            "label": "rgb-only",
            "bands": {"red": 0.4, "green": 0.8, "blue": 0.7},
            "valid_pixel_ratio": 0.95,
        }
    )

    assert summary["accepted"] is False
    assert summary["ndsi"] is None
    assert summary["snow_ice_ratio"] == 0.0
    assert "missing_green_or_swir1_band" in summary["reason_codes"]


def test_array_frame_uses_scl_to_reject_clouds_and_support_snow_ice():
    green = np.full((4, 4), 0.72)
    swir1 = np.full((4, 4), 0.18)
    nir = np.full((4, 4), 0.45)
    scl = np.full((4, 4), 11)
    scl[0:2, :] = 9

    summary = summarize_ice_snow_frame(
        {
            "label": "cloudy-snow",
            "bands": {"B03": green, "B11": swir1, "B08": nir},
            "scl": scl,
        }
    )

    assert summary["accepted"] is False
    assert summary["cloud_pixel_ratio"] == 0.5
    assert "insufficient_valid_pixels" in summary["reason_codes"]
    assert "cloud_rejected" in summary["reason_codes"]
    assert summary["snow_ice_scl_ratio"] == 0.5
    assert summary["snow_ice_ratio"] == 1.0


def test_short_or_cloud_blocked_sequence_defers_without_positive_label():
    result = score_ice_snow_extent(
        [
            _frame("2024-01-15", 0.46, 0.50, cloud=0.60),
            _frame("2025-01-15", 0.60, 0.59, cloud=0.55),
        ]
    )

    assert result["accepted_frames"] == 0
    assert result["change_score"] == 0.0
    assert result["target_action"] == "defer"
    assert "insufficient_accepted_frames" in result["reason_codes"]


def test_two_clear_frames_still_defer_until_minimum_persistence_is_met():
    result = score_ice_snow_extent(
        [
            _frame("2024-01-15", 0.30, 0.42),
            _frame("2025-01-15", 0.58, 0.61),
        ],
        min_accepted_frames=3,
    )

    assert result["accepted_frames"] == 2
    assert result["target_action"] == "defer"
    assert result["change_score"] == 0.0
    assert result["raw_change_score"] > 0.0
    assert "insufficient_accepted_frames" in result["reason_codes"]
    assert "ndsi_increase" not in result["reason_codes"]


def test_scalar_scl_numeric_class_fractions_are_supported():
    summary = summarize_ice_snow_frame(
        {
            "label": "scl-fractions",
            "bands": {"green": 0.70, "swir1": 0.20, "nir": 0.46},
            "valid_pixel_ratio": 0.88,
            "scl_class_fractions": {
                "11": 0.34,
                "6": 0.12,
                "8": 0.03,
                "9": 0.02,
                "10": 0.01,
            },
        }
    )

    assert summary["accepted"] is True
    assert summary["snow_ice_scl_ratio"] == 0.34
    assert summary["water_ratio"] == 0.12
    assert summary["cloud_pixel_ratio"] == 0.06
