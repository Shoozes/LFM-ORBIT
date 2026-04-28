import pytest
import numpy as np
from core.scene_qc import evaluate_scene_quality

def test_scene_quality_perfect_scene():
    # 64x64 grid entirely Vegetation (class 4) and Bare Soils (class 5)
    scl_band = np.full((64, 64), 4)
    scl_band[0:10, 0:10] = 5

    result = evaluate_scene_quality(scl_band)

    assert result["accepted"] is True
    assert result["valid_pixel_ratio"] == 1.0
    assert result["cloud_pixel_ratio"] == 0.0
    assert "excessive_nodata_clipping" not in result["reasons"]

def test_scene_quality_rejects_heavy_clouds():
    # Mostly composed of Cloud high probability (class 9)
    scl_band = np.full((64, 64), 9)
    # A few veg pixels
    scl_band[0:5, 0:5] = 4

    result = evaluate_scene_quality(scl_band)

    assert result["accepted"] is False
    assert result["valid_pixel_ratio"] < 0.10
    assert result["cloud_pixel_ratio"] > 0.90
    assert "insufficient_valid_pixels" in result["reasons"]

def test_scene_quality_rejects_heavy_cirrus():
    # Mostly composed of thin cirrus (class 10)
    scl_band = np.full((64, 64), 10)
    scl_band[0:5, 0:5] = 4

    result = evaluate_scene_quality(scl_band)

    assert result["accepted"] is False
    assert result["valid_pixel_ratio"] < 0.10
    assert result["cloud_pixel_ratio"] > 0.90
    assert "insufficient_valid_pixels" in result["reasons"]

def test_scene_quality_rejects_edge_clipping():
    # Represents a scene at the edge of the satellite swath (class 0: NoData)
    scl_band = np.full((64, 64), 4)
    scl_band[:, 0:20] = 0 # 20 columns out of 64 are dropped

    result = evaluate_scene_quality(scl_band)

    assert result["accepted"] is False
    assert result["nodata_pixel_ratio"] > 0.15
    assert "excessive_nodata_clipping" in result["reasons"]
