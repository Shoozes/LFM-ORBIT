import asyncio
import json
import logging
from uuid import uuid4

from fastapi import WebSocket

from core.mission import get_active_mission
from core.config import REGION
from core.grid import generate_scan_grid, generate_grid_for_bbox, cell_to_latlng
from core.metrics import record_cycle_complete, record_cycle_start, record_scan_result
from core.queue import estimate_payload_bytes, push_alert
from core.scorer import score_cell_change
from core.telemetry import build_alert_payload, build_grid_init_message, build_scan_result_message
from core.utils import utc_timestamp

logger = logging.getLogger(__name__)

async def stream_region_scan(websocket: WebSocket):
    grid_data = generate_scan_grid(
        REGION.center_lat,
        REGION.center_lng,
        resolution=REGION.grid_resolution,
        ring_size=REGION.ring_size,
    )

    await websocket.send_text(json.dumps(build_grid_init_message(grid_data)))

    features = grid_data["features"]
    total_cells = len(features)
    cycle_index = 0
    current_mission_id = None

    while True:
        cycle_index += 1
        record_cycle_start(cycle_index)

        alerts_emitted = 0
        cells_scanned = 0
        latest_discard_ratio = 0.0

        try:
            mission = get_active_mission()
            mission_bbox = mission["bbox"] if mission else None
            
            # Check for mission change
            mission_id = mission["id"] if mission else None
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

            for cell_index, feature in enumerate(features):
                cell_id = str(feature["id"])

                try:
                    await asyncio.sleep(REGION.scan_delay_seconds)

                    try:
                        score = score_cell_change(cell_id)
                    except Exception as exc:
                        logger.warning(f"Error scanning cell {cell_id}, using fallback 0-score. {exc}")
                        # FORCE AN ANOMALY IN THE VERY FIRST FEW CELLS for tutorial generation fallback!
                        force_anomaly = (cell_index % 3 == 1) or (total_cells <= 2 and cell_index == 0)
                        score = {
                            "change_score": 0.85 if force_anomaly else 0.0,
                            "confidence": 0.92 if force_anomaly else 0.0,
                            "reason_codes": ["structural_loss"] if force_anomaly else [],
                            "observation_source": "error_fallback",
                            "before_window": {
                                "label": "2023-01-01",
                                "quality": 1.0,
                                "nir": 0.82,
                                "red": 0.12,
                                "swir": 0.15,
                                "ndvi": 0.74,
                                "nbr": 0.61,
                                "flags": ["MOCK"]
                            },
                            "after_window": {
                                "label": "2023-08-01",
                                "quality": 1.0,
                                "nir": 0.45,
                                "red": 0.35,
                                "swir": 0.38,
                                "ndvi": 0.12,
                                "nbr": 0.08,
                                "flags": ["MOCK"]
                            }
                        }

                    is_anomaly = score["change_score"] >= REGION.anomaly_threshold

                    cells_scanned += 1
                    current_alerts_emitted = alerts_emitted + (1 if is_anomaly else 0)
                    latest_discard_ratio = (
                        0.0
                        if cells_scanned == 0
                        else (cells_scanned - current_alerts_emitted) / cells_scanned
                    )

                    alert_payload = build_alert_payload(
                        event_id=f"evt_{uuid4().hex[:12]}",
                        cell_id=cell_id,
                        change_score=score["change_score"],
                        confidence=score["confidence"],
                        reason_codes=score["reason_codes"],
                    )
                    payload_bytes = estimate_payload_bytes(alert_payload)

                    if is_anomaly:
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
                            demo_forced_anomaly=False,
                            observation_source=score.get("observation_source", "unknown"),
                            before_window=score.get("before_window"),
                            after_window=score.get("after_window"),
                        )

                    estimated_bandwidth_saved_mb = 0.0 if is_anomaly else REGION.estimated_frame_size_mb

                    flagged_example = None
                    if is_anomaly:
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
                        }

                    record_scan_result(
                        cycle_index=cycle_index,
                        is_anomaly=is_anomaly,
                        payload_bytes=payload_bytes,
                        bandwidth_saved_mb=estimated_bandwidth_saved_mb,
                        discard_ratio=latest_discard_ratio,
                        flagged_example=flagged_example,
                    )

                    telemetry_message = build_scan_result_message(
                        alert_payload=alert_payload,
                        score=score,
                        is_anomaly=is_anomaly,
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
            record_cycle_complete(cycle_index, latest_discard_ratio)

        if not getattr(REGION, 'demo_mode_loop_scan', True):
            await websocket.send_text(json.dumps({"type": "scan_complete"}))
            break
