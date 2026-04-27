"""
Ground Validator Agent — autonomous ground station processing loop.

This agent reads anomaly flags from the Satellite Pruner via the agent bus,
runs the offline LFM analysis on each flagged cell, generates a timelapse
for the cell's bounding box, analyzes the temporal sequence to confirm the
deforestation signal, and posts validation results back to the satellite.
It also persists confirmations and timelapse videos to the gallery DB.

Pipeline (per flagged cell):
  SAT FLAG → spectral analysis → timelapse generation → temporal analysis →
  CONFIRM/REJECT → gallery entry with timelapse → bus notification

In production this would run on ground station hardware with unconstrained
internet access to pull high-res imagery. In demo mode it runs as an async
task inside FastAPI alongside the satellite agent.
"""

import asyncio
import logging
from core.agent_bus import post_message, pull_messages, upsert_pin
from core.grid import cell_to_boundary, cell_to_latlng
from core.mission import get_active_mission
from core.analyzer import analyze_alert, analyze_timelapse
from core.gallery import add_gallery_item
from core.link_state import is_link_connected

logger = logging.getLogger(__name__)

_GROUND_SENDER = "ground"
_SATELLITE_RECIPIENT = "satellite"

# Poll interval for new satellite messages (seconds)
_POLL_INTERVAL = 1.2


def _get_cell_bbox(cell_id: str, buffer_deg: float = 0.03) -> list[float]:
    """Return [W, S, E, N] bounding box around an cell."""
    boundary = cell_to_boundary(cell_id)
    lats = [p[0] for p in boundary]
    lngs = [p[1] for p in boundary]
    return [
        min(lngs) - buffer_deg,
        min(lats) - buffer_deg,
        max(lngs) + buffer_deg,
        max(lats) + buffer_deg,
    ]


def _severity_to_action(severity: str) -> str:
    if severity == "critical":
        return "ESCALATE — flagging for immediate tasking priority."
    if severity == "high":
        return "CONFIRM — adding to active deforestation watch list."
    if severity == "moderate":
        return "MONITOR — logging for next pass comparison."
    return "ARCHIVE — change below escalation threshold."


def _build_confirmation(cell_id: str, analysis: dict, flag_payload: dict, timelapse_analysis: str | None = None) -> dict:
    severity = analysis.get("severity", "low")
    action = _severity_to_action(severity)
    change_score = flag_payload.get("change_score", 0.0)
    confidence = flag_payload.get("confidence", 0.0)
    reason_codes = flag_payload.get("reason_codes", [])
    model = analysis.get("model", "offline_lfm_v1")

    base_note = (
        f"Ground validation complete on {cell_id}. "
        f"LFM ({model}) assessment: {severity.upper()}. "
        f"Change score {change_score:.3f} | confidence {confidence:.3f}. "
        f"{action}"
    )
    if timelapse_analysis:
        base_note += f" Timelapse: {timelapse_analysis}"

    return {
        "severity": severity,
        "action": action,
        "model": model,
        "change_score": change_score,
        "confidence": confidence,
        "reason_codes": reason_codes,
        "analysis_summary": analysis.get("summary", ""),
        "findings": analysis.get("findings", []),
        "timelapse_analysis": timelapse_analysis or "",
        "note": base_note,
    }


def _build_reject(cell_id: str, reason: str, flag_payload: dict | None = None) -> dict:
    flag_payload = flag_payload or {}
    return {
        "severity": "rejected",
        "action": "REJECT — below confirmation threshold.",
        "reason": reason,
        "change_score": float(flag_payload.get("change_score", 0.0)),
        "confidence": float(flag_payload.get("confidence", 0.0)),
        "reason_codes": list(flag_payload.get("reason_codes", [])),
        "observation_source": str(flag_payload.get("observation_source", "unknown")),
        "before_window": dict(flag_payload.get("before_window", {})) if flag_payload.get("before_window") else None,
        "after_window": dict(flag_payload.get("after_window", {})) if flag_payload.get("after_window") else None,
        "demo_forced_anomaly": bool(flag_payload.get("demo_forced_anomaly", False)),
        "note": (
            f"Ground review of {cell_id} complete. "
            f"Signal does not meet confirmation threshold. Reason: {reason}. "
            f"Cell returned to monitoring queue."
        ),
    }


