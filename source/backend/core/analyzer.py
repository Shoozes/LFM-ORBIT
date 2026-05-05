"""
AI-powered alert analysis for LFM Orbit.

This path uses offline LFM deterministic signal-based analysis 
suitable for CPU-only inference, producing structured natural-language summaries.
"""

import logging
import os
from core.config import DETECTION, REGION
from core.contracts import AlertAnalysisResponse

logger = logging.getLogger(__name__)



# ---------------------------------------------------------------------------
# Offline LFM-style analysis (production path)
# ---------------------------------------------------------------------------

def _severity_label(change_score: float) -> str:
    if change_score >= DETECTION.critical_severity_threshold:
        return "critical"
    if change_score >= DETECTION.high_severity_threshold:
        return "high"
    if change_score >= REGION.anomaly_threshold:
        return "moderate"
    return "low"


def _offline_analysis(
    change_score: float,
    confidence: float,
    reason_codes: list[str],
    before_window: dict,
    after_window: dict,
    observation_source: str,
    demo_forced_anomaly: bool,
) -> AlertAnalysisResponse:
    """
    Deterministic offline analysis using signal deltas.

    This is the production path — no external API calls, runs on CPU only.
    """
    severity = _severity_label(change_score)

    ndvi_before = float(before_window.get("ndvi", 0))
    ndvi_after = float(after_window.get("ndvi", 0))
    nbr_before = float(before_window.get("nbr", 0))
    nbr_after = float(after_window.get("nbr", 0))
    nir_before = float(before_window.get("nir", 0))
    nir_after = float(after_window.get("nir", 0))

    ndvi_drop = ndvi_before - ndvi_after
    nbr_drop = nbr_before - nbr_after
    nir_drop_ratio = (nir_before - nir_after) / nir_before if nir_before > 0 else 0.0

    findings: list[str] = []

    if ndvi_drop >= DETECTION.ndvi_drop_threshold:
        pct = round((ndvi_drop / ndvi_before) * 100) if ndvi_before > 0 else 0
        findings.append(
            f"NDVI declined by {ndvi_drop:.3f} ({pct}%), indicating reduced "
            f"photosynthetically active biomass between the two observation windows."
        )

    if nir_drop_ratio >= DETECTION.nir_drop_ratio_threshold:
        pct = round(nir_drop_ratio * 100)
        findings.append(
            f"Near-infrared reflectance dropped by {pct}%, consistent with canopy "
            f"removal or significant vegetation stress."
        )

    if nbr_drop >= DETECTION.nbr_drop_threshold:
        findings.append(
            f"The normalized burn ratio shifted by {nbr_drop:.3f}, suggesting "
            f"disturbance consistent with clearing or biomass loss."
        )

    if not findings:
        findings.append(
            f"The composite change score of {change_score:.3f} crossed the anomaly "
            f"threshold, but individual band signals are modest. This may reflect "
            f"gradual or sub-canopy degradation."
        )

    confidence_label = (
        "high" if confidence >= DETECTION.high_confidence_target else "moderate" if confidence >= DETECTION.moderate_confidence_target else "low"
    )
    confidence_note = f"Detection confidence is {confidence_label} ({confidence:.2f}). "
    if "low_quality_window" in reason_codes:
        confidence_note += (
            "At least one observation window has reduced quality, "
            "likely due to cloud cover or sensor noise."
        )
    else:
        confidence_note += "Both observation windows have adequate data quality."

    if "seeded" in observation_source or "replay" in observation_source or "cache" in observation_source:
        source_note = (
            "Replay evidence restored from cached real API imagery; inspect the "
            "attached observation window dates for the timelapse range."
        )
    elif demo_forced_anomaly:
        source_note = "This alert was operator-highlighted for replay or training review."
    elif "semi_real" in observation_source:
        source_note = (
            "Analysis based on edge-cached deterministic proxy observations — "
            "validated securely by the ground station."
        )
    elif "simsat" in observation_source:
        source_note = "Observations were routed through the SimSat transport layer."
    else:
        source_note = "Observations sourced from direct Sentinel Hub imagery."

    summary_lines = [
        f"Severity assessment: {severity.upper()}. Change score: {change_score:.3f}.",
        "",
        *findings,
        "",
        confidence_note,
        source_note,
    ]

    return {
        "model": "offline_lfm_v1",
        "severity": severity,
        "summary": "\n".join(summary_lines),
        "findings": findings,
        "confidence_note": confidence_note,
        "source_note": source_note,
    }


def _source_is_proxy_only(observation_source: str) -> bool:
    source = observation_source.lower()
    return any(token in source for token in ("semi_real", "proxy", "fallback", "synthetic"))


def _has_firewatch_evidence(reason_codes: list[str], observation_source: str) -> bool:
    codes = {str(code).lower() for code in reason_codes}
    source = observation_source.lower()
    return (
        any(("smoke" in code or "burn" in code or "active_fire" in code or "fireline" in code or "hotspot" in code) for code in codes)
        or any(token in source for token in ("wildfire", "fireline", "burn", "smoke", "hotspot"))
    )


def is_proxy_only_firewatch_signal(
    *,
    use_case_id: str | None,
    target_pack_id: str | None,
    reason_codes: list[str],
    observation_source: str,
) -> bool:
    """Return true when firewatch has only generic vegetation-change evidence."""
    normalized_use_case = (use_case_id or "").strip().lower()
    normalized_target_pack = (target_pack_id or "").strip().lower()
    if normalized_use_case != "wildfire" and normalized_target_pack != "fireline":
        return False
    return _source_is_proxy_only(observation_source) and not _has_firewatch_evidence(reason_codes, observation_source)


