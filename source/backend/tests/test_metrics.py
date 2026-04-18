import json
import os

from core.metrics import (
    init_metrics,
    read_metrics_summary,
    record_cycle_complete,
    record_cycle_start,
    record_scan_result,
)


def test_metrics_summary_tracks_cycles_and_examples(tmp_path):
    metrics_path = tmp_path / "demo_metrics_summary.json"
    os.environ["CANOPY_SENTINEL_METRICS_PATH"] = str(metrics_path)

    init_metrics(reset=True)
    record_cycle_start(1)
    record_scan_result(
        cycle_index=1,
        is_anomaly=False,
        payload_bytes=0,
        bandwidth_saved_mb=5.0,
        discard_ratio=1.0,
        flagged_example=None,
    )
    record_scan_result(
        cycle_index=1,
        is_anomaly=True,
        payload_bytes=123,
        bandwidth_saved_mb=0.0,
        discard_ratio=0.5,
        flagged_example={
            "event_id": "evt_test",
            "cell_id": "85283473fffffff",
            "cycle_index": 1,
            "change_score": 0.61,
            "confidence": 0.94,
            "priority": "critical",
            "reason_codes": ["demo_seeded_highlight", "suspected_canopy_loss"],
            "payload_bytes": 123,
            "timestamp": "2026-04-15T00:00:00Z",
            "demo_forced_anomaly": True,
        },
    )
    record_cycle_complete(1, 0.5)

    summary = read_metrics_summary()

    assert summary["total_cycles_completed"] == 1
    assert summary["total_cells_scanned"] == 2
    assert summary["total_alerts_emitted"] == 1
    assert summary["total_payload_bytes"] == 123
    assert summary["total_bandwidth_saved_mb"] == 5.0
    assert summary["flagged_examples"][0]["event_id"] == "evt_test"


def test_init_metrics_reset_overwrites_existing_state(tmp_path):
    metrics_path = tmp_path / "demo_metrics_summary.json"
    os.environ["CANOPY_SENTINEL_METRICS_PATH"] = str(metrics_path)

    init_metrics(reset=True)
    with open(metrics_path, "r", encoding="utf-8") as file:
        original = json.load(file)

    original["total_cycles_completed"] = 4
    with open(metrics_path, "w", encoding="utf-8") as file:
        json.dump(original, file)

    init_metrics(reset=True)
    summary = read_metrics_summary()

    assert summary["total_cycles_completed"] == 0


def test_init_metrics_no_reset_preserves_existing_state(tmp_path):
    metrics_path = tmp_path / "demo_metrics_persist.json"
    os.environ["CANOPY_SENTINEL_METRICS_PATH"] = str(metrics_path)

    init_metrics(reset=True)
    record_cycle_start(1)
    record_scan_result(
        cycle_index=1,
        is_anomaly=True,
        payload_bytes=99,
        bandwidth_saved_mb=0.0,
        discard_ratio=0.8,
        flagged_example=None,
    )
    record_cycle_complete(1, 0.8)

    summary_before = read_metrics_summary()
    assert summary_before["total_cells_scanned"] == 1
    assert summary_before["total_alerts_emitted"] == 1

    init_metrics(reset=False)
    summary_after = read_metrics_summary()

    assert summary_after["total_cells_scanned"] == 1
    assert summary_after["total_alerts_emitted"] == 1
    assert summary_after["total_cycles_completed"] == 1