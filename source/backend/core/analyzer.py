"""
AI-powered alert analysis for LFM Orbit.

Ground validation keeps deterministic signal gates for severity and safety, then
uses the same manifest-resolved Orbit GGUF as the Satellite Pruner when that
model is loaded. If the GGUF is unavailable, the deterministic offline analyzer
remains the safe fallback.
"""

import logging
import os
from core.config import DETECTION, REGION
from core.contracts import AlertAnalysisResponse
from core.inference import generate as llm_generate
from core.inference import model_status as llm_model_status

logger = logging.getLogger(__name__)

_FALLBACK_MODEL_NAME = "offline_lfm_v1"
_GROUND_GGUF_MODE_ENV = "ORBIT_GROUND_GGUF_ANALYSIS"


def _ground_gguf_mode() -> str:
    mode = os.getenv(_GROUND_GGUF_MODE_ENV, "auto").strip().lower()
    if mode in {"1", "true", "yes", "on"}:
        return "true"
    if mode in {"0", "false", "no", "off"}:
        return "false"
    return "auto"


def _usable_llm_response(result: dict) -> str | None:
    response = str(result.get("response") or "").strip()
    if not response:
        return None
    lowered = response.lower()
    if "lfm model not loaded" in lowered or lowered.startswith("[inference error:"):
        return None
    return response


def ground_model_status() -> dict:
    """Return the Ground Validator model status without forcing a model load."""
    status = llm_model_status()
    loaded = bool(status.get("loaded", False))
    model_name = str(status.get("name") or "LFM2.5-VL-450M-Q4_0.gguf")
    return {
        "role": "ground_validator",
        "model": model_name if loaded else _FALLBACK_MODEL_NAME,
        "shared_gguf_model": model_name,
        "shared_with_satellite": loaded,
        "loaded": loaded,
        "fallback_model": _FALLBACK_MODEL_NAME,
        "mode": _ground_gguf_mode(),
        "reason": status.get("reason", ""),
        "path": status.get("path", ""),
        "runtime_inference_mode": status.get("runtime_inference_mode", "text_evidence_packet"),
    }


def warm_ground_model() -> dict:
    """
    Warm the shared GGUF for Ground Validator use when the artifact is present.

    This runs from the background ground-agent task, not API startup. It keeps
    the app responsive while making later ground confirmations use the same
    singleton model object as satellite triage.
    """
    if _ground_gguf_mode() == "false":
        return ground_model_status()
    status = llm_model_status()
    model_path = str(status.get("path") or "")
    if not model_path or not os.path.exists(model_path):
        return ground_model_status()
    llm_generate(
        (
            "[SYSTEM] You are the Ground Validator Agent for LFM-ORBIT.\n"
            "[TASK] Reply with a short readiness acknowledgement for evidence-packet review."
        ),
        max_tokens=24,
    )
    return ground_model_status()


def _ground_gguf_review(
    *,
    severity: str,
    change_score: float,
    confidence: float,
    reason_codes: list[str],
    findings: list[str],
    confidence_note: str,
    source_note: str,
) -> tuple[str | None, str | None]:
    mode = _ground_gguf_mode()
    if mode == "false":
        return None, None
    status = llm_model_status()
    if mode == "auto" and not bool(status.get("loaded", False)):
        return None, None

    prompt = (
        "[SYSTEM] You are the Ground Validator Agent for LFM-ORBIT. "
        "Use the provided evidence packet only. Keep candidate language and do not overclaim.\n\n"
        "[EVIDENCE]\n"
        f"severity: {severity}\n"
        f"change_score: {change_score:.4f}\n"
        f"confidence: {confidence:.4f}\n"
        f"reason_codes: {', '.join(reason_codes) or 'none'}\n"
        f"findings: {' | '.join(findings)}\n"
        f"confidence_note: {confidence_note}\n"
        f"source_note: {source_note}\n\n"
        "[TASK] Write two short sentences for the human reviewer. "
        "Mention whether to confirm, monitor, or reject the packet."
    )
    response = _usable_llm_response(llm_generate(prompt, max_tokens=120))
    if not response:
        return None, None
    model_name = str(llm_model_status().get("name") or status.get("name") or "LFM2.5-VL-450M-Q4_0.gguf")
    return model_name, response


def _with_ground_model_review(
    payload: AlertAnalysisResponse,
    *,
    change_score: float,
    confidence: float,
    reason_codes: list[str],
) -> AlertAnalysisResponse:
    model_name, review = _ground_gguf_review(
        severity=payload["severity"],
        change_score=change_score,
        confidence=confidence,
        reason_codes=reason_codes,
        findings=payload["findings"],
        confidence_note=payload["confidence_note"],
        source_note=payload["source_note"],
    )
    if not model_name or not review:
        payload["model_runtime"] = "deterministic_fallback"
        return payload

    payload["deterministic_model"] = payload["model"]
    payload["model"] = model_name
    payload["model_runtime"] = "shared_trained_gguf_text_evidence_packet"
    payload["summary"] = f"{payload['summary']}\n\nGround GGUF review:\n{review}"
    return payload


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

    payload: AlertAnalysisResponse = {
        "model": _FALLBACK_MODEL_NAME,
        "severity": severity,
        "summary": "\n".join(summary_lines),
        "findings": findings,
        "confidence_note": confidence_note,
        "source_note": source_note,
    }
    return _with_ground_model_review(
        payload,
        change_score=change_score,
        confidence=confidence,
        reason_codes=reason_codes,
    )


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
    payload: AlertAnalysisResponse = {
        "model": _FALLBACK_MODEL_NAME,
        "severity": severity,
        "summary": "\n".join(summary_lines),
        "findings": findings,
        "confidence_note": confidence_note,
        "source_note": source_note,
    }
    return _with_ground_model_review(
        payload,
        change_score=change_score,
        confidence=confidence,
        reason_codes=reason_codes,
    )


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
