from core.temporal_use_cases import classify_temporal_use_case, list_temporal_use_cases


def test_temporal_use_case_catalog_includes_required_examples():
    cases = {case["id"]: case for case in list_temporal_use_cases()}

    for use_case_id in ("wildfire", "maritime_activity", "civilian_lifeline_disruption", "ice_cap_growth"):
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
    florida_wildfire = classify_temporal_use_case(
        {
            "task_text": "Review dry Florida wildfire conditions around Big Cypress and Alligator Alley for smoke, burn scar, and vegetation stress.",
        }
    )

    assert wildfire["id"] == "wildfire"
    assert maritime["id"] == "maritime_activity"
    assert ice["id"] == "ice_cap_growth"
    assert lifeline["id"] == "civilian_lifeline_disruption"
    assert traffic["id"] == "civilian_lifeline_disruption"
    assert florida_wildfire["id"] == "wildfire"
