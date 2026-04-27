from core.telemetry import build_alert_payload, build_scan_result_message


def test_scan_result_message_preserves_boundary_context_and_demo_flag():
    boundary_context = [
        {
            "layer_type": "protected_area",
            "source_name": "demo_boundary_pack",
            "feature_name": "Reserva Teste",
            "overlap_area_m2": 123.4,
            "overlap_ratio": 0.5,
            "distance_to_boundary_m": 0.0,
        }
    ]
    alert_payload = build_alert_payload(
        event_id="evt_test",
        cell_id="85283473fffffff",
        change_score=0.71,
        confidence=0.93,
        reason_codes=["suspected_canopy_loss"],
        boundary_context=boundary_context,
        demo_forced_anomaly=True,
    )

    message = build_scan_result_message(
        alert_payload=alert_payload,
        score={
            "observation_source": "semi_real_loader_v1",
            "before_window": {
                "label": "before",
                "quality": 0.95,
                "nir": 0.6,
                "red": 0.1,
                "swir": 0.2,
                "ndvi": 0.7,
                "nbr": 0.5,
                "evi2": 0.6,
                "ndmi": 0.5,
                "soil_ratio": 0.3,
                "flags": [],
            },
            "after_window": {
                "label": "after",
                "quality": 0.91,
                "nir": 0.3,
                "red": 0.2,
                "swir": 0.4,
                "ndvi": 0.2,
                "nbr": 0.1,
                "evi2": 0.15,
                "ndmi": 0.1,
                "soil_ratio": 1.3,
                "flags": ["disturbance_pattern"],
            },
        },
        is_anomaly=True,
        payload_bytes=222,
        estimated_bandwidth_saved_mb=0.0,
        cells_scanned=4,
        alerts_emitted=1,
        discard_ratio=0.75,
        total_cells=12,
        cycle_index=2,
    )

    assert message["boundary_context"] == boundary_context
    assert message["demo_forced_anomaly"] is True
