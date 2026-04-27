import pytest
import geopandas as gpd
from shapely.geometry import Polygon
import os
import shutil

from core.overlays.attribution import AttributionEngine

@pytest.fixture
def mock_boundaries_dir(tmp_path):
    boundaries_dir = tmp_path / "boundaries"
    boundaries_dir.mkdir()

    # Create a mock polygon representing completely overlapping context
    poly1 = Polygon([(-60.0, -3.0), (-60.0, -3.1), (-59.9, -3.1), (-59.9, -3.0)])
    gdf1 = gpd.GeoDataFrame(
        {"layer_type": ["concession"], "source_name": ["test_source"], "name": ["Overlapping Concession"]},
        geometry=[poly1],
        crs="EPSG:4326"
    )
    gdf1.to_file(boundaries_dir / "overlap.geojson", driver="GeoJSON")

    # Create a mock polygon that is 2km away (so no overlap, but nearest check should hit)
    poly2 = Polygon([(-60.0, -2.96), (-60.0, -2.98), (-59.9, -2.98), (-59.9, -2.96)])
    gdf2 = gpd.GeoDataFrame(
        {"layer_type": ["protected"], "source_name": ["test_source"], "name": ["Nearby Park"]},
        geometry=[poly2],
        crs="EPSG:4326"
    )
    gdf2.to_file(boundaries_dir / "nearby.geojson", driver="GeoJSON")

    return str(boundaries_dir)

def test_attribution_engine_overlap(mock_boundaries_dir):
    engine = AttributionEngine(mock_boundaries_dir)

    # Create candidate polygon exactly inside poly1 bounding box
    candidate_poly = {
        "type": "Polygon",
        "coordinates": [[
            [-60.0, -3.0],
            [-60.0, -3.05],
            [-59.95, -3.05],
            [-59.95, -3.0],
            [-60.0, -3.0]
        ]]
    }

    matches = engine.evaluate_polygon(candidate_poly)

    assert len(matches) == 2

    # First match should be the overlapping one
    assert matches[0].feature_name == "Overlapping Concession"
    assert matches[0].overlap_ratio > 0.99

    # Second match should be the nearby one
    assert matches[1].feature_name == "Nearby Park"
    assert matches[1].overlap_ratio == 0.0
    assert matches[1].distance_to_boundary_m > 0
