from __future__ import annotations

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
