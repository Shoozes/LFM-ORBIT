import json
import base64

from core.agent_bus import init_bus, post_message, upsert_pin
from core.gallery import add_gallery_item
from core.queue import init_db, push_alert
from scripts import export_orbit_dataset


def _png_data_url() -> str:
    return (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z6xQAAAAASUVORK5CYII="
    )


def _png_bytes() -> bytes:
    return base64.b64decode(_png_data_url().split(",", 1)[1])


def _webm_data_url() -> str:
    return "data:video/webm;base64," + "AAECAwQ="


def _svg_data_url() -> str:
    svg = (
        '<svg width="192" height="192" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="100%" height="100%" fill="rgb(30,90,45)"/>'
        '<text x="10" y="20">OFFLINE CHIP</text>'
        "</svg>"
    )
    import base64

    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


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
    assert record["training_contract"]["schema"] == "orbit_training_contract_v1"
    assert record["training_contract"]["nm_uni_import"]["role"] == "satellite_vlm_training_bridge"
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
    assert reject["training_contract"]["operator_review_status"] == "operator_reviewed"
    assert reject["training_contract"]["target_action"] == "prune"


def test_write_dataset_export_rasterizes_svg_context_placeholders(tmp_path, monkeypatch):
    db_path = tmp_path / "alerts.sqlite"
    bus_path = tmp_path / "agent_bus.sqlite"
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(db_path))
    monkeypatch.setenv("AGENT_BUS_PATH", str(bus_path))
    monkeypatch.setattr(export_orbit_dataset, "resolve_context_thumb", lambda lat, lng: _svg_data_url())

    init_db(reset=True)
    init_bus(reset=True)
    push_alert(
        event_id="evt_svg",
        region_id="amazonas_region_alpha",
        cell_id="svg_cell",
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
        label="SAT svg",
        note="Needs offline chip.",
        cell_id="svg_cell",
    )

    output_dir = tmp_path / "export"
    export_orbit_dataset.write_dataset_export(output_dir, limit=10, eval_ratio=0.5)
    record = json.loads((output_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines()[0])
    sample_dir = output_dir / "samples" / record["sample_id"]

    assert record["assets"]["context_thumb"] == "context_thumb.png"
    assert (sample_dir / "context_thumb.png").read_bytes().startswith(b"\x89PNG")
    assert not (sample_dir / "context_thumb.svg").exists()


def test_write_dataset_export_can_force_offline_context_thumbnails(tmp_path, monkeypatch):
    db_path = tmp_path / "alerts.sqlite"
    bus_path = tmp_path / "agent_bus.sqlite"
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(db_path))
    monkeypatch.setenv("AGENT_BUS_PATH", str(bus_path))

    def fail_network_thumb(_lat, _lng):
        raise AssertionError("offline export should not call thumbnail resolver")

    monkeypatch.setattr(export_orbit_dataset, "resolve_context_thumb", fail_network_thumb)

    init_db(reset=True)
    init_bus(reset=True)
    push_alert(
        event_id="evt_offline_thumb",
        region_id="amazonas_region_alpha",
        cell_id="offline_thumb_cell",
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
        label="SAT offline",
        note="Needs local chip.",
        cell_id="offline_thumb_cell",
    )

    output_dir = tmp_path / "export"
    stale_dir = output_dir / "samples" / "stale_sample"
    stale_dir.mkdir(parents=True)
    (stale_dir / "context_thumb.png").write_bytes(b"stale")

    manifest = export_orbit_dataset.write_dataset_export(
        output_dir,
        limit=10,
        eval_ratio=0.5,
        offline_context_thumbnails=True,
    )
    record = json.loads((output_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines()[0])
    sample_dir = output_dir / "samples" / record["sample_id"]

    assert manifest["records_with_context_thumb"] == 1
    assert record["assets"]["context_thumb"] == "context_thumb.png"
    assert (sample_dir / "context_thumb.png").read_bytes().startswith(b"\x89PNG")
    assert not stale_dir.exists()


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
    (monitor_dir / "before.png").write_bytes(base64.b64decode(_png_data_url().split(",", 1)[1]))
    (monitor_dir / "after.png").write_bytes(base64.b64decode(_png_data_url().split(",", 1)[1]))

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
    assert lifeline["training_contract"]["localization"]["candidate_bbox_field"] == "candidate_bbox"

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


def test_write_dataset_export_ignores_missing_optional_monitor_report_dir(tmp_path, monkeypatch):
    db_path = tmp_path / "alerts.sqlite"
    bus_path = tmp_path / "agent_bus.sqlite"
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(db_path))
    monkeypatch.setenv("AGENT_BUS_PATH", str(bus_path))

    init_db(reset=True)
    init_bus(reset=True)

    output_dir = tmp_path / "export"
    manifest = export_orbit_dataset.write_dataset_export(
        output_dir,
        limit=10,
        eval_ratio=0.5,
        include_rejects=False,
        monitor_reports_dir=tmp_path / "missing-monitor-reports",
    )

    assert manifest["records"] == 0
    assert manifest["monitor_report_records"] == 0


