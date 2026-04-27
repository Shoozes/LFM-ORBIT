import pytest

from core.grid import generate_grid_for_bbox, generate_scan_grid, is_supported_cell_id, normalize_bbox


def test_generate_scan_grid_is_deterministic():
    first = generate_scan_grid(-3.119, -60.025, resolution=5, ring_size=2)
    second = generate_scan_grid(-3.119, -60.025, resolution=5, ring_size=2)

    assert first == second
    assert first["type"] == "FeatureCollection"
    assert len(first["features"]) > 0


def test_generate_scan_grid_features_are_geojson_ready():
    grid = generate_scan_grid(-3.119, -60.025, resolution=5, ring_size=1)
    feature = grid["features"][0]
    ring = feature["geometry"]["coordinates"][0]

    assert feature["id"] == feature["properties"]["cell_id"]
    assert ring[0] == ring[-1]
    assert len(ring[0]) == 2


def test_normalize_bbox_accepts_valid_wgs84_bounds():
    assert normalize_bbox(["-62", "-4", "-60", "-2"]) == [-62.0, -4.0, -60.0, -2.0]


def test_normalize_bbox_rejects_invalid_bounds():
    with pytest.raises(ValueError, match="west < east"):
        normalize_bbox([-60.0, -4.0, -62.0, -2.0])

    with pytest.raises(ValueError, match="south < north"):
        normalize_bbox([-62.0, -2.0, -60.0, -4.0])


def test_generate_grid_for_bbox_rejects_invalid_shape():
    with pytest.raises(ValueError, match="exactly four"):
        generate_grid_for_bbox([-62.0, -4.0, -60.0])


def test_supported_cell_id_validation_is_strict_for_current_grid():
    assert is_supported_cell_id("sq_-10.0_-63.0") is True
    assert is_supported_cell_id("85283473fffffff") is False
    assert is_supported_cell_id("sq_not_a_number_-63.0") is False
    assert is_supported_cell_id("sq_-10.0_-63.0_extra") is False
