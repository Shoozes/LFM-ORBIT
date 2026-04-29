from core.temporal_use_cases import classify_temporal_use_case, list_temporal_use_cases


def test_temporal_use_case_catalog_includes_required_examples():
    cases = {case["id"]: case for case in list_temporal_use_cases()}

    for use_case_id in (
        "wildfire",
        "maritime_activity",
        "civilian_lifeline_disruption",
        "ice_snow_extent",
        "ice_cap_growth",
        "volcanic_surface_change",
    ):
        assert use_case_id in cases
        assert cases[use_case_id]["temporal_methods"]
        assert cases[use_case_id]["examples"]


def test_temporal_use_case_classifier_handles_mission_text():
    wildfire = classify_temporal_use_case(
        {
            "task_text": "Scan this region for wildfire burn scars and smoke plume changes.",
            "reason_codes": ["burn_scar", "nbr_drop"],
        }
    )
    maritime = classify_temporal_use_case(
        {
            "task_text": "Review canal blockage and maritime vessel queueing near the port for AIS mismatch.",
            "reason_codes": ["ship_wake", "ais_mismatch", "channel_blockage"],
        }
    )
    ice = classify_temporal_use_case(
        {
            "task_text": "Compare glacier and ice cap growth across same-season frames.",
            "reason_codes": ["ice_extent_growth", "albedo_change"],
        }
    )
    ice_snow = classify_temporal_use_case(
        {
            "task_text": "Review Greenland snow versus clouds with Sentinel-2 L2A NDSI and SCL support.",
            "reason_codes": ["ndsi_increase", "multi_frame_persistence", "cloud_rejected"],
        }
    )
    lifeline = classify_temporal_use_case(
        {
            "task_text": "Before after review of bridge access obstruction affecting public mobility.",
            "reason_codes": ["probable_access_obstruction", "public_mobility_disruption"],
        }
    )
    traffic = classify_temporal_use_case(
        {
            "task_text": "Run a close transportation mix scan over the Florida I-4 and SR-536 interchange near Walt Disney World for road access and public mobility.",
        }
    )
    highway82_wildfire = classify_temporal_use_case(
        {
            "task_text": "Review the Highway 82 wildfire near Atkinson and Waynesville, Georgia for smoke, burn scar, and vegetation stress.",
        }
    )
    future_fire_watch = classify_temporal_use_case(
        {
            "task_text": "Watch the SPC Day 2 critical fire-weather corridor across eastern New Mexico and western Texas for new smoke plume or burn-scar evidence.",
        }
    )
    mauna_loa = classify_temporal_use_case(
        {
            "task_text": "Review Mauna Loa lava flow and post eruption volcanic surface change in SWIR frames.",
            "reason_codes": ["lava_flow", "post_eruption_recovery"],
            "target_category": "volcanic_surface_change",
        }
    )
    explicit_volcanic = classify_temporal_use_case({}, requested_use_case_id="volcanic_surface_change")

    assert wildfire["id"] == "wildfire"
    assert maritime["id"] == "maritime_activity"
    assert ice["id"] == "ice_cap_growth"
    assert ice_snow["id"] == "ice_snow_extent"
    assert lifeline["id"] == "civilian_lifeline_disruption"
    assert traffic["id"] == "civilian_lifeline_disruption"
    assert highway82_wildfire["id"] == "wildfire"
    assert future_fire_watch["id"] == "wildfire"
    assert mauna_loa["id"] == "volcanic_surface_change"
    assert explicit_volcanic["target_category"] == "volcanic_surface_change"
