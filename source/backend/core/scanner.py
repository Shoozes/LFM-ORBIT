import asyncio
import json
import logging
from uuid import uuid4

from fastapi import WebSocket

from core.mission import get_active_mission
from core.config import (
    REGION,
    imagery_origin_for_source,
    runtime_truth_mode_for_source,
    scoring_basis_for_source,
)
from core.grid import generate_scan_grid, generate_grid_for_bbox, cell_to_latlng
from core.metrics import record_cycle_complete, record_cycle_start, record_scan_result
from core.queue import estimate_payload_bytes, push_alert, upsert_candidate, remove_candidate
from core.scorer import score_cell_change
from core.telemetry import build_alert_payload, build_grid_init_message, build_scan_result_message
from core.utils import utc_timestamp
from core.observability import RuntimeObserver, log_throttled

logger = logging.getLogger(__name__)

QUALITY_REJECTION_REASONS = {"insufficient_valid_pixels", "scene_quality_rejected"}


def _rejection_reason_from_exception(exc: Exception) -> str:
    text = str(exc).strip().lower().replace(" ", "_")
    if "insufficient_valid_pixels" in text:
        return "insufficient_valid_pixels"
    if "scene_quality_rejected" in text:
        return "scene_quality_rejected"
    return "scan_failure"


def _is_quality_rejection(reason: str) -> bool:
    return reason in QUALITY_REJECTION_REASONS


def _zero_confidence_fallback_score(reason: str, *, observation_source: str, reason_codes: list[str]) -> dict:
    flags = [reason]
    empty_window = {
        "label": "unavailable",
        "quality": 0.0,
        "nir": 0.0,
        "red": 0.0,
        "swir": 0.0,
        "ndvi": 0.0,
        "nbr": 0.0,
        "evi2": 0.0,
        "ndmi": 0.0,
        "soil_ratio": 0.0,
        "flags": flags,
    }
    return {
        "change_score": 0.0,
        "raw_change_score": 0.0,
        "confidence": 0.0,
        "reason_codes": reason_codes,
        "observation_source": observation_source,
        "before_window": empty_window,
        "after_window": empty_window,
    }


def _quality_gate_fallback_score(reason: str) -> dict:
    return _zero_confidence_fallback_score(
        reason,
        observation_source="quality_gate_fallback",
        reason_codes=["low_quality_window", "quality_gate_failed", reason],
    )


def _score_unavailable_fallback_score(reason: str) -> dict:
    return _zero_confidence_fallback_score(
        reason,
        observation_source="provider_error_fallback",
        reason_codes=["score_unavailable", reason],
    )


