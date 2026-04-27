from core.maritime_monitoring import (
    build_cardinal_investigation_plan,
    build_maritime_monitor_report,
    bbox_from_point,
    deduplicate_stac_items,
    offset_point,
)


def test_bbox_from_point_builds_wgs84_box():
    bbox = bbox_from_point(29.92, 32.54, 10.0)

    assert len(bbox) == 4
    assert bbox[0] < 32.54 < bbox[2]
    assert bbox[1] < 29.92 < bbox[3]


def test_offset_point_moves_in_cardinal_directions():
    north_lat, north_lon = offset_point(29.92, 32.54, "N", 10.0)
    east_lat, east_lon = offset_point(29.92, 32.54, "E", 10.0)

    assert north_lat > 29.92
    assert abs(north_lon - 32.54) < 0.01
    assert east_lon > 32.54
    assert abs(east_lat - 29.92) < 0.01


def test_deduplicate_stac_items_prefers_spatial_consistency_then_date_order():
    items = [
        {
            "id": "far_same_day",
            "bbox": [31.0, 29.0, 31.2, 29.2],
            "properties": {"datetime": "2025-03-15T10:00:00Z", "eo:cloud_cover": 1},
            "assets": {"visual": {"href": "https://example.test/far.tif"}},
        },
        {
            "id": "near_same_day",
            "bbox": [32.50, 29.88, 32.58, 29.96],
            "properties": {"datetime": "2025-03-15T09:00:00Z", "eo:cloud_cover": 20},
            "assets": {"visual": {"href": "https://example.test/near.tif"}},
        },
        {
            "id": "newer_day",
            "bbox": [32.51, 29.89, 32.57, 29.95],
            "properties": {"datetime": "2025-03-17T09:00:00Z", "eo:cloud_cover": 10},
            "assets": {"visual": {"href": "https://example.test/newer.tif"}},
        },
    ]

    deduped = deduplicate_stac_items(items, max_items=4, lat=29.92, lon=32.54)

    assert [item["item_id"] for item in deduped] == ["newer_day", "near_same_day"]
    assert deduped[0]["visual_href"] == "https://example.test/newer.tif"


def test_cardinal_investigation_plan_has_tool_contract_inputs():
    plan = build_cardinal_investigation_plan(
        lat=29.92,
        lon=32.54,
        timestamp="2025-03-15",
        anomaly_description="vessel congestion near canal entrance",
    )

    assert [item["direction"] for item in plan] == ["N", "E", "S", "W"]
    assert all(item["recommended_action"] == "explore_direction" for item in plan)
    assert all(item["bbox"] for item in plan)
    assert all(item["analysis_questions"] for item in plan)


def test_build_maritime_monitor_report_is_offline_by_default():
    report = build_maritime_monitor_report(
        lat=29.92,
        lon=32.54,
        timestamp="2025-03-15",
        task_text="Review canal blockage and maritime vessel queueing near the anchorage.",
        anomaly_description="large vessel queue near a narrow channel",
    )

    assert report["mode"] == "orbit_maritime_monitoring_v1"
    assert report["use_case"]["id"] == "maritime_activity"
    assert report["stac"]["disabled"] is True
    assert report["orbit_integration"]["external_vlm_api_required"] is False
    assert len(report["investigation"]["directions"]) == 4
    assert "submit_finding(title, description, evidence_images, confidence)" in report["investigation"]["tool_contract"]
