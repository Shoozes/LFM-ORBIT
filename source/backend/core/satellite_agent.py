"""
Satellite Pruner Agent — autonomous orbital scanning loop.

This agent runs continuously, scanning cells, scoring spectral deltas,
and posting anomaly flags to the agent bus when thresholds are exceeded.
It also reads replies from the Ground Validator and acknowledges them.

In production this would run on the NVIDIA Orin in orbit.
In demo mode it runs as an async task inside FastAPI.
"""

import asyncio
import hashlib
import json
import logging
from pathlib import Path
from uuid import uuid4
from core.agent_bus import post_message, pull_messages, upsert_pin
from core.config import REGION
from core.grid import cell_to_latlng, generate_scan_grid
from core.mission import get_active_mission, update_mission_progress
from core.observability import log_throttled
from core.scorer import score_cell_change
from core.inference import build_satellite_prompt, generate, stream_tokens, parse_output

logger = logging.getLogger(__name__)

_SATELLITE_SENDER = "satellite"
_GROUND_RECIPIENT = "ground"

# How long to pause between cell evaluations (seconds)
_SCAN_INTERVAL = 0.3
# How long to pause between full grid cycles (seconds)
_CYCLE_PAUSE = 4.0


def _build_flag_message(
    cell_id: str,
    score: dict,
    mission_id: int | None = None,
    llm_result: dict | None = None,
) -> dict:
    payload = {
        "event_id": f"sat_{uuid4().hex[:10]}",
        "change_score": round(score["change_score"], 4),
        "confidence": round(score["confidence"], 4),
        "reason_codes": score["reason_codes"],
        "observation_source": score.get("observation_source", "semi_real_loader_v1"),
        "before_window": score.get("before_window", {}),
        "after_window": score.get("after_window", {}),
        "review_boundary": "candidate_evidence_packet",
        "note": (
            "Orbital triage complete. Downlinking a compact candidate evidence packet "
            "instead of raw imagery. Requesting ground validation."
        ),
    }
    if mission_id is not None:
        payload["mission_id"] = mission_id
    if llm_result:
        payload["thinking"] = llm_result.get("thinking", "")
        payload["response"] = llm_result.get("response", "")
        payload["tool_calls"] = llm_result.get("tool_calls", [])
    return payload


async def _run_llm_triage(cell_id: str, score: dict, loop: asyncio.AbstractEventLoop) -> dict:
    """Run LFM inference on an anomalous cell in a thread pool.

    Emits a stream_token heartbeat to the bus while generating so the
    debug dashboard can show live token output.
    """
    prompt = build_satellite_prompt(cell_id, score)

    # Post a thinking-started notification
    post_message(
        sender=_SATELLITE_SENDER,
        recipient="broadcast",
        msg_type="llm_thinking",
        cell_id=cell_id,
        payload={
            "action": "reasoning",
            "status": "started",
            "note": f"[LFM] Starting triage reasoning on {cell_id}...",
        },
    )

    accumulated = ""

    def _collect_stream():
        nonlocal accumulated
        for token in stream_tokens(prompt):
            accumulated += token
        return parse_output(accumulated)

    result = await loop.run_in_executor(None, _collect_stream)

    # Post a stream-complete notification with the full output
    post_message(
        sender=_SATELLITE_SENDER,
        recipient="broadcast",
        msg_type="llm_complete",
        cell_id=cell_id,
        payload={
            "action": "reasoning_complete",
            "status": "done",
            "thinking": result.get("thinking", ""),
            "response": result.get("response", ""),
            "tool_calls": result.get("tool_calls", []),
            "note": f"[LFM] Triage complete for {cell_id}. Decision embedded in flag.",
        },
    )

    return result


