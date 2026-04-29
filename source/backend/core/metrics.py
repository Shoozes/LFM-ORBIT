import json
import os
from typing import Any

from core.config import (
    REGION,
    imagery_origin_for_source,
    runtime_truth_mode_for_source,
    scoring_basis_for_source,
)
from core.contracts import MetricsFlaggedExample, MetricsSummary
from core.utils import utc_timestamp

DEFAULT_METRICS_PATH = os.path.join(
    os.path.dirname(__file__),
    "../../../runtime-data/demo_metrics_summary.json",
)


def get_metrics_path() -> str:
    return os.getenv("CANOPY_SENTINEL_METRICS_PATH", DEFAULT_METRICS_PATH)


def _default_metrics_state() -> MetricsSummary:
    return {
        "region_id": REGION.region_id,
        "demo_mode_enabled": False,
        "demo_mode_loop_scan": bool(getattr(REGION, "demo_mode_loop_scan", True)),
        "runtime_truth_mode": runtime_truth_mode_for_source(REGION.observation_mode),
        "imagery_origin": imagery_origin_for_source(REGION.observation_mode),
        "scoring_basis": scoring_basis_for_source(REGION.observation_mode),
        "total_cycles_completed": 0,
        "total_cells_scanned": 0,
        "total_alerts_emitted": 0,
        "total_payload_bytes": 0,
        "total_bandwidth_saved_mb": 0.0,
        "latest_discard_ratio": 0.0,
        "latest_cycle_index": 0,
        "latest_cycle_started_at": "",
        "latest_cycle_completed_at": "",
        "pct_scenes_rejected": 0.0,
        "pct_low_valid_coverage": 0.0,
        "average_inference_latency_ms": 0.0,
        "peak_memory_mb": 0.0,
        "runtime_failures_by_stage": {},
        "runtime_rejections_by_reason": {},
        "flagged_examples": [],
    }


def _ensure_parent_dir():
    os.makedirs(os.path.dirname(get_metrics_path()), exist_ok=True)


def _coerce_state(raw: dict[str, Any]) -> MetricsSummary:
    state = _default_metrics_state()
    state.update(
        {
            "region_id": str(raw.get("region_id", state["region_id"])),
            "demo_mode_enabled": bool(raw.get("demo_mode_enabled", state["demo_mode_enabled"])),
            "demo_mode_loop_scan": bool(raw.get("demo_mode_loop_scan", state["demo_mode_loop_scan"])),
            "runtime_truth_mode": str(raw.get("runtime_truth_mode", state["runtime_truth_mode"])),
            "imagery_origin": str(raw.get("imagery_origin", state["imagery_origin"])),
            "scoring_basis": str(raw.get("scoring_basis", state["scoring_basis"])),
            "total_cycles_completed": int(raw.get("total_cycles_completed", state["total_cycles_completed"])),
            "total_cells_scanned": int(raw.get("total_cells_scanned", state["total_cells_scanned"])),
            "total_alerts_emitted": int(raw.get("total_alerts_emitted", state["total_alerts_emitted"])),
            "total_payload_bytes": int(raw.get("total_payload_bytes", state["total_payload_bytes"])),
            "total_bandwidth_saved_mb": round(
                float(raw.get("total_bandwidth_saved_mb", state["total_bandwidth_saved_mb"])),
                4,
            ),
            "latest_discard_ratio": round(
                float(raw.get("latest_discard_ratio", state["latest_discard_ratio"])),
                4,
            ),
            "latest_cycle_index": int(raw.get("latest_cycle_index", state["latest_cycle_index"])),
            "latest_cycle_started_at": str(raw.get("latest_cycle_started_at", state["latest_cycle_started_at"])),
            "latest_cycle_completed_at": str(raw.get("latest_cycle_completed_at", state["latest_cycle_completed_at"])),
            "pct_scenes_rejected": round(float(raw.get("pct_scenes_rejected", state["pct_scenes_rejected"])), 4),
            "pct_low_valid_coverage": round(float(raw.get("pct_low_valid_coverage", state["pct_low_valid_coverage"])), 4),
            "average_inference_latency_ms": round(float(raw.get("average_inference_latency_ms", state["average_inference_latency_ms"])), 4),
            "peak_memory_mb": round(float(raw.get("peak_memory_mb", state["peak_memory_mb"])), 4),
            "runtime_failures_by_stage": dict(raw.get("runtime_failures_by_stage", state["runtime_failures_by_stage"])),
            "runtime_rejections_by_reason": dict(raw.get("runtime_rejections_by_reason", state["runtime_rejections_by_reason"])),
            "flagged_examples": list(raw.get("flagged_examples", state["flagged_examples"])),
        }
    )
    return state


