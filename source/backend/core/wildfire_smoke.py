"""Wildfire smoke/cloud confidence assist for Sentinel-2 evidence."""

from __future__ import annotations

import math
from statistics import mean
from typing import Any

from core.indices import (
    compute_blue_green_haze_score,
    compute_dnbr,
    compute_ndmi_s2,
    compute_nbr_s2,
    compute_ndvi,
    compute_visible_whiteness,
)


WILDFIRE_USE_CASE_ID = "wildfire"
WILDFIRE_SMOKE_TARGET_TASK = "wildfire_smoke_cloud_confidence"
WILDFIRE_TARGET_CATEGORY = "wildfire"
REQUIRED_BANDS = ("blue", "green", "red", "nir", "swir1", "swir2")


def _safe_float(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, dict) and "mean" in value:
        value = value.get("mean")
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


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _band(frame: dict[str, Any], *keys: str) -> Any:
    bands = frame.get("bands") if isinstance(frame.get("bands"), dict) else frame
    for key in keys:
        if key in bands:
            return bands[key]
        if key in frame:
            return frame[key]
    return None


def _probability(value: Any, *, scale_255: bool = False) -> float:
    raw = _safe_float(value, 0.0) or 0.0
    if raw > 1.0:
        return _clamp(raw / (255.0 if scale_255 else 100.0))
    return _clamp(raw)


def _scl_fraction_value(frame: dict[str, Any], key: str) -> float:
    fractions = frame.get("scl_class_fractions")
    if not isinstance(fractions, dict):
        fractions = frame.get("scl") if isinstance(frame.get("scl"), dict) else {}
    if key == "cloud":
        direct = _safe_float(_band(frame, "scl_cloud_ratio", "cloud_pixel_ratio", "cloud_ratio"), None)
        if direct is not None:
            return _clamp(direct)
        aliases = ("cloud", "clouds", "SCL_3", "SCL_8", "SCL_9", "SCL_10", "3", "8", "9", "10", 3, 8, 9, 10)
        return _clamp(sum(float(_safe_float(fractions.get(alias), 0.0) or 0.0) for alias in aliases))
    direct = _safe_float(_band(frame, "scl_snow_ratio", "snow_ice_scl_ratio", "snow_ice_ratio"), None)
    if direct is not None:
        return _clamp(direct)
    aliases = ("snow_ice", "snow", "ice", "SCL_11", "11", 11)
    return _clamp(sum(float(_safe_float(fractions.get(alias), 0.0) or 0.0) for alias in aliases))


