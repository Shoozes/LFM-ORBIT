from core.wildfire_smoke import score_wildfire_smoke_assist, summarize_wildfire_frame


def _frame(
    label: str,
    *,
    blue: float,
    green: float,
    red: float,
    nir: float,
    swir1: float,
    swir2: float,
    cloud: float = 0.02,
    cloud_probability: float = 0.02,
    snow_ice: float = 0.0,
) -> dict:
    return {
        "label": label,
        "bands": {
            "blue": blue,
            "green": green,
            "red": red,
            "nir": nir,
            "swir1": swir1,
            "swir2": swir2,
        },
        "valid_pixel_ratio": 0.9,
        "scl_cloud_ratio": cloud,
        "cloud_probability": cloud_probability,
        "scl_snow_ratio": snow_ice,
    }


def test_scl_cloud_white_rgb_defers_as_cloud_like_plume():
    frames = [
        _frame("baseline", blue=0.50, green=0.49, red=0.48, nir=0.45, swir1=0.30, swir2=0.26),
        _frame(
            "active",
            blue=0.80,
            green=0.79,
            red=0.78,
            nir=0.65,
            swir1=0.50,
            swir2=0.48,
            cloud=0.90,
            cloud_probability=0.80,
        ),
    ]

    result = score_wildfire_smoke_assist(frames)

    assert result["target_action"] == "defer"
    assert result["cloud_likelihood"] > result["smoke_likelihood"]
    assert "cloud_like_white_plume" in result["reason_codes"]
    assert "defer_smoke_cloud_ambiguity" in result["reason_codes"]


def test_blue_green_haze_low_cloud_returns_review_candidate():
    frames = [
        _frame("baseline", blue=0.10, green=0.10, red=0.08, nir=0.50, swir1=0.18, swir2=0.18),
        _frame("active", blue=0.23, green=0.22, red=0.10, nir=0.43, swir1=0.19, swir2=0.20),
    ]

    result = score_wildfire_smoke_assist(frames)

    assert result["target_action"] == "review"
    assert result["smoke_likelihood"] >= 0.60
    assert result["cloud_likelihood"] < 0.45
    assert "smoke_plume_candidate" in result["reason_codes"]


def test_positive_dnbr_smoke_and_hotspot_downlinks():
    frames = [
        _frame("baseline", blue=0.11, green=0.11, red=0.08, nir=0.56, swir1=0.16, swir2=0.12),
        _frame("active", blue=0.23, green=0.21, red=0.10, nir=0.34, swir1=0.22, swir2=0.28),
    ]

    result = score_wildfire_smoke_assist(frames, hotspot_context={"viirs_confidence": "high"})

    assert result["target_action"] == "downlink_now"
    assert result["burn_likelihood"] >= 0.55
    assert result["hotspot_support"] == 0.9
    assert "smoke_with_burn_support" in result["reason_codes"]
    assert "hotspot_support" in result["reason_codes"]


def test_proxy_source_caps_confidence_and_does_not_confirm_active_fire():
    frames = [
        _frame("baseline", blue=0.11, green=0.11, red=0.08, nir=0.56, swir1=0.16, swir2=0.12),
        _frame("active", blue=0.23, green=0.21, red=0.10, nir=0.34, swir1=0.22, swir2=0.28),
    ]

    result = score_wildfire_smoke_assist(
        frames,
        hotspot_context={"confidence": 95},
        runtime_truth_mode="proxy",
        imagery_origin="fallback_imagery",
        observation_source="simsat_proxy",
    )

    assert result["final_confidence"] <= 0.25
    assert result["target_action"] == "review"
    assert "proxy_or_fallback_source_capped" in result["reason_codes"]


def test_missing_required_bands_abstains():
    summary = summarize_wildfire_frame({"label": "active", "bands": {"red": 0.1, "nir": 0.3, "swir2": 0.2}})

    assert summary["accepted"] is False
    assert "missing_required_bands" in summary["reason_codes"]

    result = score_wildfire_smoke_assist([{"label": "active", "bands": {"red": 0.1, "nir": 0.3, "swir2": 0.2}}])

    assert result["target_action"] == "defer"
    assert result["final_confidence"] <= 0.25
    assert "missing_required_bands" in result["reason_codes"]


def test_snow_ice_white_rgb_is_not_smoke():
    frames = [
        _frame("baseline", blue=0.62, green=0.63, red=0.61, nir=0.48, swir1=0.30, swir2=0.24, snow_ice=0.70),
        _frame(
            "active",
            blue=0.72,
            green=0.73,
            red=0.71,
            nir=0.50,
            swir1=0.31,
            swir2=0.25,
            cloud=0.50,
            cloud_probability=0.30,
            snow_ice=0.80,
        ),
    ]

    result = score_wildfire_smoke_assist(frames)

    assert result["target_action"] == "defer"
    assert "snow_ice_ambiguity_not_smoke" in result["reason_codes"]
    assert "smoke_with_burn_support" not in result["reason_codes"]
