from core.lifeline_monitoring import (
    check_lifeline_acceptance,
    build_lifeline_monitor_report,
    evaluate_lifeline_predictions,
    list_lifeline_assets,
    normalize_lifeline_candidate,
    score_lifeline_candidate,
)


def _high_confidence_disruption():
    return {
        "event_type": "probable_access_obstruction",
        "severity": "high",
        "confidence": 0.91,
        "bbox": [0.24, 0.30, 0.62, 0.71],
        "civilian_impact": "public_mobility_disruption",
        "why": "The current frame shows a localized obstruction on the bridge approach.",
        "action": "downlink_now",
    }


def test_lifeline_asset_catalog_filters_seed_assets():
    assets = list_lifeline_assets(category="water")

    assert len(assets) == 1
    assert assets[0]["asset_id"] == "orbit_water_service_node"
    assert assets[0]["bbox"]


def test_no_event_candidate_is_forced_to_safe_discard():
    candidate = normalize_lifeline_candidate(
        {
            "event_type": "no_event",
            "severity": "high",
            "confidence": 0.99,
            "bbox": [0.1, 0.1, 0.9, 0.9],
            "civilian_impact": "public_mobility_disruption",
            "why": "No visible change.",
            "action": "downlink_now",
        }
    )

    assert candidate["event_type"] == "no_event"
    assert candidate["severity"] == "low"
    assert candidate["civilian_impact"] == "no_material_impact"
    assert candidate["action"] == "discard"
    assert score_lifeline_candidate(candidate)["action"] == "discard"


def test_high_confidence_material_candidate_downlinks_now():
    decision = score_lifeline_candidate(_high_confidence_disruption())

    assert decision["action"] == "downlink_now"
    assert decision["priority"] == "critical"
    assert decision["downlink_now"] is True


def test_malformed_bbox_fails_schema_and_discards():
    decision = score_lifeline_candidate(
        {
            "event_type": "probable_access_obstruction",
            "severity": "high",
            "confidence": 0.9,
            "bbox": [0.7, 0.2, 0.4, 0.9],
            "civilian_impact": "public_mobility_disruption",
            "why": "bbox is reversed",
            "action": "downlink_now",
        }
    )

    assert decision["action"] == "discard"
    assert decision["candidate"]["schema_valid"] is False
    assert decision["candidate"]["bbox_valid"] is False


def test_build_lifeline_report_keeps_before_after_frames():
    report = build_lifeline_monitor_report(
        asset_id="orbit_bridge_corridor",
        candidate=_high_confidence_disruption(),
        baseline_frame={
            "label": "before",
            "date": "2025-01-01",
            "source": "seeded_fixture",
            "asset_ref": "baseline.png",
        },
        current_frame={
            "label": "after",
            "date": "2025-01-15",
            "source": "seeded_fixture",
            "asset_ref": "current.png",
        },
        task_text="Before/after lifeline bridge disruption review.",
    )

    assert report["mode"] == "orbit_lifeline_monitoring_v1"
    assert report["asset"]["asset_id"] == "orbit_bridge_corridor"
    assert report["frames"]["pair_state"]["distinct_contextual_frames"] is True
    assert report["frames"]["pair_state"]["asset_pair_available"] is True
    assert report["decision"]["action"] == "downlink_now"
    assert report["use_case"]["id"] == "civilian_lifeline_disruption"


def test_lifeline_report_holds_downlink_without_distinct_frames():
    report = build_lifeline_monitor_report(
        asset_id="orbit_bridge_corridor",
        candidate=_high_confidence_disruption(),
        baseline_frame={"label": "before"},
        current_frame={"label": "after"},
    )

    assert report["frames"]["pair_state"]["distinct_contextual_frames"] is False
    assert report["frames"]["pair_state"]["warnings"]
    assert report["decision"]["action"] == "defer"
    assert report["decision"]["priority"] == "needs_context"
    assert report["decision"]["downlink_now"] is False


def test_lifeline_evaluation_and_acceptance_gate():
    base = evaluate_lifeline_predictions(
        [
            {
                "candidate": {**_high_confidence_disruption(), "confidence": 0.2},
                "expected_action": "downlink_now",
            }
        ]
    )
    adapter = evaluate_lifeline_predictions(
        [
            {
                "candidate": _high_confidence_disruption(),
                "expected_action": "downlink_now",
            }
        ]
    )
    gate = check_lifeline_acceptance(base, adapter)

    assert base["downlink_now_recall"] == 0.0
    assert adapter["downlink_now_recall"] == 1.0
    assert gate["accepted"] is True
