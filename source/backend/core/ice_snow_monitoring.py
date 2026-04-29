"""Ice/snow extent scoring for Sentinel-2 L2A evidence lanes."""

from __future__ import annotations

import math
import re
from statistics import mean
from typing import Any

import numpy as np

from core.config import DETECTION
from core.indices import compute_ndsi, compute_ndwi
from core.scene_qc import CLOUD_SCL_CLASSES, INVALID_SCL_CLASSES


ICE_SNOW_USE_CASE_ID = "ice_snow_extent"
ICE_SNOW_TARGET_TASK = "ice_snow_extent_monitoring"
ICE_SNOW_TARGET_CATEGORY = "cryosphere"

SCL_WATER_CLASS = 6
SCL_SNOW_ICE_CLASS = 11

MIN_SNOW_NDSI = 0.40
MIN_SNOW_GREEN = 0.20
MAX_SNOW_SWIR1 = 0.45
MIN_SNOW_RATIO_FOR_PERSISTENCE = 0.08
SIGNIFICANT_RATIO_DELTA = 0.08
SIGNIFICANT_NDSI_DELTA = 0.08
MAX_CLOUD_PIXEL_RATIO = 0.35


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(result):
        return default
    return result


def _round(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _first_value(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _band(frame: dict[str, Any], *keys: str) -> Any:
    bands = frame.get("bands") if isinstance(frame.get("bands"), dict) else frame
    return _first_value(bands, keys)


def _as_array(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    try:
        arr = np.asarray(value, dtype=float)
    except (TypeError, ValueError):
        return None
    if arr.ndim == 0:
        return None
    return arr


def _normalized_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    denominator = a + b
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(denominator > 0, (a - b) / denominator, 0.0)
    return np.nan_to_num(result, nan=0.0, posinf=0.0, neginf=0.0)


def _scalar_scl_ratio(frame: dict[str, Any], key: str) -> float:
    scl = frame.get("scl")
    if isinstance(scl, dict):
        return _scl_fraction_value(scl, key)
    fractions = frame.get("scl_class_fractions")
    if isinstance(fractions, dict):
        return _scl_fraction_value(fractions, key)
    return 0.0


def _scl_fraction_value(fractions: dict[Any, Any], key: str) -> float:
    if key == "cloud":
        for alias in ("cloud", "clouds"):
            value = _safe_float(fractions.get(alias), None)
            if value is not None:
                return float(value)
        aliases = ("SCL_3", "SCL_8", "SCL_9", "SCL_10", "3", "8", "9", "10", 3, 8, 9, 10)
        return min(1.0, sum(float(_safe_float(fractions.get(alias), 0.0) or 0.0) for alias in aliases))
    if key == "snow_ice":
        aliases = ("snow_ice", "snow", "ice", "SCL_11", "11", 11)
    elif key == "water":
        aliases = ("water", "SCL_6", "6", 6)
    else:
        aliases = (key,)
    for alias in aliases:
        value = _safe_float(fractions.get(alias), None)
        if value is not None:
            return float(value)
    return 0.0


def _frame_month(label: str) -> int | None:
    match = re.search(r"\b\d{4}-(\d{2})", label)
    if not match:
        return None
    month = int(match.group(1))
    return month if 1 <= month <= 12 else None


def _date_range_from_summaries(summaries: list[dict[str, Any]]) -> dict[str, str | None]:
    labels = [str(item.get("date") or item.get("label") or "") for item in summaries]
    labels = [label for label in labels if label]
    return {
        "start": labels[0] if labels else None,
        "end": labels[-1] if labels else None,
    }


def _split_baseline_current(accepted: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(accepted) <= 2:
        return accepted[:1], accepted[-1:]
    midpoint = len(accepted) // 2
    return accepted[:midpoint], accepted[midpoint:]


def _mean_present(values: list[float | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return mean(present) if present else None


def _accepted_frame_dates(accepted: list[dict[str, Any]]) -> list[str]:
    return [
        str(item.get("date") or item.get("label") or "") for item in accepted if item.get("date") or item.get("label")
    ]


def _seasonal_warning(baseline: list[dict[str, Any]], current: list[dict[str, Any]]) -> bool:
    baseline_months = {
        month
        for month in (_frame_month(str(item.get("date") or item.get("label") or "")) for item in baseline)
        if month is not None
    }
    current_months = {
        month
        for month in (_frame_month(str(item.get("date") or item.get("label") or "")) for item in current)
        if month is not None
    }
    return bool(baseline_months and current_months and baseline_months != current_months)


def summarize_ice_snow_frame(frame: dict[str, Any]) -> dict[str, Any]:
    """Summarize one Sentinel-2 L2A frame for snow/ice scoring.

    Accepts either scalar frame summaries or pixel arrays. Array mode expects
    Green/B03 and SWIR1/B11, with optional NIR/B08 and SCL classes.
    """
    label = str(frame.get("label") or frame.get("date") or frame.get("timestamp") or "")
    green_raw = _band(frame, "green", "B03", "b03")
    swir1_raw = _band(frame, "swir1", "swir", "B11", "b11")
    nir_raw = _band(frame, "nir", "B08", "b08")
    scl_raw = frame["scl"] if "scl" in frame else frame.get("SCL")
    green_arr = _as_array(green_raw)
    swir1_arr = _as_array(swir1_raw)

    if green_arr is not None or swir1_arr is not None:
        return _summarize_array_frame(frame, label, green_arr, swir1_arr, _as_array(nir_raw), _as_array(scl_raw))

    green = _safe_float(green_raw)
    swir1 = _safe_float(swir1_raw)
    if green is None or swir1 is None:
        return {
            "label": label,
            "date": frame.get("date"),
            "accepted": False,
            "reason_codes": ["missing_green_or_swir1_band"],
            "ndsi": None,
            "ndwi": None,
            "snow_ice_ratio": 0.0,
            "valid_pixel_ratio": 0.0,
            "cloud_pixel_ratio": 0.0,
            "snow_ice_scl_ratio": 0.0,
            "water_ratio": 0.0,
        }

    ndsi = compute_ndsi(green, swir1)
    nir = _safe_float(nir_raw)
    ndwi = compute_ndwi(green, nir) if nir is not None else None
    valid_ratio = _safe_float(frame.get("valid_pixel_ratio"), _safe_float(frame.get("quality"), 1.0))
    cloud_ratio = _safe_float(frame.get("cloud_pixel_ratio"), _scalar_scl_ratio(frame, "cloud"))
    snow_ice_scl_ratio = _safe_float(frame.get("snow_ice_scl_ratio"), _scalar_scl_ratio(frame, "snow_ice"))
    water_ratio = _safe_float(frame.get("water_ratio"), _scalar_scl_ratio(frame, "water"))
    inferred_ratio = 1.0 if ndsi >= MIN_SNOW_NDSI and green >= MIN_SNOW_GREEN and swir1 <= MAX_SNOW_SWIR1 else 0.0
    snow_ice_ratio = _safe_float(
        frame.get("snow_ice_ratio", frame.get("snow_ice_mask_ratio")),
        max(float(snow_ice_scl_ratio or 0.0), inferred_ratio),
    )

    reasons = []
    if float(valid_ratio or 0.0) < DETECTION.min_quality_threshold:
        reasons.append("insufficient_valid_pixels")
    if float(cloud_ratio or 0.0) > MAX_CLOUD_PIXEL_RATIO:
        reasons.append("cloud_rejected")

    return {
        "label": label,
        "date": frame.get("date"),
        "accepted": not reasons,
        "reason_codes": reasons,
        "ndsi": _round(ndsi),
        "ndwi": _round(ndwi),
        "snow_ice_ratio": _round(float(snow_ice_ratio or 0.0)),
        "valid_pixel_ratio": _round(float(valid_ratio or 0.0)),
        "cloud_pixel_ratio": _round(float(cloud_ratio or 0.0)),
        "snow_ice_scl_ratio": _round(float(snow_ice_scl_ratio or 0.0)),
        "water_ratio": _round(float(water_ratio or 0.0)),
    }


def _summarize_array_frame(
    frame: dict[str, Any],
    label: str,
    green: np.ndarray | None,
    swir1: np.ndarray | None,
    nir: np.ndarray | None,
    scl: np.ndarray | None,
) -> dict[str, Any]:
    if green is None or swir1 is None or green.shape != swir1.shape:
        return {
            "label": label,
            "date": frame.get("date"),
            "accepted": False,
            "reason_codes": ["missing_green_or_swir1_band"],
            "ndsi": None,
            "ndwi": None,
            "snow_ice_ratio": 0.0,
            "valid_pixel_ratio": 0.0,
            "cloud_pixel_ratio": 0.0,
            "snow_ice_scl_ratio": 0.0,
            "water_ratio": 0.0,
        }

    total_pixels = int(green.size)
    finite_mask = np.isfinite(green) & np.isfinite(swir1)
    valid_mask = finite_mask.copy()
    cloud_ratio = 0.0
    water_ratio = 0.0
    snow_ice_scl_ratio = 0.0

    if scl is not None and scl.shape == green.shape:
        scl_int = scl.astype(int)
        cloud_mask = np.isin(scl_int, CLOUD_SCL_CLASSES)
        invalid_mask = np.isin(scl_int, INVALID_SCL_CLASSES)
        valid_mask &= ~invalid_mask
        cloud_ratio = float(cloud_mask.sum()) / max(1, total_pixels)
        water_ratio = float((scl_int == SCL_WATER_CLASS).sum()) / max(1, total_pixels)
        snow_ice_scl_ratio = float((scl_int == SCL_SNOW_ICE_CLASS).sum()) / max(1, total_pixels)

    valid_count = int(valid_mask.sum())
    valid_ratio = float(valid_count) / max(1, total_pixels)
    ndsi = _normalized_difference(green, swir1)
    ndwi = _normalized_difference(green, nir) if nir is not None and nir.shape == green.shape else None
    snow_mask = (
        valid_mask
        & (ndsi >= MIN_SNOW_NDSI)
        & (green >= MIN_SNOW_GREEN)
        & (swir1 <= MAX_SNOW_SWIR1)
    )
    if scl is not None and scl.shape == green.shape:
        snow_mask |= valid_mask & (scl.astype(int) == SCL_SNOW_ICE_CLASS) & (ndsi >= 0.25)
    snow_ice_ratio = float(snow_mask.sum()) / max(1, valid_count)

    reasons = []
    if valid_ratio < DETECTION.min_quality_threshold:
        reasons.append("insufficient_valid_pixels")
    if cloud_ratio > MAX_CLOUD_PIXEL_RATIO:
        reasons.append("cloud_rejected")

    return {
        "label": label,
        "date": frame.get("date"),
        "accepted": not reasons,
        "reason_codes": reasons,
        "ndsi": _round(float(np.mean(ndsi[valid_mask])) if valid_count else None),
        "ndwi": _round(float(np.mean(ndwi[valid_mask])) if ndwi is not None and valid_count else None),
        "snow_ice_ratio": _round(snow_ice_ratio),
        "valid_pixel_ratio": _round(valid_ratio),
        "cloud_pixel_ratio": _round(cloud_ratio),
        "snow_ice_scl_ratio": _round(snow_ice_scl_ratio),
        "water_ratio": _round(water_ratio),
    }


def score_ice_snow_extent(
    frames: list[dict[str, Any]],
    *,
    runtime_truth_mode: str = "replay",
    imagery_origin: str = "cached_api",
    observation_source: str = "seeded_sentinelhub_multispectral_replay",
    min_accepted_frames: int = 3,
) -> dict[str, Any]:
    """Score long-window snow/ice extent change from Sentinel-2 frame summaries."""
    summaries = [summarize_ice_snow_frame(frame) for frame in frames]
    accepted = [summary for summary in summaries if summary["accepted"]]
    rejected_cloud_frames = sum(
        1
        for summary in summaries
        if not summary["accepted"]
        and any(reason in {"cloud_rejected", "insufficient_valid_pixels"} for reason in summary["reason_codes"])
    )
    reason_codes: list[str] = []
    if rejected_cloud_frames:
        reason_codes.append("cloud_rejected")

    if len(accepted) < 2:
        reason_codes.append("insufficient_accepted_frames")
        return {
            "runtime_truth_mode": runtime_truth_mode,
            "imagery_origin": imagery_origin,
            "scoring_basis": "multispectral_bands",
            "observation_source": observation_source,
            "use_case": ICE_SNOW_USE_CASE_ID,
            "target_task": ICE_SNOW_TARGET_TASK,
            "target_category": ICE_SNOW_TARGET_CATEGORY,
            "date_range": _date_range_from_summaries(summaries),
            "accepted_frame_dates": _accepted_frame_dates(accepted),
            "accepted_frames": len(accepted),
            "rejected_cloud_frames": rejected_cloud_frames,
            "baseline_snow_ice_ratio": None,
            "current_snow_ice_ratio": None,
            "delta_ratio": 0.0,
            "baseline_ndsi": None,
            "current_ndsi": None,
            "delta_ndsi": 0.0,
            "change_score": 0.0,
            "raw_change_score": 0.0,
            "confidence": 0.18,
            "target_action": "defer",
            "reason_codes": reason_codes,
            "frame_summaries": summaries,
        }

    baseline, current = _split_baseline_current(accepted)
    baseline_ratio = _mean_present([item["snow_ice_ratio"] for item in baseline])
    current_ratio = _mean_present([item["snow_ice_ratio"] for item in current])
    baseline_ndsi = _mean_present([item["ndsi"] for item in baseline])
    current_ndsi = _mean_present([item["ndsi"] for item in current])
    delta_ratio = float(current_ratio or 0.0) - float(baseline_ratio or 0.0)
    delta_ndsi = float(current_ndsi or 0.0) - float(baseline_ndsi or 0.0)

    has_minimum_evidence = len(accepted) >= min_accepted_frames
    if not has_minimum_evidence:
        reason_codes.append("insufficient_accepted_frames")
    elif delta_ratio >= SIGNIFICANT_RATIO_DELTA or delta_ndsi >= SIGNIFICANT_NDSI_DELTA:
        reason_codes.append("ndsi_increase")
    elif delta_ratio <= -SIGNIFICANT_RATIO_DELTA or delta_ndsi <= -SIGNIFICANT_NDSI_DELTA:
        reason_codes.append("ndsi_decrease")

    persistent_frames = [
        item for item in accepted if float(item.get("snow_ice_ratio") or 0.0) >= MIN_SNOW_RATIO_FOR_PERSISTENCE
    ]
    if len(accepted) >= min_accepted_frames and len(persistent_frames) >= max(2, min_accepted_frames // 2):
        reason_codes.append("multi_frame_persistence")

    avg_snow_ice_scl = _mean_present([item["snow_ice_scl_ratio"] for item in accepted]) or 0.0
    if avg_snow_ice_scl >= 0.04:
        reason_codes.append("snow_ice_scl_support")

    avg_water_ratio = _mean_present([item["water_ratio"] for item in accepted]) or 0.0
    if avg_water_ratio >= 0.25:
        reason_codes.append("water_ice_ambiguity")

    if _seasonal_warning(baseline, current):
        reason_codes.append("seasonal_window_warning")

    if has_minimum_evidence and not any(code in reason_codes for code in ("ndsi_increase", "ndsi_decrease")):
        reason_codes.append("stable_snow_ice_extent")

    quality = _mean_present([item["valid_pixel_ratio"] for item in accepted]) or 0.0
    raw_change_score = min(1.0, abs(delta_ratio) * 3.0 + abs(delta_ndsi) * 0.5)
    change_score = raw_change_score if has_minimum_evidence else 0.0
    confidence = 0.32 + (quality * 0.25) + min(0.25, raw_change_score * 0.35)
    if "multi_frame_persistence" in reason_codes:
        confidence += 0.10
    if "snow_ice_scl_support" in reason_codes:
        confidence += 0.08
    if "water_ice_ambiguity" in reason_codes:
        confidence -= 0.10
    if "seasonal_window_warning" in reason_codes:
        confidence -= 0.08
    if not has_minimum_evidence:
        confidence = min(confidence - 0.12, 0.45)
    confidence = max(0.0, min(1.0, confidence))

    if not has_minimum_evidence:
        target_action = "defer"
    elif any(code in reason_codes for code in ("ndsi_increase", "ndsi_decrease")):
        target_action = "review"
    else:
        target_action = "monitor"

    return {
        "runtime_truth_mode": runtime_truth_mode,
        "imagery_origin": imagery_origin,
        "scoring_basis": "multispectral_bands",
        "observation_source": observation_source,
        "use_case": ICE_SNOW_USE_CASE_ID,
        "target_task": ICE_SNOW_TARGET_TASK,
        "target_category": ICE_SNOW_TARGET_CATEGORY,
        "date_range": _date_range_from_summaries(summaries),
        "accepted_frame_dates": _accepted_frame_dates(accepted),
        "accepted_frames": len(accepted),
        "rejected_cloud_frames": rejected_cloud_frames,
        "baseline_snow_ice_ratio": _round(baseline_ratio),
        "current_snow_ice_ratio": _round(current_ratio),
        "delta_ratio": _round(delta_ratio),
        "baseline_ndsi": _round(baseline_ndsi),
        "current_ndsi": _round(current_ndsi),
        "delta_ndsi": _round(delta_ndsi),
        "change_score": _round(change_score),
        "raw_change_score": _round(raw_change_score),
        "confidence": _round(confidence),
        "target_action": target_action,
        "reason_codes": reason_codes,
        "frame_summaries": summaries,
    }
