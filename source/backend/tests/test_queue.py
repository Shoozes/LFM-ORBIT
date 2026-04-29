import os

from core.queue import estimate_payload_bytes, get_alert_counts, get_recent_alerts, init_db, push_alert


def test_queue_round_trip(tmp_path):
    db_path = tmp_path / "alerts.sqlite"
    os.environ["CANOPY_SENTINEL_DB_PATH"] = str(db_path)

    init_db()

    push_alert(
        event_id="evt_test",
        region_id="amazonas_region_alpha",
        cell_id="85283473fffffff",
        change_score=0.51,
        confidence=0.88,
        priority="high",
        reason_codes=["ndvi_drop", "suspected_canopy_loss"],
        payload_bytes=123,
    )

    counts = get_alert_counts()
    recent = get_recent_alerts(limit=5)

    assert counts["total_alerts"] == 1
    assert counts["total_payload_bytes"] == 123
    assert recent["region_id"] == "amazonas_region_alpha"
    assert recent["alerts"][0]["cell_id"] == "85283473fffffff"
    assert recent["alerts"][0]["runtime_truth_mode"] == "unknown"
    assert recent["alerts"][0]["imagery_origin"] == "unknown"
    assert recent["alerts"][0]["scoring_basis"] == "unknown"


def test_demo_forced_anomaly_persists(tmp_path):
    db_path = tmp_path / "alerts_demo.sqlite"
    os.environ["CANOPY_SENTINEL_DB_PATH"] = str(db_path)

    init_db()

    push_alert(
        event_id="evt_seeded",
        region_id="amazonas_region_alpha",
        cell_id="85283473fffffff",
        change_score=0.60,
        confidence=0.94,
        priority="critical",
        reason_codes=["demo_seeded_highlight", "suspected_canopy_loss"],
        payload_bytes=200,
        demo_forced_anomaly=True,
    )

    push_alert(
        event_id="evt_organic",
        region_id="amazonas_region_alpha",
        cell_id="85283477fffffff",
        change_score=0.45,
        confidence=0.85,
        priority="high",
        reason_codes=["ndvi_drop"],
        payload_bytes=180,
        demo_forced_anomaly=False,
    )

    recent = get_recent_alerts(limit=10)
    alerts = recent["alerts"]

    seeded = next(a for a in alerts if a["event_id"] == "evt_seeded")
    organic = next(a for a in alerts if a["event_id"] == "evt_organic")

    assert seeded["demo_forced_anomaly"] is True
    assert seeded["runtime_truth_mode"] == "fallback"
    assert seeded["imagery_origin"] == "unknown"
    assert seeded["scoring_basis"] == "unknown"
    assert organic["demo_forced_anomaly"] is False


def test_init_db_reset_clears_alerts(tmp_path):
    db_path = tmp_path / "alerts_reset.sqlite"
    os.environ["CANOPY_SENTINEL_DB_PATH"] = str(db_path)

    init_db()

    push_alert(
        event_id="evt_before_reset",
        region_id="amazonas_region_alpha",
        cell_id="85283473fffffff",
        change_score=0.50,
        confidence=0.88,
        priority="high",
        reason_codes=["ndvi_drop"],
        payload_bytes=100,
    )

    counts = get_alert_counts()
    assert counts["total_alerts"] == 1

    init_db(reset=True)

    counts = get_alert_counts()
    assert counts["total_alerts"] == 0


def test_payload_estimation_is_positive():
    payload = {
        "event_id": "evt_test",
        "region_id": "amazonas_region_alpha",
        "cell_id": "85283473fffffff",
        "change_score": 0.42,
    }

    assert estimate_payload_bytes(payload) > 0


def test_boundary_context_round_trips(tmp_path):
    db_path = tmp_path / "alerts_boundary.sqlite"
    os.environ["CANOPY_SENTINEL_DB_PATH"] = str(db_path)

    init_db(reset=True)

    boundary_context = [
        {
            "layer_type": "protected_area",
            "source_name": "demo_boundary_pack",
            "feature_name": "Reserva Teste",
            "overlap_area_m2": 3210.5,
            "overlap_ratio": 0.42,
            "distance_to_boundary_m": 0.0,
        }
    ]

    push_alert(
        event_id="evt_boundary",
        region_id="amazonas_region_alpha",
        cell_id="85283473fffffff",
        change_score=0.67,
        confidence=0.91,
        priority="critical",
        reason_codes=["suspected_canopy_loss"],
        payload_bytes=180,
        boundary_context=boundary_context,
    )

    recent = get_recent_alerts(limit=5)

    assert recent["alerts"][0]["boundary_context"] == boundary_context