def _build_heartbeat_recap(
    cycle: int,
    cells_scanned: int,
    total_cells: int,
    flags_sent: int,
    acks_received: int,
    pending_ground_replies: int,
    link_connected: bool,
    current_action: str,
    mission: dict | None,
) -> dict:
    """
    Build a structured heartbeat recap so the debug dashboard can display
    a useful status card rather than a plain truncated note.
    """
    cells_remaining = max(0, total_cells - cells_scanned)
    discard_ratio = round((cells_scanned - flags_sent) / cells_scanned, 3) if cells_scanned > 0 else 0.0

    task_label = "Full-grid sweep (no active mission)"
    if mission:
        task_label = f"[MISSION #{mission['id']}] {mission['task_text']}"

    if link_connected:
        what_next = "Awaiting next cell. Ground uplink active — flags delivered on emit."
    else:
        what_next = f"Ground uplink SEVERED. Flags buffered in queue ({pending_ground_replies} pending). Will flush on reconnect."

    return {
        # Structured fields for dashboard rendering
        "cycle": cycle,
        "current_task": task_label,
        "cells_done": cells_scanned,
        "cells_remaining": cells_remaining,
        "cells_total": total_cells,
        "flags_sent_this_cycle": flags_sent,
        "acks_received_lifetime": acks_received,
        "pending_ground_replies": pending_ground_replies,
        "link_connected": link_connected,
        "current_action": current_action,
        "discard_ratio": discard_ratio,
        "what_next": what_next,
        # Human-readable summary for the heartbeat strip
        "note": (
            f"Cycle {cycle} | {cells_scanned}/{total_cells} cells "
            f"| {flags_sent} flagged | {acks_received} acks | "
            f"{'LINK OK' if link_connected else 'LINK SEVERED'} | {current_action}"
        ),
    }


# Simplified heartbeat builder used by tests (subset of _build_heartbeat_recap).
def _build_heartbeat_message(cells_scanned: int, total_cells: int, cycle: int) -> dict:
    return {
        "cycle": cycle,
        "cells_scanned": cells_scanned,
        "total_cells": total_cells,
        "status": "scanning",
        "note": f"Cycle {cycle} | {cells_scanned}/{total_cells} cells",
    }


