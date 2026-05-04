from core.object_tracking import compute_object_deltas


def test_compute_object_deltas_handles_missing_baseline_and_zero_division():
    deltas = compute_object_deltas(
        None,
        {"counts_by_label": {"shelter": 3, "vehicle": 0}},
    )

    by_label = {item["label"]: item for item in deltas}
    assert by_label["shelter"]["baseline_count"] == 0
    assert by_label["shelter"]["current_count"] == 3
    assert by_label["shelter"]["delta_percent"] == 100.0
    assert by_label["shelter"]["action_hint"] == "defer"
    assert by_label["vehicle"]["action_hint"] == "discard"


def test_compute_object_deltas_escalates_large_count_change():
    deltas = compute_object_deltas(
        {"counts_by_label": {"ship": 10}},
        {"counts_by_label": {"ship": 16}},
    )

    assert deltas == [
        {
            "label": "ship",
            "baseline_count": 10,
            "current_count": 16,
            "delta_count": 6,
            "delta_percent": 60.0,
            "action_hint": "downlink_now",
        }
    ]
