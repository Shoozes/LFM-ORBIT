import json

from core.agent_bus import init_bus, post_message, upsert_pin
from core.gallery import add_gallery_item
from core.queue import init_db, push_alert
from scripts import export_orbit_dataset


def _png_data_url() -> str:
    return (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z6xQAAAAASUVORK5CYII="
    )


def _webm_data_url() -> str:
    return "data:video/webm;base64," + "AAECAwQ="


def test_write_dataset_export_writes_manifest_records_and_assets(tmp_path, monkeypatch):
    db_path = tmp_path / "alerts.sqlite"
    bus_path = tmp_path / "agent_bus.sqlite"
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(db_path))
    monkeypatch.setenv("AGENT_BUS_PATH", str(bus_path))

    init_db(reset=True)
    init_bus(reset=True)
    push_alert(
        event_id="evt_export",
        region_id="amazonas_region_alpha",
        cell_id="85283473fffffff",
        change_score=0.67,
        confidence=0.92,
        priority="critical",
        reason_codes=["suspected_canopy_loss"],
        payload_bytes=256,
        observation_source="seeded_cache",
        before_window={"label": "2024-06", "quality": 0.9, "nir": 0.7, "red": 0.1, "swir": 0.2, "ndvi": 0.6, "nbr": 0.4, "evi2": 0.5, "ndmi": 0.3, "soil_ratio": 0.2, "flags": []},
        after_window={"label": "2025-06", "quality": 0.85, "nir": 0.3, "red": 0.15, "swir": 0.28, "ndvi": 0.25, "nbr": 0.12, "evi2": 0.2, "ndmi": 0.1, "soil_ratio": 0.4, "flags": []},
    )

    add_gallery_item(
        cell_id="85283473fffffff",
        lat=-3.14,
        lng=-60.02,
        severity="critical",
        change_score=0.67,
        fetch_thumb=False,
        timelapse_b64=_webm_data_url(),
        timelapse_analysis="Confirmed canopy loss.",
    )

    from core.agent_bus import _connect as _bus_connect
    with _bus_connect() as conn:
        conn.execute(
            "UPDATE gallery_items SET context_thumb = ? WHERE cell_id = ?",
            (_png_data_url(), "85283473fffffff"),
        )
        conn.commit()

    output_dir = tmp_path / "export"
    manifest = export_orbit_dataset.write_dataset_export(output_dir, limit=20, eval_ratio=0.5)

    assert manifest["records"] == 1
    assert manifest["positive_records"] == 1
    assert manifest["control_records"] == 0
    assert manifest["api_observation_records"] == 0
    assert manifest["records_with_gallery"] == 1
    assert manifest["records_with_context_thumb"] == 1
    assert manifest["records_with_timelapse"] == 1
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "samples.jsonl").exists()
    assert (output_dir / "train.jsonl").exists() or (output_dir / "eval.jsonl").exists()
    assert (output_dir / "training.jsonl").exists()

    records = [json.loads(line) for line in (output_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    record = records[0]
    assert record["confirmation_source"] == "ground_gallery"
    assert record["temporal_use_case"]["id"] == "deforestation"
    assert record["api_prep"]["auto_build"] is True
    assert record["assets"]["context_thumb"] == "context_thumb.png"
    assert record["assets"]["timelapse"] == "timelapse.webm"

    sample_dir = output_dir / "samples" / record["sample_id"]
    assert (sample_dir / "context_thumb.png").exists()
    assert (sample_dir / "timelapse.webm").exists()
    assert (sample_dir / "timelapse_analysis.txt").read_text(encoding="utf-8") == "Confirmed canopy loss."

    training_rows = [
        json.loads(line)
        for line in (output_dir / "training.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert training_rows[0]["format"] == "orbit_temporal_sft_v1"
    assert training_rows[0]["metadata"]["use_case_id"] == "deforestation"


def test_write_dataset_export_backfills_context_and_includes_ground_reject_controls(tmp_path, monkeypatch):
    db_path = tmp_path / "alerts.sqlite"
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(db_path))
    bus_path = tmp_path / "agent_bus.sqlite"
    monkeypatch.setenv("AGENT_BUS_PATH", str(bus_path))
    monkeypatch.setattr(export_orbit_dataset, "resolve_context_thumb", lambda lat, lng: _png_data_url())

    init_db(reset=True)
    init_bus(reset=True)
    push_alert(
        event_id="evt_alert_only",
        region_id="amazonas_region_alpha",
        cell_id="alert_cell_only",
        change_score=0.51,
        confidence=0.88,
        priority="high",
        reason_codes=["ndvi_drop"],
        payload_bytes=123,
    )
    upsert_pin(
        pin_type="satellite",
        lat=-3.12,
        lng=-60.01,
        label="SAT ◆ alert",
        note="Orbital flag",
        cell_id="alert_cell_only",
    )

    post_message(
        sender="ground",
        recipient="satellite",
        msg_type="reject",
        cell_id="reject_cell_only",
        payload={
            "reason": "composite score too low for escalation",
            "change_score": 0.18,
            "confidence": 0.32,
            "reason_codes": ["low_signal"],
            "observation_source": "seeded_cache",
        },
    )
    upsert_pin(
        pin_type="satellite",
        lat=-3.22,
        lng=-60.11,
        label="SAT ◆ reject",
        note="Orbital flag then reject",
        cell_id="reject_cell_only",
    )

    output_dir = tmp_path / "export"
    manifest = export_orbit_dataset.write_dataset_export(output_dir, limit=10, eval_ratio=0.5)
    records = [json.loads(line) for line in (output_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

    assert manifest["records"] == 2
    assert manifest["positive_records"] == 1
    assert manifest["control_records"] == 1
    assert manifest["records_with_gallery"] == 0
    assert manifest["records_with_context_thumb"] == 2

    by_cell = {record["cell_id"]: record for record in records}
    positive = by_cell["alert_cell_only"]
    reject = by_cell["reject_cell_only"]

    assert positive["record_type"] == "positive"
    assert positive["confirmation_source"] == "alert_queue"
    assert positive["target_action"] == "alert"
    assert positive["assets"]["context_thumb"] == "context_thumb.png"

    assert reject["record_type"] == "control"
    assert reject["confirmation_source"] == "ground_reject"
    assert reject["target_action"] == "prune"
    assert reject["target_category"] == "none"
    assert reject["label_tier"] == "weak_negative"
    assert "composite score too low" in reject["rejection_reason"]
    assert reject["assets"]["context_thumb"] == "context_thumb.png"

    assert (output_dir / "samples" / positive["sample_id"] / "context_thumb.png").exists()
    assert (output_dir / "samples" / reject["sample_id"] / "context_thumb.png").exists()


def test_write_dataset_export_auto_classifies_wildfire_training_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "alerts.sqlite"
    bus_path = tmp_path / "agent_bus.sqlite"
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(db_path))
    monkeypatch.setenv("AGENT_BUS_PATH", str(bus_path))

    init_db(reset=True)
    init_bus(reset=True)
    push_alert(
        event_id="evt_fire",
        region_id="california_fire_test",
        cell_id="fire_cell_only",
        change_score=0.74,
        confidence=0.91,
        priority="critical",
        reason_codes=["burn_scar", "nbr_drop", "ndmi_drop"],
        payload_bytes=321,
        observation_source="nasa_gibs",
        before_window={"label": "2024-07", "quality": 0.9, "nir": 0.62, "red": 0.10, "swir": 0.20, "ndvi": 0.72, "nbr": 0.51, "evi2": 0.61, "ndmi": 0.40, "soil_ratio": 0.30, "flags": []},
        after_window={"label": "2024-10", "quality": 0.88, "nir": 0.28, "red": 0.16, "swir": 0.39, "ndvi": 0.27, "nbr": -0.16, "evi2": 0.22, "ndmi": -0.16, "soil_ratio": 1.39, "flags": ["burn_scar"]},
    )

    output_dir = tmp_path / "export"
    manifest = export_orbit_dataset.write_dataset_export(
        output_dir,
        limit=10,
        eval_ratio=0.5,
        include_rejects=False,
    )
    records = [
        json.loads(line)
        for line in (output_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    training_rows = [
        json.loads(line)
        for line in (output_dir / "training.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert manifest["use_case_counts"]["wildfire"] == 1
    assert records[0]["temporal_use_case"]["id"] == "wildfire"
    assert records[0]["target_task"] == "wildfire_temporal_detection"
    assert records[0]["target_category"] == "wildfire"
    assert records[0]["temporal_use_case"]["examples"]

    assistant_payload = json.loads(training_rows[0]["messages"][2]["content"])
    assert assistant_payload["use_case_id"] == "wildfire"
    assert assistant_payload["target_category"] == "wildfire"


def test_write_dataset_export_includes_persisted_monitor_reports(tmp_path, monkeypatch):
    db_path = tmp_path / "alerts.sqlite"
    bus_path = tmp_path / "agent_bus.sqlite"
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(db_path))
    monkeypatch.setenv("AGENT_BUS_PATH", str(bus_path))
    monkeypatch.setattr(export_orbit_dataset, "resolve_context_thumb", lambda lat, lng: _png_data_url())

    init_db(reset=True)
    init_bus(reset=True)

    from core.lifeline_monitoring import build_lifeline_monitor_report
    from core.maritime_monitoring import build_maritime_monitor_report

    monitor_dir = tmp_path / "monitor_reports"
    monitor_dir.mkdir()

    lifeline_report = build_lifeline_monitor_report(
        asset_id="orbit_bridge_corridor",
        baseline_frame={"label": "before", "date": "2025-01-01", "asset_ref": "before.png"},
        current_frame={"label": "after", "date": "2025-01-15", "asset_ref": "after.png"},
        candidate={
            "event_type": "probable_access_obstruction",
            "severity": "high",
            "confidence": 0.91,
            "bbox": [0.2, 0.25, 0.65, 0.75],
            "civilian_impact": "public_mobility_disruption",
            "why": "The current frame shows a bridge approach obstruction.",
            "action": "downlink_now",
        },
    )
    maritime_report = build_maritime_monitor_report(
        lat=29.92,
        lon=32.54,
        timestamp="2025-03-15",
        task_text="Review maritime vessel queueing near a channel.",
    )
    maritime_report["stac"] = {
        "provider": "element84_earth_search",
        "collection": "sentinel-2-l2a",
        "disabled": False,
        "items": [
            {
                "item_id": "scene-1",
                "date": "2025-03-15",
                "visual_href": "https://example.test/scene-1.tif",
                "bbox": [32.2, 29.7, 32.8, 30.1],
            }
        ],
    }

    (monitor_dir / "lifeline.json").write_text(json.dumps(lifeline_report), encoding="utf-8")
    (monitor_dir / "maritime.json").write_text(json.dumps(maritime_report), encoding="utf-8")

    output_dir = tmp_path / "export"
    manifest = export_orbit_dataset.write_dataset_export(
        output_dir,
        limit=10,
        eval_ratio=0.5,
        include_rejects=False,
        monitor_reports_dir=monitor_dir,
    )
    records = [
        json.loads(line)
        for line in (output_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_type = {record["monitor_type"]: record for record in records}

    assert manifest["records"] == 2
    assert manifest["monitor_report_records"] == 2
    assert manifest["records_with_context_thumb"] == 2
    assert manifest["use_case_counts"]["civilian_lifeline_disruption"] == 1
    assert manifest["use_case_counts"]["maritime_activity"] == 1

    lifeline = by_type["lifeline_before_after"]
    assert lifeline["target_action"] == "downlink_now"
    assert lifeline["candidate"]["civilian_impact"] == "public_mobility_disruption"
    assert lifeline["assets"]["baseline_frame"] == "before.png"
    assert lifeline["assets"]["current_frame"] == "after.png"

    maritime = by_type["maritime_stac_investigation"]
    assert maritime["target_category"] == "maritime"
    assert maritime["stac_items"][0]["visual_href"] == "https://example.test/scene-1.tif"
    assert maritime["assets"]["visual_hrefs"] == ["https://example.test/scene-1.tif"]

    training_rows = [
        json.loads(line)
        for line in (output_dir / "training.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert {row["metadata"]["use_case_id"] for row in training_rows} == {
        "civilian_lifeline_disruption",
        "maritime_activity",
    }