def test_write_dataset_export_can_include_seeded_cache_records(tmp_path, monkeypatch):
    db_path = tmp_path / "alerts.sqlite"
    bus_path = tmp_path / "agent_bus.sqlite"
    seeded_dir = tmp_path / "seeded_data"
    seeded_dir.mkdir()
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(db_path))
    monkeypatch.setenv("AGENT_BUS_PATH", str(bus_path))
    monkeypatch.setattr(export_orbit_dataset, "_SEEDED_DATA_DIR", seeded_dir)
    monkeypatch.setattr(export_orbit_dataset, "resolve_context_thumb", lambda lat, lng: _png_data_url())

    init_db(reset=True)
    init_bus(reset=True)

    (seeded_dir / "sh_demo1234.webm").write_bytes(b"webm-bytes")
    demo_frame_dir = seeded_dir / "sh_demo1234_frames"
    demo_frame_dir.mkdir()
    (demo_frame_dir / "01_before.png").write_bytes(b"png-before")
    (demo_frame_dir / "02_after.png").write_bytes(b"png-after")
    (seeded_dir / "sh_demo1234_meta.json").write_text(
        json.dumps(
            {
                "chunk_signature": "demo1234",
                "bbox": [-63.1, -10.1, -63.0, -10.0],
                "lat": -10.05,
                "lon": -63.05,
                "location_name": "Rondonia test cell",
                "region_note": "Replay cache fixture",
                "start_date": "2023-01",
                "end_date": "2025-01",
                "frames_count": 25,
                "frame_dates": ["2023-01-15", "2025-01-15"],
                "frame_images": [
                    str(demo_frame_dir / "01_before.png"),
                    str(demo_frame_dir / "02_after.png"),
                ],
                "date_windows": [
                    {"label": "before", "start_date": "2023-01-01", "end_date": "2023-02-01"},
                    {"label": "after", "start_date": "2025-01-01", "end_date": "2025-02-01"},
                ],
                "frame_quality": [
                    {"label": "before", "valid_pixel_ratio": 0.97, "cloud_pixel_ratio": 0.01, "reasons": []},
                    {"label": "after", "valid_pixel_ratio": 0.95, "cloud_pixel_ratio": 0.02, "reasons": []},
                ],
                "rejected_windows": [
                    {
                        "label": "cloudy",
                        "quality": {
                            "accepted": False,
                            "valid_pixel_ratio": 0.2,
                            "cloud_pixel_ratio": 0.8,
                            "reasons": ["insufficient_valid_pixels"],
                        },
                    },
                ],
                "visual_mode": "burn_scar",
                "vlm_explanation": "Seeded Sentinel-2 timelapse.",
                "source": "Sentinel Hub Sentinel-2 L2A",
                "training_ready": True,
                "use_case_id": "wildfire",
                "target_category": "wildfire",
                "target_pack_id": "fireline",
                "target_task": "wildfire_close_look_candidate_review",
                "spectral_bands": {
                    "visual_mode": "burn_scar",
                    "requested_bands": ["B12", "B08", "B04"],
                    "band_stats_by_frame": [
                        {
                            "label": "before",
                            "bands": {
                                "B04_red": {"mean": 0.05},
                                "B08_nir": {"mean": 0.3},
                                "B12_swir2": {"mean": 0.15},
                            },
                            "derived_indices": {
                                "ndvi": 0.7143,
                                "nbr_swir2": 0.3333,
                                "swir2_nir_ratio": 0.5,
                            },
                            "valid_pixel_ratio": 0.97,
                            "stats_source": "test",
                        },
                    ],
                    "derived_indices": ["ndvi", "nbr_swir2", "swir2_nir_ratio"],
                },
            }
        ),
        encoding="utf-8",
    )
    (seeded_dir / "sh_ice1234.webm").write_bytes(b"ice-webm-bytes")
    (seeded_dir / "sh_ice1234_meta.json").write_text(
        json.dumps(
            {
                "chunk_signature": "ice1234",
                "bbox": [-51.13, 69.1, -50.97, 69.26],
                "lat": 69.18,
                "lon": -51.05,
                "location_name": "Greenland ice/snow extent test cell",
                "region_note": "NDSI/SCL fixture",
                "start_date": "2024-01",
                "end_date": "2025-12",
                "frames_count": 4,
                "frame_dates": ["2024-01-15", "2025-12-15"],
                "vlm_explanation": "Seeded ice/snow extent metadata.",
                "source": "Sentinel Hub Sentinel-2 L2A",
                "runtime_truth_mode": "replay",
                "imagery_origin": "cached_api",
                "scoring_basis": "multispectral_bands",
                "training_ready": True,
                "use_case_id": "ice_snow_extent",
                "target_category": "cryosphere",
                "target_task": "ice_snow_extent_monitoring",
            }
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "export"
    manifest = export_orbit_dataset.write_dataset_export(
        output_dir,
        limit=10,
        include_rejects=False,
        include_api_observations=False,
        include_seeded_cache=True,
    )
    records = [
        json.loads(line)
        for line in (output_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert manifest["records"] == 2
    assert manifest["seeded_cache_records"] == 2
    assert manifest["records_with_timelapse"] == 2
    assert manifest["use_case_counts"]["ice_snow_extent"] == 1
    record = next(item for item in records if item["chunk_signature"] == "demo1234")
    ice_record = next(item for item in records if item["chunk_signature"] == "ice1234")
    assert record["record_type"] == "seeded_cache"
    assert record["confirmation_source"] == "seeded_data"
    assert record["target_category"] == "wildfire"
    assert record["target_pack_id"] == "fireline"
    assert "target_pack:fireline" in record["reason_codes"]
    assert record["target_task"] == "wildfire_temporal_detection"
    assert record["visual_mode"] == "burn_scar"
    assert record["date_windows"][0]["label"] == "before"
    assert record["frame_quality"][0]["valid_pixel_ratio"] == 0.97
    assert record["rejected_windows"][0]["quality"]["cloud_pixel_ratio"] == 0.8
    assert record["seeded_meta_path"] == "sh_demo1234_meta.json"
    assert record["band_tags"] == ["B12", "B08", "B04"]
    assert record["derived_indices"] == ["ndvi", "nbr_swir2", "swir2_nir_ratio"]
    assert record["spectral_bands"]["band_stats_by_frame"][0]["derived_indices"]["ndvi"] == 0.7143
    assert record["assets"]["timelapse"] == "timelapse.webm"
    assert record["assets"]["frames"] == ["frames/01_01_before.png", "frames/02_02_after.png"]
    assert (output_dir / "samples" / record["sample_id"] / "timelapse.webm").read_bytes() == b"webm-bytes"
    assert (output_dir / "samples" / record["sample_id"] / "frames" / "01_01_before.png").read_bytes() == b"png-before"
    assert ice_record["target_category"] == "cryosphere"
    assert ice_record["target_task"] == "ice_snow_extent_monitoring"
    assert ice_record["runtime_truth_mode"] == "replay"
    assert ice_record["imagery_origin"] == "cached_api"
    assert ice_record["scoring_basis"] == "multispectral_bands"
    assert ice_record["temporal_use_case"]["id"] == "ice_snow_extent"


def test_seeded_cache_record_replaces_duplicate_api_observation(tmp_path, monkeypatch):
    db_path = tmp_path / "alerts.sqlite"
    bus_path = tmp_path / "agent_bus.sqlite"
    seeded_dir = tmp_path / "seeded_data"
    seeded_dir.mkdir()
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(db_path))
    monkeypatch.setenv("AGENT_BUS_PATH", str(bus_path))
    monkeypatch.setattr(export_orbit_dataset, "_SEEDED_DATA_DIR", seeded_dir)
    monkeypatch.setattr(export_orbit_dataset, "resolve_context_thumb", lambda lat, lng: _png_data_url())
    monkeypatch.setattr(
        export_orbit_dataset,
        "list_observations",
        lambda training_ready_only=False: [
            {
                "chunk_signature": "demo1234",
                "bbox": [-63.1, -10.1, -63.0, -10.0],
                "source": "sentinelhub_process",
                "training_ready": True,
                "observations": [{"vlm_text": "generic observation row"}],
            }
        ],
    )

    init_db(reset=True)
    init_bus(reset=True)

    (seeded_dir / "sh_demo1234.webm").write_bytes(b"webm-bytes")
    (seeded_dir / "sh_demo1234_meta.json").write_text(
        json.dumps(
            {
                "chunk_signature": "demo1234",
                "bbox": [-63.1, -10.1, -63.0, -10.0],
                "lat": -10.05,
                "lon": -63.05,
                "location_name": "Seeded flood target",
                "frames_count": 4,
                "frame_dates": ["before", "after"],
                "vlm_explanation": "richer seeded metadata",
                "source": "Sentinel Hub Sentinel-2 L2A",
                "training_ready": True,
                "use_case_id": "flood_extent",
                "target_category": "flood",
                "target_task": "flood_temporal_detection",
            }
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "export"
    manifest = export_orbit_dataset.write_dataset_export(
        output_dir,
        limit=10,
        include_rejects=False,
        include_api_observations=True,
        include_seeded_cache=True,
    )
    records = [
        json.loads(line)
        for line in (output_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert manifest["records"] == 1
    assert manifest["api_observation_records"] == 0
    assert manifest["seeded_cache_records"] == 1
    assert records[0]["record_type"] == "seeded_cache"
    assert records[0]["target_task"] == "flood_temporal_detection"
    assert records[0]["timelapse_analysis"] == "richer seeded metadata"


def test_dataset_export_can_recycle_visual_story_frames(tmp_path, monkeypatch):
    db_path = tmp_path / "alerts.sqlite"
    bus_path = tmp_path / "agent_bus.sqlite"
    seeded_dir = tmp_path / "seeded_data"
    story_dir = seeded_dir / "visual_story_frames"
    story_dir.mkdir(parents=True)
    story_image = story_dir / "story_houses.png"
    story_image.write_bytes(_png_bytes())
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(db_path))
    monkeypatch.setenv("AGENT_BUS_PATH", str(bus_path))
    monkeypatch.setattr(export_orbit_dataset, "_SEEDED_DATA_DIR", seeded_dir)

    init_db(reset=True)
    init_bus(reset=True)

    (story_dir / "visual_story_manifest.json").write_text(
        json.dumps(
            {
                "stories": [
                    {
                        "story_id": "houses",
                        "title": "Buildings / Houses",
                        "bbox": [-81.458, 28.408, -81.448, 28.418],
                        "date_from": "2026-01-01",
                        "date_to": "2026-02-15",
                        "source": "Esri World Imagery context",
                        "imagery_origin": "esri_context",
                        "runtime_truth_mode": "replay",
                        "scoring_basis": "visual_only",
                        "box_source": "visual_story_fixture",
                        "box_count": 3,
                        "targets": ["houses", "roof rows"],
                        "frame_path": str(story_image),
                        "output_path": str(story_image),
                        "training_ready": True,
                        "note": "Boxes are deterministic visual-story evidence fixtures, not a claim of live model-backed object detection.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "export"
    manifest = export_orbit_dataset.write_dataset_export(
        output_dir,
        limit=10,
        include_rejects=False,
        include_seeded_cache=True,
    )
    records = [
        json.loads(line)
        for line in (output_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert manifest["records"] == 1
    assert manifest["visual_story_frame_records"] == 1
    assert manifest["records_with_context_thumb"] == 1
    record = records[0]
    assert record["record_type"] == "visual_story_frame"
    assert record["confirmation_source"] == "visual_story_manifest"
    assert record["box_source"] == "visual_story_fixture"
    assert record["object_targets"] == ["houses", "roof rows"]
    assert record["assets"]["context_thumb"] == "context_thumb.png"
    assert (output_dir / "samples" / record["sample_id"] / "context_thumb.png").read_bytes() == _png_bytes()


def test_dataset_export_preserves_current_and_archived_mission_metadata(tmp_path, monkeypatch):
    db_path = tmp_path / "alerts.sqlite"
    bus_path = tmp_path / "agent_bus.sqlite"
    runtime_dir = tmp_path / "runtime-data"
    monkeypatch.setenv("CANOPY_SENTINEL_DB_PATH", str(db_path))
    monkeypatch.setenv("AGENT_BUS_PATH", str(bus_path))
    monkeypatch.setenv("CANOPY_SENTINEL_METRICS_PATH", str(tmp_path / "metrics.json"))
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(runtime_dir))

    init_db(reset=True)
    init_bus(reset=True)

    from core.mission import init_missions, start_mission
    from core.mission_archive import read_mission_archive
    from core.runtime_state import reset_runtime_state

    init_missions(reset=True)
    start_mission(
        "Run Southeast Fireline Watch. Look for dark smoke and road obstruction.",
        bbox=[-81.916, 31.143, -81.756, 31.303],
        target_pack_id="fireline",
    )

    current_manifest = export_orbit_dataset.write_dataset_export(
        tmp_path / "current-export",
        limit=10,
        include_rejects=False,
    )
    current_records = [
        json.loads(line)
        for line in (tmp_path / "current-export" / "samples.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert current_manifest["mission_metadata_records"] == 1
    current = current_records[0]
    assert current["record_type"] == "mission_metadata"
    assert current["confirmation_source"] == "mission_state"
    assert current["target_pack_id"] == "fireline"
    assert "dark smoke" in current["object_target_labels"]
    assert current["training_contract"]["evidence_requirements"]["context_thumb_required_for_nm_uni"] is False

    reset_summary = reset_runtime_state()
    assert reset_summary["missions_archived"] == 1
    assert read_mission_archive(limit=5)

    archived_manifest = export_orbit_dataset.write_dataset_export(
        tmp_path / "archived-export",
        limit=10,
        include_rejects=False,
    )
    archived_records = [
        json.loads(line)
        for line in (tmp_path / "archived-export" / "samples.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert archived_manifest["mission_metadata_records"] == 1
    archived = archived_records[0]
    assert archived["record_type"] == "mission_metadata"
    assert archived["confirmation_source"] == "mission_archive"
    assert archived["target_pack_id"] == "fireline"
    assert "road obstruction" in archived["object_target_labels"]
