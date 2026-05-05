from __future__ import annotations

import json

import pytest
import numpy as np

from scripts import seed_sentinel_cache


def test_parse_date_windows_accepts_repeated_event_windows():
    windows = seed_sentinel_cache.parse_date_windows(
        [
            "pre=2026-04-01:2026-04-10",
            "post=2026-04-25:2026-04-28",
        ]
    )

    assert windows == [
        ("pre", "2026-04-01", "2026-04-10"),
        ("post", "2026-04-25", "2026-04-28"),
    ]


def test_parse_date_windows_rejects_ambiguous_values():
    with pytest.raises(ValueError, match="LABEL=YYYY-MM-DD:YYYY-MM-DD"):
        seed_sentinel_cache.parse_date_windows(["2026-04-01:2026-04-10"])


def test_burn_scar_visual_mode_uses_real_sentinel_bands():
    evalscript = seed_sentinel_cache.SH_EVALSCRIPTS["burn_scar"]

    assert "B12" in evalscript
    assert "B08" in evalscript
    assert "B04" in evalscript
    assert "B03" not in evalscript


def test_frame_quality_from_scl_rejects_cloudy_seed_frames():
    arr = np.zeros((8, 8, 2), dtype=np.uint8)
    arr[:, :, 0] = 9
    arr[:, :, 1] = 1
    arr[0, 0, 0] = 4

    quality = seed_sentinel_cache._frame_quality_from_scl(arr)

    assert quality["accepted"] is False
    assert quality["cloud_pixel_ratio"] > 0.9
    assert "insufficient_valid_pixels" in quality["reasons"]


def test_frame_quality_from_scl_uses_data_mask_as_nodata():
    arr = np.zeros((8, 8, 2), dtype=np.uint8)
    arr[:, :, 0] = 4
    arr[:, :, 1] = 0

    quality = seed_sentinel_cache._frame_quality_from_scl(arr)

    assert quality["accepted"] is False
    assert quality["valid_pixel_ratio"] == 0.0
    assert quality["nodata_pixel_ratio"] == 1.0


def test_band_stats_from_response_computes_wildfire_indices():
    arr = np.zeros((4, 4, 5), dtype=np.float32)
    arr[:, :, 0] = 0.05
    arr[:, :, 1] = 0.30
    arr[:, :, 2] = 0.15
    arr[:, :, 3] = 4
    arr[:, :, 4] = 1

    stats = seed_sentinel_cache._band_stats_from_response(arr)

    assert stats is not None
    assert stats["bands"]["B04_red"]["mean"] == 0.05
    assert stats["bands"]["B08_nir"]["mean"] == 0.3
    assert stats["bands"]["B12_swir2"]["mean"] == 0.15
    assert stats["derived_indices"]["ndvi"] == 0.7143
    assert stats["derived_indices"]["nbr_swir2"] == 0.3333
    assert stats["derived_indices"]["swir2_nir_ratio"] == 0.5


def test_seed_single_cell_persists_frame_images_for_custom_windows(tmp_path, monkeypatch):
    frames = [
        np.full((8, 8, 3), 40, dtype=np.uint8),
        np.full((8, 8, 3), 120, dtype=np.uint8),
    ]

    def fake_fetch(label, *_args, **_kwargs):
        index = 0 if label == "pre" else 1
        return frames[index], f"source {label}", {
            "valid_pixel_ratio": 0.99,
            "cloud_pixel_ratio": 0.0,
            "nodata_pixel_ratio": 0.0,
            "reasons": [],
            "band_stats": {
                "bands": {"B04_red": {"mean": 0.05}, "B08_nir": {"mean": 0.3}, "B12_swir2": {"mean": 0.15}},
                "derived_indices": {"ndvi": 0.7143, "nbr_swir2": 0.3333, "swir2_nir_ratio": 0.5},
                "valid_pixel_ratio": 0.99,
                "stats_source": "test",
            },
        }

    monkeypatch.setattr(seed_sentinel_cache, "fetch_sh_window", fake_fetch)
    monkeypatch.setattr(seed_sentinel_cache.iio, "imwrite", lambda path, *_args, **_kwargs: open(path, "wb").write(b"webm"))
    monkeypatch.setattr(seed_sentinel_cache, "save_observation", lambda **_kwargs: None)
    monkeypatch.setattr(seed_sentinel_cache, "DETECTION", type("D", (), {"min_quality_threshold": 0.65})())

    sig = seed_sentinel_cache.seed_single_cell(
        lat=29.6466,
        lon=-82.1662,
        cell_dim=0.035,
        start_ym="2023-01",
        end_ym="2025-01",
        location_name="Florida fire seed test",
        region_note="test",
        cache_dir=tmp_path,
        config=object(),
        force=True,
        skip_vlm_metadata=True,
        use_case_id="wildfire",
        target_category="wildfire",
        target_pack_id="fireline",
        target_task="wildfire_close_look_candidate_review",
        date_windows=[
            ("pre", "2026-04-05", "2026-04-14"),
            ("active", "2026-04-15", "2026-04-18"),
        ],
        visual_mode="burn_scar",
    )

    assert sig is not None
    meta = json.loads((tmp_path / f"sh_{sig}_meta.json").read_text())
    assert meta["start_date"] == "2026-04-05"
    assert meta["end_date"] == "2026-04-18"
    assert meta["target_category"] == "wildfire"
    assert meta["target_pack_id"] == "fireline"
    assert len(meta["frame_images"]) == 2
    assert meta["spectral_bands"]["requested_bands"] == ["B12", "B08", "B04"]
    assert len(meta["spectral_bands"]["band_stats_by_frame"]) == 2
    assert meta["spectral_bands"]["band_stats_by_frame"][0]["derived_indices"]["ndvi"] == 0.7143
    assert (tmp_path / f"sh_{sig}_frames" / "01_pre.png").exists()
    assert (tmp_path / f"sh_{sig}_frames" / "02_active.png").exists()