def _generate_cell_timelapse(cell_id: str) -> tuple[str | None, str | None, str | None]:
    """
    Generate a timelapse WebM for the cell's bounding box and run temporal analysis.

    Returns (video_b64, analysis_text, source). Values can be None on failure.
    This is run in a thread pool since timelapse generation is I/O-heavy.
    """
    from core.config import REGION
    from core.timelapse import generate_timelapse_frames

    try:
        bbox = _get_cell_bbox(cell_id)
        result = generate_timelapse_frames(
            bbox=bbox,
            start_date=REGION.before_label,
            end_date=REGION.after_label,
            steps=12,
        )
        video_b64 = result.get("video_b64")
        timelapse_source = (
            (result.get("provenance") or {}).get("kind")
            if isinstance(result.get("provenance"), dict)
            else None
        ) or result.get("source") or result.get("provider")

        # Now run the temporal signal analysis over the same bbox
        analysis_text = analyze_timelapse(bbox)
        logger.info("[GND] Timelapse generated for %s: %d frames. Analysis: %s",
                    cell_id, result.get("frames_count", 0), analysis_text[:80])
        return video_b64, analysis_text, str(timelapse_source) if timelapse_source else None
    except Exception as exc:
        logger.warning("[GND] Timelapse generation failed for %s: %s", cell_id, exc)
        return None, None, None