async def stream_region_scan(websocket: WebSocket):
    mission = get_active_mission()
    mission_bbox = mission["bbox"] if mission else None
    grid_data = (
        generate_grid_for_bbox(mission_bbox)
        if mission_bbox
        else generate_scan_grid(
            REGION.center_lat,
            REGION.center_lng,
            resolution=REGION.grid_resolution,
            ring_size=REGION.ring_size,
        )
    )

    await websocket.send_text(json.dumps(build_grid_init_message(grid_data)))

    features = grid_data["features"]
    total_cells = len(features)
    cycle_index = 0
    current_mission_id = mission["id"] if mission else None
    replay_idle_mission_id = None

    while True:
        mission = get_active_mission()
        mission_bbox = mission["bbox"] if mission else None
        mission_id = mission["id"] if mission else None
        mission_mode = mission.get("mission_mode") if mission else None

        if mission_id != current_mission_id:
            current_mission_id = mission_id
            if mission_bbox:
                grid_data = generate_grid_for_bbox(mission_bbox)
            else:
                grid_data = generate_scan_grid(
                    REGION.center_lat,
                    REGION.center_lng,
                    resolution=REGION.grid_resolution,
                    ring_size=REGION.ring_size,
                )
            features = grid_data["features"]
            total_cells = len(features)
            await websocket.send_text(json.dumps(build_grid_init_message(grid_data)))

        if mission_mode == "replay":
            if mission_id != replay_idle_mission_id:
                await websocket.send_text(json.dumps({"type": "scan_complete"}))
                replay_idle_mission_id = mission_id
            await asyncio.sleep(1.0)
            continue

        replay_idle_mission_id = None
        cycle_index += 1
        record_cycle_start(cycle_index)

        alerts_emitted = 0
        cells_scanned = 0
        latest_discard_ratio = 0.0

        try:
            for feature in features:
                cell_id = str(feature["id"])

                observer = RuntimeObserver(run_id=f"run_{cycle_index}_{cell_id}", cell_id=cell_id)
                demo_forced_anomaly = False

                try:
                    await asyncio.sleep(REGION.scan_delay_seconds)

                    try:
                        with observer.Stage("Multi-Index Scoring"):
                            score = score_cell_change(cell_id, observer)
                    except Exception as exc:
                        rejection_reason = _rejection_reason_from_exception(exc)
                        observer.reject(rejection_reason)
                        log_throttled(
                            logger,
                            logging.WARNING,
                            f"scanner:score_failure:{type(exc).__name__}:{str(exc)}",
                            "Error scanning cell %s, using fallback 0-score. %s",
                            cell_id,
                            exc,
                        )
                        if _is_quality_rejection(rejection_reason):
                            score = _quality_gate_fallback_score(rejection_reason)
                        else:
                            score = _score_unavailable_fallback_score(rejection_reason)

                    is_anomaly = score["change_score"] >= REGION.anomaly_threshold
                    is_confirmed_anomaly = False

                    if is_anomaly:
                        if getattr(REGION, 'demo_mode_loop_scan', False):
                            # Bypass persistence in pure demo loops for quick visual feedback
                            is_confirmed_anomaly = True
                        else:
                            with observer.Stage("Persistence Check"):
                                consecutive = upsert_candidate(cell_id)
                                if consecutive >= 2:
                                    is_confirmed_anomaly = True
                                    remove_candidate(cell_id)
                    else:
                        remove_candidate(cell_id)

                    cells_scanned += 1
                    current_alerts_emitted = alerts_emitted + (1 if is_confirmed_anomaly else 0)
                    latest_discard_ratio = (
                        0.0
                        if cells_scanned == 0
                        else (cells_scanned - current_alerts_emitted) / cells_scanned
                    )

                    boundary_context = None
                    if is_confirmed_anomaly:
                        with observer.Stage("Concession Attribution"):
                            try:
                                from core.overlays.attribution import get_attribution_engine
                                from core.grid import cell_to_boundary

                                ring = cell_to_boundary(cell_id)
                                geojson_ring = [[lng, lat] for lat, lng in ring]
                                geojson_ring.append(geojson_ring[0])
                                poly = {"type": "Polygon", "coordinates": [geojson_ring]}

                                engine = get_attribution_engine()
                                matches = engine.evaluate_polygon(poly)
                                if matches:
                                    boundary_context = [
                                        {
                                            "layer_type": m.layer_type,
                                            "source_name": m.source_name,
                                            "feature_name": m.feature_name,
                                            "overlap_area_m2": m.overlap_area_m2,
                                            "overlap_ratio": m.overlap_ratio,
                                            "distance_to_boundary_m": m.distance_to_boundary_m
                                        }
                                        for m in matches
                                    ]
                            except Exception as e:
                                log_throttled(
                                    logger,
                                    logging.ERROR,
                                    f"scanner:attribution_failure:{type(e).__name__}:{str(e)}",
                                    "Attribution engine failed for %s: %s",
                                    cell_id,
                                    e,
                                    interval_seconds=60.0,
                                )

                    alert_payload = build_alert_payload(
                        event_id=f"evt_{uuid4().hex[:12]}",
                        cell_id=cell_id,
                        change_score=score["change_score"],
                        confidence=score["confidence"],
                        reason_codes=score["reason_codes"],
                        boundary_context=boundary_context,
                        demo_forced_anomaly=demo_forced_anomaly,
                    )
                    payload_bytes = estimate_payload_bytes(alert_payload)

                    if is_confirmed_anomaly:
                        alerts_emitted = current_alerts_emitted
                        push_alert(
                            event_id=alert_payload["event_id"],
                            region_id=alert_payload["region_id"],
                            cell_id=alert_payload["cell_id"],
                            change_score=alert_payload["change_score"],
                            confidence=alert_payload["confidence"],
                            priority=alert_payload["priority"],
                            reason_codes=alert_payload["reason_codes"],
                            payload_bytes=payload_bytes,
                            demo_forced_anomaly=demo_forced_anomaly,
                            observation_source=score.get("observation_source", "unknown"),
                            runtime_truth_mode=runtime_truth_mode_for_source(
                                score.get("observation_source", "unknown"),
                                demo_forced_anomaly=demo_forced_anomaly,
                            ),
                            imagery_origin=imagery_origin_for_source(score.get("observation_source", "unknown")),
                            scoring_basis=scoring_basis_for_source(score.get("observation_source", "unknown")),
                            before_window=score.get("before_window"),
                            after_window=score.get("after_window"),
                            boundary_context=boundary_context,
                        )

                    estimated_bandwidth_saved_mb = 0.0 if is_confirmed_anomaly else REGION.estimated_frame_size_mb

                    flagged_example = None
                    if is_confirmed_anomaly:
                        flagged_example = {
                            "event_id": alert_payload["event_id"],
                            "cell_id": alert_payload["cell_id"],
                            "cycle_index": cycle_index,
                            "change_score": alert_payload["change_score"],
                            "confidence": alert_payload["confidence"],
                            "priority": alert_payload["priority"],
                            "reason_codes": alert_payload["reason_codes"],
                            "payload_bytes": payload_bytes,
                            "timestamp": utc_timestamp(),
                            "demo_forced_anomaly": demo_forced_anomaly,
                            "runtime_truth_mode": runtime_truth_mode_for_source(
                                score.get("observation_source", "unknown"),
                                demo_forced_anomaly=demo_forced_anomaly,
                            ),
                            "imagery_origin": imagery_origin_for_source(score.get("observation_source", "unknown")),
                            "scoring_basis": scoring_basis_for_source(score.get("observation_source", "unknown")),
                        }
                        if boundary_context:
                            flagged_example["boundary_context"] = boundary_context

                    record_scan_result(
                        cycle_index=cycle_index,
                        is_anomaly=is_confirmed_anomaly,
                        payload_bytes=payload_bytes,
                        bandwidth_saved_mb=estimated_bandwidth_saved_mb,
                        discard_ratio=latest_discard_ratio,
                        flagged_example=flagged_example,
                    )

                    telemetry_message = build_scan_result_message(
                        alert_payload=alert_payload,
                        score=score,
                        is_anomaly=is_confirmed_anomaly,
                        payload_bytes=payload_bytes,
                        estimated_bandwidth_saved_mb=estimated_bandwidth_saved_mb,
                        cells_scanned=cells_scanned,
                        alerts_emitted=current_alerts_emitted,
                        discard_ratio=round(latest_discard_ratio, 4),
                        total_cells=total_cells,
                        cycle_index=cycle_index,
                    )

                    await websocket.send_text(json.dumps(telemetry_message))

                except Exception as e:
                    import traceback
                    if isinstance(e, asyncio.CancelledError):
                        raise
                    if "disconnect" in str(type(e)).lower() or "close" in str(type(e)).lower() or "connection" in str(type(e)).lower():
                        # Let disconnects cleanly bubble out to break the cycle loop
                        raise
                    logger.error(f"Error scanning cell {cell_id}: {e}\n{traceback.format_exc()}")
                    continue
                finally:
                    observer.finalize()

        finally:
            record_cycle_complete(cycle_index, latest_discard_ratio)

        if not getattr(REGION, 'demo_mode_loop_scan', True):
            await websocket.send_text(json.dumps({"type": "scan_complete"}))
            break
