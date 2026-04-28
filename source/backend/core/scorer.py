from core.config import DETECTION, REGION
from core.contracts import WindowObservation
from core.loader import load_temporal_observations
from core.grid import get_cell_neighbors
from typing import Any



from core.indices import compute_ndvi, compute_nbr, compute_evi2, compute_ndmi, compute_swir_nir_ratio


QUALITY_GATE_REASON_CODES = [
    "low_quality_window",
    "quality_gate_failed",
    "abstained_cloud_coverage",
]


def _window_is_cloud_degraded(window: dict) -> bool:
    flags = {str(flag).lower() for flag in window.get("flags", [])}
    return "cloud_degraded" in flags or "insufficient_valid_pixels" in flags


def _to_window_payload(window: dict) -> WindowObservation:
    bands = window["bands"]
    ndvi = compute_ndvi(bands["nir"], bands["red"])
    nbr = compute_nbr(bands["nir"], bands["swir"])
    evi2 = compute_evi2(bands["nir"], bands["red"])
    ndmi = compute_ndmi(bands["nir"], bands["swir"])
    soil_ratio = compute_swir_nir_ratio(bands["nir"], bands["swir"])

    return {
        "label": window["label"],
        "quality": round(window["quality"], 4),
        "nir": round(bands["nir"], 4),
        "red": round(bands["red"], 4),
        "swir": round(bands["swir"], 4),
        "ndvi": round(ndvi, 4),
        "nbr": round(nbr, 4),
        "evi2": round(evi2, 4),
        "ndmi": round(ndmi, 4),
        "soil_ratio": round(soil_ratio, 4),
        "flags": list(window["flags"]),
    }


