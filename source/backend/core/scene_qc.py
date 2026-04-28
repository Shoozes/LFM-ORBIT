"""
Scene Quality Control gate for LFM Orbit.
Evaluates arrays for validity, cloud cover, and completeness before allowing analysis.
"""

from typing import Literal, TypedDict
import numpy as np
from core.config import DETECTION

class SceneEligibility(TypedDict):
    accepted: bool
    valid_pixel_ratio: float
    cloud_pixel_ratio: float
    nodata_pixel_ratio: float
    total_pixels: int
    reasons: list[str]


CLOUD_SCL_CLASSES = [3, 8, 9, 10]
INVALID_SCL_CLASSES = [0, 1, *CLOUD_SCL_CLASSES]

def evaluate_scene_quality(
    scl_band_array: np.ndarray,
) -> SceneEligibility:
    """
    Evaluates a single Sentinel SCL band array to ensure it meets strict analysis requirements.
    Masking logic:
    0: No Data
    1: Saturated or defective
    3: Cloud Shadows
    8: Cloud Medium Probability
    9: Cloud High Probability
    10: Cirrus
    """
    total_pixels = scl_band_array.size
    if total_pixels == 0:
        return {
            "accepted": False,
            "valid_pixel_ratio": 0.0,
            "cloud_pixel_ratio": 0.0,
            "nodata_pixel_ratio": 0.0,
            "total_pixels": 0,
            "reasons": ["empty_scene_array"],
        }

    # 0 is usually the NoData class
    nodata_mask = (scl_band_array == 0)
    nodata_count = nodata_mask.sum()

    cloud_mask = np.isin(scl_band_array.astype(int), CLOUD_SCL_CLASSES)
    invalid_mask = np.isin(scl_band_array.astype(int), INVALID_SCL_CLASSES)

    valid_mask = ~(nodata_mask | invalid_mask)
    valid_count = valid_mask.sum()

    valid_ratio = float(valid_count) / float(total_pixels)
    cloud_ratio = float(cloud_mask.sum()) / float(total_pixels)
    nodata_ratio = float(nodata_count) / float(total_pixels)

    reasons = []
    if nodata_ratio > 0.15:
        reasons.append("excessive_nodata_clipping")

    if valid_ratio < DETECTION.min_quality_threshold:
        reasons.append("insufficient_valid_pixels")

    accepted = len(reasons) == 0

    return {
        "accepted": accepted,
        "valid_pixel_ratio": round(valid_ratio, 4),
        "cloud_pixel_ratio": round(cloud_ratio, 4),
        "nodata_pixel_ratio": round(nodata_ratio, 4),
        "total_pixels": total_pixels,
        "reasons": reasons,
    }