def _read_state() -> MetricsSummary:
    path = get_metrics_path()

    if not os.path.exists(path):
        return _default_metrics_state()

    try:
        with open(path, "r", encoding="utf-8") as file:
            raw = json.load(file)
        if not isinstance(raw, dict):
            return _default_metrics_state()
        return _coerce_state(raw)
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return _default_metrics_state()


def _write_state(state: MetricsSummary):
    _ensure_parent_dir()
    with open(get_metrics_path(), "w", encoding="utf-8") as file:
        json.dump(state, file, indent=2, sort_keys=True)


def init_metrics(reset: bool = False):
    if reset:
        _write_state(_default_metrics_state())
        return

    if not os.path.exists(get_metrics_path()):
        _write_state(_default_metrics_state())


def read_metrics_summary() -> MetricsSummary:
    return _read_state()


def seed_metrics_summary(state: dict[str, Any]) -> MetricsSummary:
    coerced = _coerce_state(state)
    _write_state(coerced)
    return coerced


def record_cycle_start(cycle_index: int):
    state = _read_state()
    state["latest_cycle_index"] = cycle_index
    state["latest_cycle_started_at"] = utc_timestamp()
    _write_state(state)


def record_scan_result(
    *,
    cycle_index: int,
    is_anomaly: bool,
    payload_bytes: int,
    bandwidth_saved_mb: float,
    discard_ratio: float,
    flagged_example: MetricsFlaggedExample | None = None,
):
    state = _read_state()
    state["latest_cycle_index"] = cycle_index
    state["total_cells_scanned"] += 1
    state["total_bandwidth_saved_mb"] = round(
        state["total_bandwidth_saved_mb"] + bandwidth_saved_mb,
        4,
    )
    state["latest_discard_ratio"] = round(discard_ratio, 4)

    if is_anomaly:
        state["total_alerts_emitted"] += 1
        state["total_payload_bytes"] += payload_bytes

        if flagged_example is not None:
            state["flagged_examples"] = [flagged_example, *state["flagged_examples"][:4]]

    _write_state(state)


def record_cycle_complete(cycle_index: int, discard_ratio: float):
    state = _read_state()
    state["total_cycles_completed"] = max(state["total_cycles_completed"], cycle_index)
    state["latest_cycle_index"] = cycle_index
    state["latest_discard_ratio"] = round(discard_ratio, 4)
    state["latest_cycle_completed_at"] = utc_timestamp()
    _write_state(state)

def _increment_counter(target: dict[str, int], key: str) -> None:
    target[key] = int(target.get(key, 0)) + 1


def record_observability_telemetry(
    total_time_ms: float,
    peak_memory_mb: float,
    is_rejected: bool,
    failures: dict[str, str],
    stage_times: dict[str, float],
    rejection_reason: str = "",
):
    state = _read_state()

    # Update running averages
    current_count = state["total_cells_scanned"]
    if current_count == 0:
         current_count = 1

    old_avg = state["average_inference_latency_ms"]
    state["average_inference_latency_ms"] = round(((old_avg * (current_count - 1)) + total_time_ms) / current_count, 2)

    # Update peak memory ceiling
    if peak_memory_mb > state["peak_memory_mb"]:
        state["peak_memory_mb"] = round(peak_memory_mb, 2)

    # Update rejection tracking
    if is_rejected:
        # Pct scenes rejected roughly = rejections / scanned
        rejs = round(state["pct_scenes_rejected"] * (current_count - 1)) + 1
        state["pct_scenes_rejected"] = round(rejs / current_count, 4)
        reason = rejection_reason.strip() or "unspecified"
        _increment_counter(state["runtime_rejections_by_reason"], reason)

        low_valid_count = round(state["pct_low_valid_coverage"] * (current_count - 1))
        if "insufficient_valid_pixels" in reason or "low_valid_coverage" in reason:
            low_valid_count += 1
        state["pct_low_valid_coverage"] = round(low_valid_count / current_count, 4)
    else:
        rejs = round(state["pct_scenes_rejected"] * (current_count - 1))
        state["pct_scenes_rejected"] = round(rejs / current_count, 4)
        low_valid_count = round(state["pct_low_valid_coverage"] * (current_count - 1))
        state["pct_low_valid_coverage"] = round(low_valid_count / current_count, 4)

    # Update failures
    for stage, err in failures.items():
        _increment_counter(state["runtime_failures_by_stage"], stage)

    _write_state(state)