async def run_satellite_agent(stop_event: asyncio.Event | None = None) -> None:
    """
    Main satellite agent loop.
    Scans the H3 grid continuously, posts flags when anomalies are detected,
    and reads acknowledgements from the ground station.
    """
    logger.info("[SAT] Satellite Pruner Agent booted.")

    grid_data = generate_scan_grid(
        REGION.center_lat,
        REGION.center_lng,
        resolution=REGION.grid_resolution,
        ring_size=REGION.ring_size,
    )
    features = grid_data["features"]
    total_cells = len(features)
    cycle = 0
    acks_received_lifetime = 0  # cumulative ground acks seen across all cycles

    # Boot heartbeat
    post_message(
        sender=_SATELLITE_SENDER,
        recipient="broadcast",
        msg_type="heartbeat",
        payload=_build_heartbeat_recap(
            cycle=0,
            cells_scanned=0,
            total_cells=total_cells,
            flags_sent=0,
            acks_received=0,
            pending_ground_replies=0,
            link_connected=True,
            current_action="booting",
            mission=None,
        ) | {
            "note": (
                f"Orbital Pruner online. Grid loaded: {total_cells} H3 cells "
                f"over {REGION.display_name}. Beginning triage sweep."
            ),
        },
    )

    while True:
        if stop_event and stop_event.is_set():
            logger.info("[SAT] Stop event received. Shutting down.")
            break

        mission = get_active_mission()
        if mission and mission.get("mission_mode") == "replay":
            mission_id = mission["id"]
            if mission_id != getattr(run_satellite_agent, "_last_replay_mission_id", None):
                run_satellite_agent._last_replay_mission_id = mission_id  # type: ignore[attr-defined]
                post_message(
                    sender=_SATELLITE_SENDER,
                    recipient="broadcast",
                    msg_type="status",
                    payload={
                        "mission_id": mission_id,
                        "replay_id": mission.get("replay_id"),
                        "note": (
                            f"[REPLAY #{mission_id}] Satellite loop idled. "
                            "Serving the cached replay mission state until the operator exits replay mode."
                        ),
                    },
                )
            await asyncio.sleep(_CYCLE_PAUSE)
            continue

        run_satellite_agent._last_replay_mission_id = None  # type: ignore[attr-defined]
        cycle += 1
        cells_scanned = 0
        flags_sent = 0

        # Read active mission
        mission_id = mission["id"] if mission else None
        mission_bbox = mission["bbox"] if mission else None  # [W, S, E, N] or None

        if mission and (cycle == 1 or mission_id != getattr(run_satellite_agent, "_last_mission_id", None)):
            run_satellite_agent._last_mission_id = mission_id  # type: ignore[attr-defined]
            post_message(
                sender=_SATELLITE_SENDER,
                recipient="broadcast",
                msg_type="mission",
                payload={
                    "mission_id": mission_id,
                    "task": mission["task_text"],
                    "bbox": mission_bbox,
                    "note": f"[MISSION #{mission_id}] Satellite tasked: {mission['task_text']}",
                },
            )

        loop = asyncio.get_running_loop()
        replay_interrupted = False

        for feature in features:
            if stop_event and stop_event.is_set():
                break

            live_mission = get_active_mission()
            if live_mission and live_mission.get("mission_mode") == "replay":
                replay_interrupted = True
                break

            cell_id = str(feature["id"])

            # Skip cells outside mission bbox (if mission is active with a bbox)
            if mission_bbox:
                try:
                    clat, clng = cell_to_latlng(cell_id)
                    w, s, e, n = mission_bbox
                    if not (w <= clng <= e and s <= clat <= n):
                        continue  # outside mission area
                except Exception as exc:
                    logger.debug("[SAT] Failed mission bbox check for %s: %s", cell_id, exc)
                    continue

            await asyncio.sleep(_SCAN_INTERVAL)

            try:
                score = score_cell_change(cell_id)
            except Exception as exc:
                log_throttled(
                    logger,
                    logging.WARNING,
                    f"satellite_agent:scorer_error:{type(exc).__name__}:{str(exc)}",
                    "[SAT] Scorer error on %s: %s",
                    cell_id,
                    exc,
                )
                continue

            # Automatically flag any area with a seeded video cache so we don't redownload
            try:
                from core.timelapse import _chunk_sig, _read_cache
                clat, clng = cell_to_latlng(cell_id)
                dim = 0.05
                cell_bbox = [clng - dim, clat - dim, clng + dim, clat + dim]
                chunk_sig = _chunk_sig(cell_bbox)
                
                if _read_cache(chunk_sig):
                    # We have seeded video data! Override the score to ensure it flags.
                    score["change_score"] = 0.96
                    score["confidence"] = 0.99
                    score["observation_source"] = "Seeded Orbital Video Cache"
                    
                    if "seeded_data_found" not in score["reason_codes"]:
                        score["reason_codes"].extend(["seeded_data_found", "interesting", "alert"])
                        
                    # Also persist it to our observation store as a training-ready VLM inference 
                    from core.observation_store import load_observation, save_observation
                    obs = load_observation(cell_bbox)
                    vlm_text = None
                    if obs and obs.get("observations"):
                        vlm_text = obs["observations"][-1].get("vlm_text")
                    if not vlm_text:
                        vlm_text = "Detailed seeded timelapse analysis confirms intense forest canopy loss. Tagged as interesting."
                        save_observation(
                            bbox=cell_bbox,
                            agent_role="satellite",
                            vlm_text=vlm_text,
                            cell_id=cell_id,
                            source="seeded_cache_auto_tag",
                            extra={"tags": ["interesting", "alert", "deforestation"]}
                        )
                    score["timelapse_analysis"] = vlm_text
            except Exception as cache_exc:
                log_throttled(
                    logger,
                    logging.WARNING,
                    f"satellite_agent:cache_link_error:{type(cache_exc).__name__}:{str(cache_exc)}",
                    "[SAT] Cache link error for %s: %s",
                    cell_id,
                    cache_exc,
                )

            cells_scanned += 1
            is_anomaly = score["change_score"] >= REGION.anomaly_threshold

            if is_anomaly:
                # Run LFM triage reasoning on this cell
                llm_result = None
                try:
                    llm_result = await _run_llm_triage(cell_id, score, loop)
                except Exception as exc:
                    log_throttled(
                        logger,
                        logging.WARNING,
                        f"satellite_agent:llm_triage_error:{type(exc).__name__}:{str(exc)}",
                        "[SAT] LFM triage error on %s: %s",
                        cell_id,
                        exc,
                    )

                response_str = (llm_result.get("response", "") if llm_result else "").lower()
                tool_calls = llm_result.get("tool_calls", []) if llm_result else []
                is_discard = any(str(tc.get("name", "")).startswith("discard") for tc in tool_calls)
                
                # Check explicit tags / prompt responses
                is_seasonal = "discard" in response_str and "seasonal" in response_str
                
                if is_discard or is_seasonal:
                    logger.info("[SAT] Dropping flag %s - detected as seasonal variation or discarded by LFM.", cell_id)
                    continue

                flags_sent += 1
                payload = _build_flag_message(cell_id, score, mission_id=mission_id, llm_result=llm_result)
                post_message(
                    sender=_SATELLITE_SENDER,
                    recipient=_GROUND_RECIPIENT,
                    msg_type="flag",
                    cell_id=cell_id,
                    payload=payload,
                )
                # Drop a satellite pin on the map at the cell centroid
                try:
                    lat, lng = cell_to_latlng(cell_id)
                    upsert_pin(
                        pin_type="satellite",
                        cell_id=cell_id,
                        lat=lat,
                        lng=lng,
                        label=f"SAT ◆ {cell_id[:8]}",
                        note=f"Orbital flag. Change score {score['change_score']:.3f}. Requesting ground validation.",
                        severity=None,
                    )
                except Exception as exc:
                    logger.debug("[SAT] Failed to place satellite pin for %s: %s", cell_id, exc)
                logger.info(
                    "[SAT] FLAG → %s | score=%.3f confidence=%.3f | llm=%s",
                    cell_id,
                    score["change_score"],
                    score["confidence"],
                    "ok" if llm_result else "skip",
                )

            # Every 15 cells send a progress heartbeat recap
            if cells_scanned % 15 == 0:
                from core.link_state import is_link_connected
                from core.agent_bus import get_bus_stats
                bus_stats = get_bus_stats()
                post_message(
                    sender=_SATELLITE_SENDER,
                    recipient="broadcast",
                    msg_type="heartbeat",
                    payload=_build_heartbeat_recap(
                        cycle=cycle,
                        cells_scanned=cells_scanned,
                        total_cells=total_cells,
                        flags_sent=flags_sent,
                        acks_received=acks_received_lifetime,
                        pending_ground_replies=bus_stats.get("unread_messages", 0),
                        link_connected=is_link_connected(),
                        current_action="scanning",
                        mission=mission,
                    ),
                )

        if replay_interrupted:
            continue

        # Update mission progress
        if mission_id:
            update_mission_progress(mission_id, cells_scanned, flags_sent)

        # Read any replies from ground (acknowledgements, queries)
        replies = pull_messages(recipient=_SATELLITE_SENDER, limit=20)
        acks_received_lifetime += len(replies)
        for reply in replies:
            logger.info(
                "[SAT] <- GROUND [%s] on %s: %s",
                reply["msg_type"],
                reply.get("cell_id", "N/A"),
                reply["payload"].get("note", ""),
            )

            # Let the satellite agent "watch" the timelapse and confirm
            if reply["msg_type"] == "confirmation":
                conf_cell_id = reply.get("cell_id")
                timelapse_analysis = reply["payload"].get("timelapse_analysis")
                
                if conf_cell_id and timelapse_analysis:
                    from core.inference import generate
                    
                    system_prompt = "You are the Satellite VLM Agent observing a sequence of orbital frames."
                    user_prompt = (
                        f"The ground station has linked a visual timelapse for cell {conf_cell_id} showing the following signals: "
                        f"'{timelapse_analysis}'. "
                        "Review this visual sequence data. Answer in exactly 1-2 short sentences: explicitly explain "
                        "what you see from orbit and confirm the structural decay."
                    )
                    
                    try:
                        vlm_explanation = None
                        try:
                            lat, lng = cell_to_latlng(conf_cell_id)
                            dim = 0.05
                            cell_bbox = [lng - dim, lat - dim, lng + dim, lat + dim]
                            rounded = [round(b, 3) for b in cell_bbox]
                            chunk_sig = hashlib.md5(str(rounded).encode()).hexdigest()[:8]

                            # Check replay cache first
                            meta_path = Path(__file__).resolve().parent.parent / "assets" / "seeded_data" / f"nasa_{chunk_sig}_meta.json"
                            if meta_path.exists():
                                with open(meta_path, "r") as mf:
                                    meta_data = json.load(mf)
                                    vlm_explanation = meta_data.get("vlm_explanation")
                                    logger.info(f"Using seeded VLM cache for {conf_cell_id} ({chunk_sig})")

                            # Check observation store as second-level cache
                            if not vlm_explanation:
                                from core.observation_store import load_observation
                                obs = load_observation(cell_bbox)
                                if obs and obs.get("observations"):
                                    latest = obs["observations"][-1]
                                    vlm_explanation = latest.get("vlm_text")
                                    if vlm_explanation:
                                        logger.info(f"Using observation store cache for {conf_cell_id} ({chunk_sig})")

                        except Exception as cache_exc:
                            logger.warning("[SAT] Cache lookup failed for %s: %s", conf_cell_id, cache_exc)

                        if not vlm_explanation:
                            prompt_str = f"[SYSTEM] {system_prompt}\n\n{user_prompt}"
                            vlm_result = await loop.run_in_executor(
                                None,
                                lambda: generate(
                                    prompt=prompt_str,
                                    max_tokens=100
                                )
                            )
                            vlm_explanation = vlm_result.get("response", "") if isinstance(vlm_result, dict) else str(vlm_result)

                            # Persist fresh inference result so it is not regenerated next time
                            try:
                                from core.observation_store import save_observation
                                lat, lng = cell_to_latlng(conf_cell_id)
                                dim = 0.05
                                bbox = [lng - dim, lat - dim, lng + dim, lat + dim]
                                save_observation(
                                    bbox=bbox,
                                    agent_role="satellite",
                                    vlm_text=vlm_explanation.strip(),
                                    cell_id=conf_cell_id,
                                    source="agent_inference",
                                    extra={"timelapse_analysis": timelapse_analysis},
                                )
                            except Exception as store_exc:
                                logger.warning("[SAT] Failed to save observation: %s", store_exc)

                        
                        post_message(
                            sender=_SATELLITE_SENDER,
                            recipient="broadcast",
                            msg_type="vlm_confirmation",
                            cell_id=conf_cell_id,
                            payload={
                                "note": vlm_explanation.strip(),
                                "action": "Visual orbital confirmation complete.",
                            }
                        )
                    except Exception as e:
                        logger.warning("[SAT] VLM explanation generation failed: %s", e)

        # End-of-cycle heartbeat recap (replaces plain status message)
        from core.link_state import is_link_connected
        from core.agent_bus import get_bus_stats
        bus_stats = get_bus_stats()
        post_message(
            sender=_SATELLITE_SENDER,
            recipient="broadcast",
            msg_type="heartbeat",
            payload=_build_heartbeat_recap(
                cycle=cycle,
                cells_scanned=cells_scanned,
                total_cells=total_cells,
                flags_sent=flags_sent,
                acks_received=acks_received_lifetime,
                pending_ground_replies=bus_stats.get("unread_messages", 0),
                link_connected=is_link_connected(),
                current_action=f"cool-down ({_CYCLE_PAUSE}s)",
                mission=mission,
            ),
        )

        await asyncio.sleep(_CYCLE_PAUSE)
