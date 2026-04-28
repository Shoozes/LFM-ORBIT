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
from core.scene_qc import INVALID_SCL_CLASSES, evaluate_scene_quality
import os

def _get_sentinel_instance_id():
    explicit = os.environ.get("SENTINEL_INSTANCE_ID", "").strip()
    if explicit:
        return explicit
    try:
        from core.config import resolve_sentinel_credentials

        return resolve_sentinel_credentials().instance_id.strip()
    except Exception:
        logger.debug("Unable to resolve Sentinel Hub instance id from configured credentials", exc_info=True)
        return ""

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

def _fetch_seasonal_baseline(bbox_coords: tuple, target_label: str, instance_id: str, years_back: int = 2) -> Optional[dict]:
    """
    Constructs a historical baseline using the same season from prior years.
    If target is '2024-08', fetches '2023-08' and '2022-08', merging them into a single stable baseline.
    """
    parts = target_label.split("-")
    if len(parts) < 2:
        return None

    year = int(parts[0])
    month = parts[1]

    valid_nirs, valid_reds, valid_swirs, qualities = [], [], [], []

    for past_year in range(year - years_back, year):
        past_label = f"{past_year}-{month}"
        start_date, end_date = _date_range_for_label(past_label)

        bands = _fetch_window_bands(bbox_coords, start_date, end_date, instance_id)
        if bands is not None and not bands.get("cloud_degraded"):
            valid_nirs.append(bands["nir"])
            valid_reds.append(bands["red"])
            valid_swirs.append(bands["swir"])
            qualities.append(bands["quality"])

    if not valid_nirs:
        return None

    return {
        "nir": round(sum(valid_nirs) / len(valid_nirs), 4),
        "red": round(sum(valid_reds) / len(valid_reds), 4),
        "swir": round(sum(valid_swirs) / len(valid_swirs), 4),
        "quality": round(sum(qualities) / len(qualities), 4),
        "cloud_degraded": False,
    }

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
            scl_band = arr[:, :, 3]
            qc_result = evaluate_scene_quality(scl_band)

            if not qc_result["accepted"] and len(data_list) > 1:
                # If we have multiple scenes and this one is entirely garbage, skip it
                logger.debug(f"Skipping scene frame due to QC flags: {qc_result['reasons']}")
                continue

            valid_mask = ~np.isin(scl_band.astype(int), INVALID_SCL_CLASSES)
            valid_count = valid_mask.sum()
            pixel_count = arr.shape[0] * arr.shape[1]

            if valid_count > 0:
                red_band = arr[:, :, 0]
                nir_band = arr[:, :, 1]
                swir_band = arr[:, :, 2]
                reds.extend(red_band[valid_mask].tolist())
                nirs.extend(nir_band[valid_mask].tolist())
                swirs.extend(swir_band[valid_mask].tolist())
                scls.append((valid_count, pixel_count))

        if not reds:
            return None

        total_valid = sum(v for v, p in scls)
        total_pixels = sum(p for v, p in scls)
        quality = round(total_valid / max(1, total_pixels), 4)

        from core.config import DETECTION
        cloud_flag = quality < DETECTION.min_quality_threshold

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

    after_from, after_to = _date_range_for_label(REGION.after_label)

    logger.info("sentinelhub_direct: fetching windows for cell %s", cell_id)

    # Switch to seasonal baseline rather than hardcoded pairwise month compare
    before_bands = _fetch_seasonal_baseline(bbox, REGION.after_label, instance_id, years_back=2)
    if not before_bands:
        # Fall back to pairwise baseline if seasonal failed to reconstruct (e.g., cloudy past years)
        before_from, before_to = _date_range_for_label(REGION.before_label)
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
            "label": f"Baseline {REGION.after_label} (-2Y)",
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
