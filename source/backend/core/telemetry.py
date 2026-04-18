from core.config import REGION
from core.contracts import AlertRecord, GridInitMessage, HealthResponse, ScanResultMessage


def get_priority(change_score: float) -> str:
    if change_score >= 0.60:
        return "critical"
    if change_score >= 0.45:
        return "high"
    if change_score >= REGION.anomaly_threshold:
        return "medium"
    return "low"


def build_region_info() -> dict:
    return {
        "region_id": REGION.region_id,
        "display_name": REGION.display_name,
        "grid_resolution": REGION.grid_resolution,
        "ring_size": REGION.ring_size,
        "bbox": list(REGION.bbox),
        "center_lat": REGION.center_lat,
        "center_lng": REGION.center_lng,
        "map_zoom": REGION.map_zoom,
    }


def build_grid_init_message(grid_data: dict) -> GridInitMessage:
    return {
        "type": "grid_init",
        "data": grid_data,
        "region": build_region_info(),
    }


def build_health_payload(counts: dict[str, int]) -> HealthResponse:
    return {
        "status": "ok",
        "region_id": REGION.region_id,
        "display_name": REGION.display_name,
        "bbox": list(REGION.bbox),
        "grid_resolution": REGION.grid_resolution,
        "ring_size": REGION.ring_size,
        "anomaly_threshold": REGION.anomaly_threshold,
        "observation_mode": REGION.observation_mode,
        "before_label": REGION.before_label,
        "after_label": REGION.after_label,
        "total_alerts": counts["total_alerts"],
        "total_payload_bytes": counts["total_payload_bytes"],
    }


def build_alert_payload(
    event_id: str,
    cell_id: str,
    change_score: float,
    confidence: float,
    reason_codes: list[str],
) -> AlertRecord:
    return {
        "event_id": event_id,
        "region_id": REGION.region_id,
        "cell_id": cell_id,
        "change_score": change_score,
        "confidence": confidence,
        "priority": get_priority(change_score),
        "reason_codes": reason_codes,
        "payload_bytes": 0,
    }


def build_scan_result_message(
    *,
    alert_payload: AlertRecord,
    score: dict,
    is_anomaly: bool,
    payload_bytes: int,
    estimated_bandwidth_saved_mb: float,
    cells_scanned: int,
    alerts_emitted: int,
    discard_ratio: float,
    total_cells: int,
    cycle_index: int,
) -> ScanResultMessage:
    return {
        "type": "scan_result",
        "event_id": alert_payload["event_id"],
        "region_id": alert_payload["region_id"],
        "cell_id": alert_payload["cell_id"],
        "is_anomaly": is_anomaly,
        "change_score": alert_payload["change_score"],
        "confidence": alert_payload["confidence"],
        "priority": alert_payload["priority"],
        "reason_codes": alert_payload["reason_codes"],
        "payload_bytes": payload_bytes,
        "estimated_bandwidth_saved_mb": estimated_bandwidth_saved_mb,
        "observation_source": score["observation_source"],
        "before_window": score["before_window"],
        "after_window": score["after_window"],
        "heartbeat": {
            "last_cell": alert_payload["cell_id"],
            "cells_scanned": cells_scanned,
            "alerts_emitted": alerts_emitted,
            "discard_ratio": discard_ratio,
            "total_cells": total_cells,
            "cycle_index": cycle_index,
        },
        "cycle_index": cycle_index,
    }