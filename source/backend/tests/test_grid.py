from core.grid import generate_scan_grid


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