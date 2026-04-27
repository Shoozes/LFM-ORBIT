import json
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pathlib import Path
import math

# We will use geopandas and shapely to perform robust spatial indexing and calculations.
import geopandas as gpd
from shapely.geometry import shape, Polygon, mapping
from core.paths import get_boundaries_dir

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class BoundaryMatch:
    layer_type: str
    source_name: str
    feature_id: str
    feature_name: Optional[str]
    overlap_area_m2: float
    overlap_ratio: float
    distance_to_boundary_m: float

class AttributionEngine:
    """
    Engine to identify intersections between candidate loss polygons
    and governance boundaries (concessions, protected areas, etc).
    """
    def __init__(self, boundaries_dir: str | Path | None = None):
        self.boundaries_dir = Path(boundaries_dir) if boundaries_dir is not None else get_boundaries_dir()
        self.layers: Dict[str, gpd.GeoDataFrame] = {}
        self._load_layers()

    def _load_layers(self):
        """Load internal standardized boundaries into local memory with spatial indexing."""
        if not self.boundaries_dir.exists():
            return

        for geojson_path in self.boundaries_dir.glob("*.geojson"):
            try:
                gdf = gpd.read_file(geojson_path)
                # Ensure projected CRS for accurate meters area/distance calculations.
                # We'll use EPSG:3857 (Web Mercator) as an approximation for meters.
                # All inputs should be EPSG:4326.
                if gdf.crs and gdf.crs.to_string() != "EPSG:3857":
                    gdf = gdf.to_crs(epsg=3857)

                layer_name = geojson_path.stem
                self.layers[layer_name] = gdf
                logger.info(f"Loaded boundary layer: {layer_name} with {len(gdf)} features")
            except Exception as e:
                logger.warning(f"Failed to load boundary layer {geojson_path}: {e}")

    def evaluate_polygon(self, geojson_polygon: dict) -> List[BoundaryMatch]:
        """
        Evaluate a candidate geographic polygon (EPSG:4326) against all loaded layers.

        Args:
            geojson_polygon: A dictionary representing a GeoJSON Polygon feature.
        """
        if not self.layers:
            return []

        try:
            # Convert candidate polygon to shapely geometry and project to Web Mercator (EPSG:3857)
            candidate_geom = shape(geojson_polygon)
            # Create temporary GeoDataFrame to project
            candidate_gdf = gpd.GeoDataFrame(geometry=[candidate_geom], crs="EPSG:4326")
            candidate_gdf_proj = candidate_gdf.to_crs(epsg=3857)
            candidate_proj_geom = candidate_gdf_proj.geometry.iloc[0]

            candidate_area = candidate_proj_geom.area
            if candidate_area <= 0:
                return []

        except Exception as e:
            logger.warning(f"Invalid polygon geometry provided to AttributionEngine: {e}")
            return []

        matches = []

        for layer_name, layer_gdf in self.layers.items():
            # To find nearby boundaries, query sindex with a 5000m buffer
            candidate_buffered = candidate_proj_geom.buffer(5000)
            possible_matches_index = list(layer_gdf.sindex.intersection(candidate_buffered.bounds))
            possible_matches = layer_gdf.iloc[possible_matches_index]

            for idx, feature in possible_matches.iterrows():
                geom = feature.geometry
                if not geom.is_valid:
                    continue

                if geom.intersects(candidate_proj_geom):
                    intersection = geom.intersection(candidate_proj_geom)
                    overlap_area = intersection.area
                    overlap_ratio = overlap_area / candidate_area

                    matches.append(BoundaryMatch(
                        layer_type=feature.get("layer_type", "unknown_layer"),
                        source_name=feature.get("source_name", layer_name),
                        feature_id=str(feature.get("original_feature_id", idx)),
                        feature_name=feature.get("name", feature.get("feature_name", None)),
                        overlap_area_m2=round(overlap_area, 2),
                        overlap_ratio=round(overlap_ratio, 4),
                        distance_to_boundary_m=0.0
                    ))
                else:
                    # It's nearby but not intersecting
                    distance = geom.distance(candidate_proj_geom)
                    if distance < 5000: # only report within 5km
                        matches.append(BoundaryMatch(
                            layer_type=feature.get("layer_type", "unknown_layer"),
                            source_name=feature.get("source_name", layer_name),
                            feature_id=str(feature.get("original_feature_id", idx)),
                            feature_name=feature.get("name", feature.get("feature_name", None)),
                            overlap_area_m2=0.0,
                            overlap_ratio=0.0,
                            distance_to_boundary_m=round(distance, 2)
                        ))

        return sorted(matches, key=lambda x: (x.overlap_ratio, -x.distance_to_boundary_m), reverse=True)

# Singleton access
_engine = None

def get_attribution_engine() -> AttributionEngine:
    global _engine
    if _engine is None:
        _engine = AttributionEngine()
    return _engine