def score_cell_change(cell_id: str, observer: Any = None) -> dict:
    if observer:
        with observer.Stage("Seasonal Baseline Loader"):
            observations = load_temporal_observations(cell_id)
    else:
        observations = load_temporal_observations(cell_id)

    before_window = _to_window_payload(observations["before"])
    after_window = _to_window_payload(observations["after"])

    ndvi_drop = max(0.0, before_window["ndvi"] - after_window["ndvi"])
    nbr_drop = max(0.0, before_window["nbr"] - after_window["nbr"])
    evi2_drop = max(0.0, before_window["evi2"] - after_window["evi2"])
    ndmi_drop = max(0.0, before_window["ndmi"] - after_window["ndmi"])

    # Soil ratio SPIKES when forest is cleared (SWIR overtakes NIR)
    soil_ratio_spike = max(0.0, after_window["soil_ratio"] - before_window["soil_ratio"])

    nir_drop_ratio = 0.0
    if before_window["nir"] > 0:
        nir_drop_ratio = max(0.0, (before_window["nir"] - after_window["nir"]) / before_window["nir"])

    quality_factor = min(before_window["quality"], after_window["quality"])

    # Evi2 and NDMI are included in raw_change_score calculation to enforce multi-index agreement weight
    # Soil ratio spike is added as positive evidence of cleared ground
    raw_change_score = min(
        1.0,
        (ndvi_drop * 0.25) + (evi2_drop * 0.2) + (nir_drop_ratio * 0.15) + (nbr_drop * 0.15) + (ndmi_drop * 0.15) + (soil_ratio_spike * 0.1),
    )

    reason_codes: list[str] = []
    quality_blocked = (
        quality_factor < DETECTION.min_quality_threshold
        or _window_is_cloud_degraded(before_window)
        or _window_is_cloud_degraded(after_window)
    )
    change_score = 0.0 if quality_blocked else raw_change_score

    if quality_blocked:
        reason_codes.extend(QUALITY_GATE_REASON_CODES)
    else:
        if ndvi_drop >= DETECTION.ndvi_drop_threshold:
            reason_codes.append("ndvi_drop")
        if evi2_drop >= DETECTION.evi2_drop_threshold:
            reason_codes.append("evi2_drop")
        if nir_drop_ratio >= DETECTION.nir_drop_ratio_threshold:
            reason_codes.append("nir_drop")
        if nbr_drop >= DETECTION.nbr_drop_threshold:
            reason_codes.append("nbr_drop")
        if ndmi_drop >= DETECTION.ndmi_drop_threshold:
            reason_codes.append("ndmi_drop")
        if soil_ratio_spike >= DETECTION.soil_ratio_spike_threshold:
            reason_codes.append("soil_exposure_spike")

        if "evi2_drop" in reason_codes and ("ndvi_drop" in reason_codes or "nbr_drop" in reason_codes):
            reason_codes.append("multi_index_consensus")
        if "disturbance_pattern" in after_window["flags"]:
            reason_codes.append("observation_pattern_match")
        if change_score >= REGION.anomaly_threshold:
            reason_codes.append("suspected_canopy_loss")
        if not reason_codes:
            reason_codes.append("stable_vegetation")

    confidence = DETECTION.confidence_base + (quality_factor * DETECTION.confidence_quality_multiplier)
    if change_score < DETECTION.low_change_threshold:
        confidence -= DETECTION.confidence_penalty_low_change
    if "low_quality_window" in reason_codes:
        confidence -= DETECTION.confidence_penalty_low_quality
    if quality_blocked:
        confidence = min(confidence, 0.25)
    if "suspected_canopy_loss" in reason_codes and "multi_index_consensus" not in reason_codes:
        confidence -= DETECTION.confidence_penalty_single_index

    # --- Context Discriminator ---
    # Trigger contextual analysis only if we have a suspected loss to save API calls
    if "suspected_canopy_loss" in reason_codes:
        if observer:
            with observer.Stage("Drought Context Discriminator"):
                neighbors = get_cell_neighbors(cell_id, radius=1)
                neighbor_scores = []
                for n_id in neighbors:
                    n_obs = load_temporal_observations(n_id)
                    n_before = _to_window_payload(n_obs["before"])
                    n_after = _to_window_payload(n_obs["after"])
                    n_ndvi_drop = max(0.0, n_before["ndvi"] - n_after["ndvi"])
                    n_evi2_drop = max(0.0, n_before["evi2"] - n_after["evi2"])
                    n_score = (n_ndvi_drop * 0.25) + (n_evi2_drop * 0.2)
                    neighbor_scores.append(n_score)
        else:
            neighbors = get_cell_neighbors(cell_id, radius=1)
            neighbor_scores = []
            for n_id in neighbors:
                n_obs = load_temporal_observations(n_id)
                n_before = _to_window_payload(n_obs["before"])
                n_after = _to_window_payload(n_obs["after"])
                n_ndvi_drop = max(0.0, n_before["ndvi"] - n_after["ndvi"])
                n_evi2_drop = max(0.0, n_before["evi2"] - n_after["evi2"])
                n_score = (n_ndvi_drop * 0.25) + (n_evi2_drop * 0.2)
                neighbor_scores.append(n_score)

        if neighbor_scores:
            avg_neighbor_score = sum(neighbor_scores) / len(neighbor_scores)
            # If the surrounding forest is also exhibiting high anomaly, it is likely structural drought
            if avg_neighbor_score > (REGION.anomaly_threshold * 0.7):
                reason_codes.append("regional_phenology_shift")
                if "suspected_canopy_loss" in reason_codes:
                    reason_codes.remove("suspected_canopy_loss")
                confidence -= 0.45  # Heavy penalty for regional drought signature

    if "observation_pattern_match" in reason_codes:
        confidence += DETECTION.confidence_bonus_pattern_match
    confidence = max(0.0, min(1.0, confidence))

    return {
        "observation_source": observations["source"],
        "before_window": before_window,
        "after_window": after_window,
        "change_score": round(change_score, 4),
        "raw_change_score": round(raw_change_score, 4),
        "confidence": round(confidence, 4),
        "reason_codes": reason_codes,
    }
