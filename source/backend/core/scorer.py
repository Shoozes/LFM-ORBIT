from core.contracts import WindowObservation
from core.loader import load_temporal_observations


def _compute_ndvi(nir: float, red: float) -> float:
    denominator = nir + red
    if denominator <= 0:
        return 0.0
    return (nir - red) / denominator


def _compute_nbr(nir: float, swir: float) -> float:
    denominator = nir + swir
    if denominator <= 0:
        return 0.0
    return (nir - swir) / denominator


def _to_window_payload(window: dict) -> WindowObservation:
    bands = window["bands"]
    ndvi = _compute_ndvi(bands["nir"], bands["red"])
    nbr = _compute_nbr(bands["nir"], bands["swir"])

    return {
        "label": window["label"],
        "quality": round(window["quality"], 4),
        "nir": round(bands["nir"], 4),
        "red": round(bands["red"], 4),
        "swir": round(bands["swir"], 4),
        "ndvi": round(ndvi, 4),
        "nbr": round(nbr, 4),
        "flags": list(window["flags"]),
    }


def score_cell_change(cell_id: str) -> dict:
    observations = load_temporal_observations(cell_id)

    before_window = _to_window_payload(observations["before"])
    after_window = _to_window_payload(observations["after"])

    ndvi_drop = max(0.0, before_window["ndvi"] - after_window["ndvi"])
    nbr_drop = max(0.0, before_window["nbr"] - after_window["nbr"])

    nir_drop_ratio = 0.0
    if before_window["nir"] > 0:
        nir_drop_ratio = max(0.0, (before_window["nir"] - after_window["nir"]) / before_window["nir"])

    quality_factor = min(before_window["quality"], after_window["quality"])
    change_score = min(
        1.0,
        (ndvi_drop * 0.5) + (nir_drop_ratio * 0.25) + (nbr_drop * 0.25),
    )

    reason_codes: list[str] = []
    if ndvi_drop >= 0.18:
        reason_codes.append("ndvi_drop")
    if nir_drop_ratio >= 0.25:
        reason_codes.append("nir_drop")
    if nbr_drop >= 0.20:
        reason_codes.append("nbr_drop")
    if "disturbance_pattern" in after_window["flags"]:
        reason_codes.append("observation_pattern_match")
    if quality_factor < 0.65:
        reason_codes.append("low_quality_window")
    if change_score >= 0.32:
        reason_codes.append("suspected_canopy_loss")
    if not reason_codes:
        reason_codes.append("stable_vegetation")

    confidence = 0.58 + (quality_factor * 0.32)
    if change_score < 0.12:
        confidence -= 0.08
    if "low_quality_window" in reason_codes:
        confidence -= 0.12
    if "observation_pattern_match" in reason_codes:
        confidence += 0.06
    confidence = max(0.0, min(1.0, confidence))

    return {
        "observation_source": observations["source"],
        "before_window": before_window,
        "after_window": after_window,
        "change_score": round(change_score, 4),
        "confidence": round(confidence, 4),
        "reason_codes": reason_codes,
    }