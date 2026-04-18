"""
Narrow direct Sentinel Hub provider for LFM-ORBIT.

This module provides direct access to Sentinel Hub for local dev/testing
when the SimSat API is not available. It implements:

  - WMS-based band retrieval directly using the instance ID.
  - Real NDVI/NBR-ready band extraction (B04-red, B08-nir, B11-swir, SCL-quality)
  - Bbox/date handling for a single H3 cell

Observation source label: ``sentinelhub_direct_imagery``
"""

import logging
import math
import numpy as np
from typing import Optional
from core.grid import cell_to_boundary, cell_to_latlng
from core.config import (
    REGION,
    SentinelCredentials,
)
import os

def _get_sentinel_instance_id():
    return os.environ.get("SENTINEL_INSTANCE_ID", "")

logger = logging.getLogger(__name__)

def is_sentinelhub_available(creds: SentinelCredentials | None = None) -> bool:
    """Check whether Sentinel Hub credentials are available."""
    if creds is None:
        from core.config import resolve_sentinel_credentials
        creds = resolve_sentinel_credentials()
    return creds.available


def _cell_bbox(cell_id: str, buffer_deg: float = 0.02) -> tuple[float, float, float, float]:
    """Return a tight bbox (west, south, east, north) around a square cell."""
    boundary = cell_to_boundary(cell_id)
    lats = [p[0] for p in boundary]
    lngs = [p[1] for p in boundary]
    return (
        min(lngs) - buffer_deg,
        min(lats) - buffer_deg,
        max(lngs) + buffer_deg,
        max(lats) + buffer_deg,
    )


def _date_range_for_label(label: str) -> tuple[str, str]:
    """Convert label '2024-06' to a start, end range."""
    parts = label.split("-")
    year = int(parts[0])
    month = int(parts[1]) if len(parts) > 1 else 6

    from_date = f"{year}-{month:02d}-01"
    if month == 12:
        to_date = f"{year + 1}-01-01"
    else:
        to_date = f"{year}-{month + 1:02d}-01"

    return from_date, to_date

EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B04", "B08", "B11", "SCL"], units: "DN" }],
    output: { bands: 4, sampleType: "FLOAT32" }
  };
}
function evaluatePixel(sample) {
  return [sample.B04 / 10000, sample.B08 / 10000, sample.B11 / 10000, sample.SCL];
}
"""

def _fetch_window_bands(bbox_coords: tuple, start_date: str, end_date: str, instance_id: str) -> Optional[dict]:
    try:
        from sentinelhub import BBox, CRS, WmsRequest, MimeType, DataCollection, SHConfig, CustomUrlParam
        config = SHConfig()
        config.instance_id = instance_id
        config.sh_client_id = ''
        config.sh_client_secret = ''
        
        box = BBox(bbox=bbox_coords, crs=CRS.WGS84)
        
        req = WmsRequest(
            data_collection=DataCollection.SENTINEL2_L2A,
            layer='1_TRUE-COLOR-L1C',  # Mock valid string, evalscript will overwrite band logic entirely
            bbox=box,
            time=(start_date, end_date),
            width=64,
            height=64,
            maxcc=0.4,
            image_format=MimeType.TIFF,
            custom_url_params={CustomUrlParam.EVALSCRIPT: EVALSCRIPT},
            config=config
        )
        
        data_list = req.get_data()
        if not data_list:
            return None
            
        # Merge all available frames (often just 1 or 2 good ones)
        reds, nirs, swirs, scls = [], [], [], []
        
        for arr in data_list:
            red_band = arr[:, :, 0]
            nir_band = arr[:, :, 1]
            swir_band = arr[:, :, 2]
            scl_band = arr[:, :, 3]
            
            valid_mask = ~np.isin(scl_band.astype(int), [0, 1, 3, 8, 9, 10])
            valid_count = valid_mask.sum()
            pixel_count = arr.shape[0] * arr.shape[1]
            
            if valid_count > 0:
                reds.extend(red_band[valid_mask].tolist())
                nirs.extend(nir_band[valid_mask].tolist())
                swirs.extend(swir_band[valid_mask].tolist())
                scls.append((valid_count, pixel_count))

        if not reds:
            return None
            
        total_valid = sum(v for v, p in scls)
        total_pixels = sum(p for v, p in scls)
        quality = round(total_valid / max(1, total_pixels), 4)
        cloud_flag = quality < 0.7

        return {
            "nir": round(float(np.mean(nirs)), 4),
            "red": round(float(np.mean(reds)), 4),
            "swir": round(float(np.mean(swirs)), 4),
            "quality": quality,
            "cloud_degraded": cloud_flag,
        }

    except Exception as exc:
        logger.warning(f"WMS Band Fetch Failed: {exc}")
        return None

def fetch_sentinelhub_observations(
    cell_id: str,
    creds: SentinelCredentials | None = None,
) -> Optional[dict]:
    instance_id = _get_sentinel_instance_id()
    if not instance_id:
        return None

    bbox = _cell_bbox(cell_id)
    centroid_lat, centroid_lng = cell_to_latlng(cell_id)

    before_from, before_to = _date_range_for_label(REGION.before_label)
    after_from, after_to = _date_range_for_label(REGION.after_label)

    logger.info("sentinelhub_direct: fetching windows for cell %s", cell_id)
    before_bands = _fetch_window_bands(bbox, before_from, before_to, instance_id)
    if not before_bands:
        return None

    after_bands = _fetch_window_bands(bbox, after_from, after_to, instance_id)
    if not after_bands:
        return None

    before_flags = ["sentinelhub_wms_real_bands"]
    after_flags = ["sentinelhub_wms_real_bands"]
    if before_bands.get("cloud_degraded"):
        before_flags.append("cloud_degraded")
    if after_bands.get("cloud_degraded"):
        after_flags.append("cloud_degraded")

    return {
        "source": "sentinelhub_direct_imagery",
        "cell_id": cell_id,
        "centroid_lat": round(centroid_lat, 6),
        "centroid_lng": round(centroid_lng, 6),
        "before": {
            "label": REGION.before_label,
            "quality": before_bands["quality"],
            "bands": {
                "nir": before_bands["nir"],
                "red": before_bands["red"],
                "swir": before_bands["swir"],
            },
            "flags": before_flags,
        },
        "after": {
            "label": REGION.after_label,
            "quality": after_bands["quality"],
            "bands": {
                "nir": after_bands["nir"],
                "red": after_bands["red"],
                "swir": after_bands["swir"],
            },
            "flags": after_flags,
        },
    }