def _mean_present(values: list[float | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return mean(present) if present else None


def _hotspot_support(hotspot_context: dict[str, Any] | None) -> float:
    if not hotspot_context:
        return 0.0
    for key in ("hotspot_support", "support", "score"):
        value = _safe_float(hotspot_context.get(key), None)
        if value is not None:
            return _clamp(value / 100.0 if value > 1.0 else value)
    confidence = _safe_float(hotspot_context.get("confidence"), None)
    if confidence is not None:
        return _clamp(confidence / 100.0 if confidence > 1.0 else confidence)
    label = str(
        hotspot_context.get("viirs_confidence")
        or hotspot_context.get("modis_confidence")
        or hotspot_context.get("confidence_label")
        or ""
    ).lower()
    if label == "high":
        return 0.9
    if label == "nominal":
        return 0.7
    if label == "low":
        return 0.35
    if int(_safe_float(hotspot_context.get("active_fire_count"), 0.0) or 0) > 0:
        return 0.7
    return 0.0


def _proxy_or_fallback_source(runtime_truth_mode: str, imagery_origin: str, observation_source: str) -> bool:
    source = " ".join([runtime_truth_mode, imagery_origin, observation_source]).lower()
    return any(token in source for token in ("proxy", "fallback", "simsat", "synthetic", "mock"))


def _date_range_from_summaries(summaries: list[dict[str, Any]]) -> dict[str, str | None]:
    labels = [str(item.get("date") or item.get("label") or "") for item in summaries]
    labels = [label for label in labels if label]
    return {"start": labels[0] if labels else None, "end": labels[-1] if labels else None}


def _missing_result(
    summaries: list[dict[str, Any]],
    *,
    runtime_truth_mode: str,
    imagery_origin: str,
    observation_source: str,
    reason_codes: list[str],
) -> dict[str, Any]:
    return {
        "runtime_truth_mode": runtime_truth_mode,
        "imagery_origin": imagery_origin,
        "scoring_basis": "multispectral_bands",
        "observation_source": observation_source,
        "use_case": WILDFIRE_USE_CASE_ID,
        "target_task": WILDFIRE_SMOKE_TARGET_TASK,
        "target_category": WILDFIRE_TARGET_CATEGORY,
        "target_action": "defer",
        "date_range": _date_range_from_summaries(summaries),
        "accepted_frames": 0,
        "smoke_likelihood": 0.0,
        "cloud_likelihood": 0.0,
        "burn_likelihood": 0.0,
        "hotspot_support": 0.0,
        "confidence_delta": -0.25,
        "final_confidence": 0.12,
        "reason_codes": list(dict.fromkeys(reason_codes)),
        "frame_summaries": summaries,
        "provenance": {
            "scoring_basis": "multispectral_bands",
            "required_bands": "B02,B03,B04,B08,B11,B12,SCL,CLD,CLP",
            "source_guard": "no_proxy_fire_confirmation",
        },
    }


def summarize_wildfire_frame(frame: dict[str, Any]) -> dict[str, Any]:
    """Summarize one Sentinel-2 frame for smoke/cloud/burn scoring."""
    label = str(frame.get("label") or frame.get("date") or frame.get("timestamp") or "")
    blue = _safe_float(_band(frame, "blue", "B02", "b02", "B02_blue"))
    green = _safe_float(_band(frame, "green", "B03", "b03", "B03_green"))
    red = _safe_float(_band(frame, "red", "B04", "b04", "B04_red"))
    nir = _safe_float(_band(frame, "nir", "B08", "b08", "B08_nir"))
    swir1 = _safe_float(_band(frame, "swir1", "B11", "b11", "B11_swir1"))
    swir2 = _safe_float(_band(frame, "swir2", "swir", "B12", "b12", "B12_swir2"))
    missing = [
        name
        for name, value in (
            ("blue", blue),
            ("green", green),
            ("red", red),
            ("nir", nir),
            ("swir1", swir1),
            ("swir2", swir2),
        )
        if value is None
    ]

    if missing:
        return {
            "label": label,
            "date": frame.get("date"),
            "accepted": False,
            "reason_codes": ["missing_required_bands"],
            "missing_bands": missing,
            "valid_pixel_ratio": 0.0,
            "cloud_likelihood": 0.0,
            "smoke_cue": 0.0,
        }

    assert blue is not None and green is not None and red is not None
    assert nir is not None and swir1 is not None and swir2 is not None

    valid_ratio = _safe_float(_band(frame, "valid_pixel_ratio", "data_mask_ratio", "quality"), 1.0) or 0.0
    scl_cloud_ratio = _scl_fraction_value(frame, "cloud")
    cloud_probability = max(
        _probability(_band(frame, "cloud_probability", "CLD", "cld")),
        _probability(_band(frame, "cloud_probability_clp", "CLP", "clp"), scale_255=True),
    )
    snow_ice_ratio = _scl_fraction_value(frame, "snow_ice")
    whiteness = compute_visible_whiteness(red, green, blue)
    brightness = _clamp((red + green + blue) / 3.0)
    haze_score = compute_blue_green_haze_score(blue, green, red)
    nbr = compute_nbr_s2(nir, swir2)
    ndmi = compute_ndmi_s2(nir, swir1)
    ndvi = compute_ndvi(nir, red)

    reason_codes: list[str] = []
    if scl_cloud_ratio >= 0.35:
        reason_codes.append("scl_cloud_support")
    if cloud_probability >= 0.35:
        reason_codes.append("cloud_probability_support")
    if snow_ice_ratio >= 0.20:
        reason_codes.append("snow_ice_ambiguity_not_smoke")
    if haze_score >= 0.08:
        reason_codes.append("blue_green_haze_support")

    return {
        "label": label,
        "date": frame.get("date"),
        "accepted": True,
        "reason_codes": reason_codes,
        "blue": _round(blue),
        "green": _round(green),
        "red": _round(red),
        "nir": _round(nir),
        "swir1": _round(swir1),
        "swir2": _round(swir2),
        "ndvi": _round(ndvi),
        "nbr": _round(nbr),
        "ndmi": _round(ndmi),
        "visible_whiteness": _round(whiteness),
        "visible_brightness": _round(brightness),
        "blue_green_haze_score": _round(haze_score),
        "scl_cloud_ratio": _round(scl_cloud_ratio),
        "cloud_probability": _round(cloud_probability),
        "snow_ice_ratio": _round(snow_ice_ratio),
        "valid_pixel_ratio": _round(_clamp(valid_ratio)),
    }


def score_wildfire_smoke_assist(
    frames: list[dict[str, Any]],
    *,
    hotspot_context: dict[str, Any] | None = None,
    runtime_truth_mode: str = "replay",
    imagery_origin: str = "cached_api",
    observation_source: str = "unknown",
    min_accepted_frames: int = 2,
) -> dict[str, Any]:
    """Return smoke/cloud/burn likelihoods, confidence delta, action, and reason codes."""
    summaries = [summarize_wildfire_frame(frame) for frame in frames]
    reason_codes: list[str] = []
    for summary in summaries:
        reason_codes.extend(summary.get("reason_codes", []))

    accepted = [summary for summary in summaries if summary.get("accepted")]
    if not accepted or any("missing_required_bands" in summary.get("reason_codes", []) for summary in summaries):
        reason_codes.append("missing_required_bands")
        return _missing_result(
            summaries,
            runtime_truth_mode=runtime_truth_mode,
            imagery_origin=imagery_origin,
            observation_source=observation_source,
            reason_codes=reason_codes,
        )

    hotspot = _hotspot_support(hotspot_context)
    baseline = accepted[0]
    current = accepted[-1]
    dnbr_raw = compute_dnbr(float(baseline["nbr"]), float(current["nbr"]))
    ndmi_drop_raw = float(baseline["ndmi"]) - float(current["ndmi"])
    ndvi_drop_raw = float(baseline["ndvi"]) - float(current["ndvi"])
    dnbr_score = _clamp(dnbr_raw / 0.45)
    nbr_drop_score = _clamp(dnbr_raw / 0.25)
    ndmi_drop_score = _clamp(ndmi_drop_raw / 0.30)
    ndvi_drop_score = _clamp(ndvi_drop_raw / 0.35)
    swir2_char_score = _clamp((float(current["swir2"]) - float(current["nir"]) + 0.18) * 2.5)
    burn_likelihood = _clamp(
        (0.45 * dnbr_score)
        + (0.20 * nbr_drop_score)
        + (0.15 * ndmi_drop_score)
        + (0.10 * ndvi_drop_score)
        + (0.10 * swir2_char_score)
    )

    scl_cloud_ratio = max(float(summary.get("scl_cloud_ratio") or 0.0) for summary in accepted)
    cloud_probability = max(float(summary.get("cloud_probability") or 0.0) for summary in accepted)
    visible_whiteness = float(current.get("visible_whiteness") or 0.0)
    visible_brightness = float(current.get("visible_brightness") or 0.0)
    snow_ice_ratio = _mean_present([summary.get("snow_ice_ratio") for summary in accepted]) or 0.0
    cloud_likelihood = _clamp(
        (0.40 * scl_cloud_ratio)
        + (0.25 * cloud_probability)
        + (0.20 * visible_whiteness)
        + (0.15 * visible_brightness)
        + (0.10 * snow_ice_ratio)
    )

    haze_score = float(current.get("blue_green_haze_score") or 0.0)
    non_cloud_scl_support = _clamp(1.0 - max(scl_cloud_ratio, cloud_probability, snow_ice_ratio))
    plume_softness_score = _clamp(visible_whiteness * (1.0 - (cloud_likelihood * 0.6)))
    haze_persistent_frames = [
        summary for summary in accepted if float(summary.get("blue_green_haze_score") or 0.0) >= 0.08
    ]
    temporal_plume_persistence = _clamp(len(haze_persistent_frames) / max(1, min_accepted_frames))
    smoke_likelihood = _clamp(
        (0.30 * haze_score)
        + (0.20 * non_cloud_scl_support)
        + (0.15 * plume_softness_score)
        + (0.15 * temporal_plume_persistence)
        + (0.10 * burn_likelihood)
        + (0.10 * hotspot)
    )

    if len(accepted) < min_accepted_frames:
        reason_codes.append("insufficient_accepted_frames")
        smoke_likelihood *= 0.75
        burn_likelihood *= 0.75

    if haze_score >= 0.08 and smoke_likelihood >= 0.35 and cloud_likelihood < 0.65:
        reason_codes.append("smoke_plume_candidate")
    if burn_likelihood >= 0.35:
        reason_codes.append("dnbr_burn_support")
    if hotspot >= 0.70:
        reason_codes.append("hotspot_support")
    else:
        reason_codes.append("no_hotspot_support")

    if snow_ice_ratio >= 0.35 and cloud_likelihood >= 0.45:
        target_action = "defer"
        reason_codes.append("snow_ice_ambiguity_not_smoke")
    elif cloud_likelihood >= 0.65 and smoke_likelihood < 0.55:
        target_action = "defer"
        reason_codes.append("cloud_like_white_plume")
    elif burn_likelihood >= 0.55 and smoke_likelihood >= 0.45:
        target_action = "downlink_now"
        reason_codes.append("smoke_with_burn_support")
    elif hotspot >= 0.70 and smoke_likelihood >= 0.45:
        target_action = "downlink_now"
        reason_codes.append("smoke_with_hotspot_support")
    elif smoke_likelihood >= 0.60 and cloud_likelihood < 0.45:
        target_action = "review"
        reason_codes.append("smoke_plume_candidate")
    elif burn_likelihood >= 0.55 and cloud_likelihood < 0.55:
        target_action = "review"
        reason_codes.append("burn_scar_candidate")
    else:
        target_action = "defer"

    if target_action == "defer" and cloud_likelihood >= 0.55:
        reason_codes.append("defer_smoke_cloud_ambiguity")

    confidence_delta = _clamp(
        (0.25 * smoke_likelihood)
        + (0.20 * burn_likelihood)
        + (0.15 * hotspot)
        - (0.35 * cloud_likelihood),
        -0.35,
        0.35,
    )
    final_confidence = _clamp(0.46 + confidence_delta)

    if _proxy_or_fallback_source(runtime_truth_mode, imagery_origin, observation_source):
        reason_codes.append("proxy_or_fallback_source_capped")
        final_confidence = min(final_confidence, 0.25)
        if target_action == "downlink_now":
            target_action = "review"

    return {
        "runtime_truth_mode": runtime_truth_mode,
        "imagery_origin": imagery_origin,
        "scoring_basis": "multispectral_bands",
        "observation_source": observation_source,
        "use_case": WILDFIRE_USE_CASE_ID,
        "target_task": WILDFIRE_SMOKE_TARGET_TASK,
        "target_category": WILDFIRE_TARGET_CATEGORY,
        "date_range": _date_range_from_summaries(summaries),
        "accepted_frames": len(accepted),
        "smoke_likelihood": _round(smoke_likelihood),
        "cloud_likelihood": _round(cloud_likelihood),
        "burn_likelihood": _round(burn_likelihood),
        "hotspot_support": _round(hotspot),
        "confidence_delta": _round(confidence_delta),
        "final_confidence": _round(final_confidence),
        "target_action": target_action,
        "reason_codes": list(dict.fromkeys(reason_codes)),
        "burn_context": {
            "dnbr": _round(dnbr_raw),
            "ndmi_drop": _round(ndmi_drop_raw),
            "ndvi_drop": _round(ndvi_drop_raw),
        },
        "frame_summaries": summaries,
        "provenance": {
            "scoring_basis": "multispectral_bands",
            "required_bands": "B02,B03,B04,B08,B11,B12,SCL,CLD,CLP",
            "source_guard": "no_proxy_fire_confirmation",
        },
    }
