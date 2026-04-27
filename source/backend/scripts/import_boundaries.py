import sys
import os
import argparse
from pathlib import Path
import logging

import geopandas as gpd
from core.paths import get_boundaries_dir

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("import_boundaries")

def import_boundaries(
    input_file: str,
    layer_name: str,
    layer_type: str,
    source_name: str,
    output_dir: str | None = None,
):
    """
    Ingest, normalize, index, and organize a raw boundary file.
    """
    input_path = Path(input_file)
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)

    out_dir = Path(output_dir) if output_dir else get_boundaries_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Loading {input_path}...")
    try:
        gdf = gpd.read_file(input_path)
    except Exception as e:
        logger.error(f"Failed to load file: {e}")
        sys.exit(1)

    logger.info(f"Loaded {len(gdf)} features. Original CRS: {gdf.crs}")

    # 1. Normalize CRS to WGS84 (EPSG:4326) for standard storage
    if gdf.crs is None or gdf.crs.to_string() != "EPSG:4326":
        logger.info("Projecting to EPSG:4326...")
        gdf = gdf.to_crs(epsg=4326)

    # 2. Repair invalid geometries
    invalid_count = (~gdf.is_valid).sum()
    if invalid_count > 0:
        logger.info(f"Repairing {invalid_count} invalid geometries...")
        gdf.geometry = gdf.geometry.make_valid()

    # Drop empty/null geometries
    gdf = gdf.dropna(subset=['geometry'])

    # 3. Attach metadata
    logger.info("Attaching standard metadata...")
    gdf["layer_type"] = layer_type
    gdf["source_name"] = source_name

    if "id" not in gdf.columns and "OBJECTID" not in gdf.columns:
        gdf["original_feature_id"] = gdf.index.astype(str)
    else:
        # attempt to preserve ID
        id_col = "id" if "id" in gdf.columns else "OBJECTID"
        gdf["original_feature_id"] = gdf[id_col].astype(str)

    if "name" not in gdf.columns and "NAME" in gdf.columns:
        gdf["name"] = gdf["NAME"]

    # 4. Save
    output_file = out_dir / f"{layer_name}.geojson"
    logger.info(f"Saving to {output_file}...")

    # Save as GeoJSON for simple native loading without specialized drivers
    gdf.to_file(output_file, driver="GeoJSON")
    logger.info("Import successful.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest boundary polygons.")
    parser.add_argument("input", help="Path to input shapefile/geojson")
    parser.add_argument("--name", required=True, help="Internal layer name (e.g. 'amazonas_concessions')")
    parser.add_argument("--type", required=True, help="Layer type (e.g. 'mining', 'logging', 'protected_area')")
    parser.add_argument("--source", required=True, help="Source attribution string")

    args = parser.parse_args()

    # Ensure correct working directory context
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    import_boundaries(
        input_file=args.input,
        layer_name=args.name,
        layer_type=args.type,
        source_name=args.source
    )