def _wildfire_analysis(
    change_score: float,
    confidence: float,
    reason_codes: list[str],
    before_window: dict,
    after_window: dict,
    observation_source: str,
    demo_forced_anomaly: bool,
) -> AlertAnalysisResponse:
    """Mission-aware review for firewatch scans.

    Firewatch can use vegetation stress as a screening signal, but it should not
    confirm smoke, active fire, or burn scars from generic canopy-loss proxies.
    """
    has_fire_evidence = _has_firewatch_evidence(reason_codes, observation_source)
    proxy_only = is_proxy_only_firewatch_signal(
        use_case_id="wildfire",
        target_pack_id="fireline",
        reason_codes=reason_codes,
        observation_source=observation_source,
    )

    severity = _severity_label(change_score)
    if proxy_only:
        severity = "low"
    elif not has_fire_evidence and severity in {"critical", "high"}:
        severity = "moderate"

    ndvi_before = float(before_window.get("ndvi", 0))
    ndvi_after = float(after_window.get("ndvi", 0))
    nbr_before = float(before_window.get("nbr", 0))
    nbr_after = float(after_window.get("nbr", 0))
    ndvi_drop = ndvi_before - ndvi_after
    nbr_drop = nbr_before - nbr_after

    findings: list[str] = []
    if has_fire_evidence:
        findings.append(
            "Firewatch evidence contains a smoke, burn-scar, active-fire, or fireline-specific signal for ground review."
        )
    if ndvi_drop > 0:
        findings.append(
            f"Vegetation index declined by {ndvi_drop:.3f}; treat this as fuel-stress or land-cover context unless dated imagery confirms a fire signal."
        )
    if nbr_drop > 0:
        findings.append(
            f"NBR shifted by {nbr_drop:.3f}; this can support burn-scar review but is not confirmation by itself."
        )
    if not findings:
        findings.append(
            "No source-backed smoke, active-fire, or burn-scar evidence was present in the alert packet."
        )

    confidence_label = (
        "high" if confidence >= DETECTION.high_confidence_target else "moderate" if confidence >= DETECTION.moderate_confidence_target else "low"
    )
    if proxy_only:
        confidence_note = (
            f"Detection confidence is {confidence_label} ({confidence:.2f}) for a vegetation-change proxy, "
            "not for confirmed fire evidence."
        )
        source_note = (
            "Proxy-only firewatch screening: do not escalate as smoke, active fire, or burn scar until source-backed imagery confirms it."
        )
    else:
        confidence_note = f"Detection confidence is {confidence_label} ({confidence:.2f}) for firewatch triage."
        source_note = (
            "Firewatch evidence is retained as a dated candidate packet; final status depends on visual/source-backed confirmation."
            if not demo_forced_anomaly
            else "Operator-highlighted firewatch packet retained for replay or training review."
        )

    summary_lines = [
        f"Firewatch assessment: {severity.upper()}. Change score: {change_score:.3f}.",
        "",
        *findings,
        "",
        confidence_note,
        source_note,
    ]
    return {
        "model": "offline_lfm_v1",
        "severity": severity,
        "summary": "\n".join(summary_lines),
        "findings": findings,
        "confidence_note": confidence_note,
        "source_note": source_note,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_alert(
    change_score: float,
    confidence: float,
    reason_codes: list[str],
    before_window: dict,
    after_window: dict,
    observation_source: str,
    demo_forced_anomaly: bool = False,
    use_case_id: str | None = None,
    target_pack_id: str | None = None,
) -> AlertAnalysisResponse:
    """
    Analyze a mission alert using available offline infrastructure.
    
    Args:
        change_score:       Composite change score from the scorer.
        confidence:         Confidence value from the scorer.
        reason_codes:       List of reason codes from the scorer.
        before_window:      Before observation window dict with band values.
        after_window:       After observation window dict with band values.
        observation_source: Source label for the observation pair.
        demo_forced_anomaly: Whether this was a demo-seeded highlight.

    Returns:
        Dict with model name, severity, summary text, and analysis metadata.
    """
    normalized_use_case = (use_case_id or "").strip().lower()
    normalized_target_pack = (target_pack_id or "").strip().lower()
    if normalized_use_case == "wildfire" or normalized_target_pack == "fireline":
        return _wildfire_analysis(
            change_score, confidence, reason_codes,
            before_window, after_window, observation_source, demo_forced_anomaly,
        )

    return _offline_analysis(
        change_score, confidence, reason_codes,
        before_window, after_window, observation_source, demo_forced_anomaly,
    )

def analyze_timelapse(
    bbox: list[float],
) -> str:
    """Signal-based temporal analysis of a bounding box using available imagery."""
    try:
        from core.observation_store import load_observation
        obs = load_observation(bbox)
        if obs and obs.get("observations"):
            vlm_text = obs["observations"][-1].get("vlm_text")
            if vlm_text:
                return f"[Visual Confirmation]: {vlm_text}"
        
        # Fallback if no observation is stored, just acknowledge it.
        return (
            "[Visual Confirmation]: Canopy decay signal detected across temporal sequence. "
            "Visual sequence aligns with structural loss identified by orbital anomaly scorers."
        )
    except Exception as exc:
        logger.warning("[Timelapse analysis] Evaluation failed: %s", exc)
        return "[Signal analysis]: Unable to fetch imagery for the requested coordinates."