async def run_ground_agent(stop_event: asyncio.Event | None = None) -> None:
    """
    Main ground agent loop.
    Polls the bus for satellite flags, runs LFM + timelapse analysis, posts results back.
    """
    logger.info("[GND] Ground Validator Agent booted.")

    post_message(
        sender=_GROUND_SENDER,
        recipient="broadcast",
        msg_type="status",
        payload={
            "status": "online",
            "note": (
                "Ground Station online. LFM offline analyzer + timelapse pipeline ready. "
                "Monitoring satellite bus for anomaly flags."
            ),
        },
    )

    loop = asyncio.get_running_loop()

    while True:
        if stop_event and stop_event.is_set():
            logger.info("[GND] Stop event received. Shutting down.")
            break

        mission = get_active_mission()
        if mission and mission.get("mission_mode") == "replay":
            await asyncio.sleep(_POLL_INTERVAL)
            continue

        # --- Link state check ---
        if not is_link_connected():
            # Downlink severed — satellite flags accumulate in queue, we skip processing
            from core.agent_bus import get_bus_stats
            stats = get_bus_stats()
            logger.debug("[GND] Downlink SEVERED — %d flags queued", stats["unread_messages"])
            await asyncio.sleep(_POLL_INTERVAL)
            continue

        flags = pull_messages(recipient=_GROUND_SENDER, limit=5)

        for msg in flags:
            if msg["msg_type"] != "flag":
                continue

            cell_id = msg.get("cell_id") or "unknown"
            flag_payload = msg["payload"]

            logger.info("[GND] ← SAT FLAG on %s (score=%.3f)", cell_id, flag_payload.get("change_score", 0))

            # Post immediate status: timelapse being generated
            post_message(
                sender=_GROUND_SENDER,
                recipient="broadcast",
                msg_type="status",
                cell_id=cell_id,
                payload={
                    "note": (
                        f"[GND] Flag received for {cell_id}. "
                        f"Generating timelapse to confirm temporal signal before escalation."
                    ),
                },
            )

            try:
                # ---- Step 1: Spectral analysis (fast, synchronous) ----
                analysis = analyze_alert(
                    change_score=float(flag_payload.get("change_score", 0)),
                    confidence=float(flag_payload.get("confidence", 0)),
                    reason_codes=list(flag_payload.get("reason_codes", [])),
                    before_window=dict(flag_payload.get("before_window", {})),
                    after_window=dict(flag_payload.get("after_window", {})),
                    observation_source=str(flag_payload.get("observation_source", "unknown")),
                    demo_forced_anomaly=bool(flag_payload.get("demo_forced_anomaly", False)),
                )

                severity = analysis.get("severity", "low")

                # ---- Step 2: Timelapse generation + temporal analysis ----
                # Only generate for confirmed-worthy alerts (moderate / high / critical)
                video_b64: str | None = None
                timelapse_analysis: str | None = None
                timelapse_source: str | None = None

                if severity in ("critical", "high", "moderate"):
                    # Run blocking timelapse generation in threadpool so we don't stall the event loop
                    video_b64, timelapse_analysis, timelapse_source = await loop.run_in_executor(
                        None, _generate_cell_timelapse, cell_id
                    )

                    # Post timelapse-generated notification to bus with analysis
                    tl_note = timelapse_analysis or "Timelapse generation failed or unavailable."
                    post_message(
                        sender=_GROUND_SENDER,
                        recipient="broadcast",
                        msg_type="status",
                        cell_id=cell_id,
                        payload={
                            "note": (
                                f"[GND] Timelapse analysis complete for {cell_id}. "
                                f"{tl_note}"
                            ),
                            "timelapse_analysis": tl_note,
                            "has_timelapse": video_b64 is not None,
                            "timelapse_source": timelapse_source,
                        },
                    )

                # ---- Step 3: Confirm or reject ----
                if severity in ("critical", "high", "moderate"):
                    confirmation = _build_confirmation(cell_id, analysis, flag_payload, timelapse_analysis)
                    post_message(
                        sender=_GROUND_SENDER,
                        recipient=_SATELLITE_RECIPIENT,
                        msg_type="confirmation",
                        cell_id=cell_id,
                        payload=confirmation,
                    )
                    # Upgrade the satellite pin to a ground-confirmed pin
                    try:
                        lat, lng = cell_to_latlng(cell_id)
                        upsert_pin(
                            pin_type="ground",
                            cell_id=cell_id,
                            lat=lat,
                            lng=lng,
                            label=f"GND ● {cell_id[:8]}",
                            note=f"Ground confirmed {severity.upper()}. {confirmation['action']}",
                            severity=severity,
                        )
                        # Add to gallery — including timelapse video if we have it
                        mission_id = flag_payload.get("mission_id")
                        add_gallery_item(
                            cell_id=cell_id,
                            lat=lat,
                            lng=lng,
                            severity=severity,
                            change_score=float(flag_payload.get("change_score", 0)),
                            mission_id=int(mission_id) if mission_id else None,
                            fetch_thumb=True,
                            timelapse_b64=video_b64,
                            timelapse_analysis=timelapse_analysis,
                            timelapse_source=timelapse_source,
                        )
                    except Exception as gallery_exc:
                        logger.warning("[GND] Gallery/pin update failed for %s: %s", cell_id, gallery_exc)
                    logger.info("[GND] → SAT CONFIRM %s | %s | timelapse=%s",
                                cell_id, severity.upper(), "yes" if video_b64 else "no")
                else:
                    reject = _build_reject(cell_id, "composite score too low for escalation", flag_payload)
                    post_message(
                        sender=_GROUND_SENDER,
                        recipient=_SATELLITE_RECIPIENT,
                        msg_type="reject",
                        cell_id=cell_id,
                        payload=reject,
                    )
                    logger.info("[GND] → SAT REJECT %s", cell_id)

            except Exception as exc:
                logger.warning("[GND] Analysis error on %s: %s", cell_id, exc)
                post_message(
                    sender=_GROUND_SENDER,
                    recipient=_SATELLITE_RECIPIENT,
                    msg_type="error",
                    cell_id=cell_id,
                    payload={
                        "error": str(exc),
                        "note": f"Ground analysis failed for {cell_id}. Retrying next pass.",
                    },
                )

        await asyncio.sleep(_POLL_INTERVAL)
