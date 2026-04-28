"""Runtime state helpers for deterministic setup, teardown, and replay loading."""

from __future__ import annotations

from typing import Any

from core.agent_bus import _connect as _bus_connect, init_bus
from core.gallery import init_gallery
from core.link_state import set_link_state
from core.metrics import init_metrics, read_metrics_summary
from core.mission import init_missions
from core.observation_store import clear_observations
from core.queue import _connect as _queue_connect, init_db


def _count_rows(connection, table_name: str) -> int:
    row = connection.execute(f"SELECT COUNT(*) AS total FROM {table_name}").fetchone()
    return int(row["total"] or 0)


def snapshot_runtime_state() -> dict[str, int]:
    """Return the current counts across the mutable runtime stores."""
    init_db()
    init_bus()
    init_gallery()
    init_missions()
    init_metrics()

    with _queue_connect() as queue_conn:
        alerts = _count_rows(queue_conn, "alerts")
        candidates = _count_rows(queue_conn, "candidates")

    with _bus_connect() as bus_conn:
        agent_messages = _count_rows(bus_conn, "agent_messages")
        map_pins = _count_rows(bus_conn, "map_pins")
        gallery_items = _count_rows(bus_conn, "gallery_items")
        missions = _count_rows(bus_conn, "missions")

    metrics = read_metrics_summary()

    return {
        "alerts": alerts,
        "candidates": candidates,
        "agent_messages": agent_messages,
        "map_pins": map_pins,
        "gallery_items": gallery_items,
        "missions": missions,
        "metrics_total_cells_scanned": int(metrics["total_cells_scanned"]),
        "metrics_total_alerts_emitted": int(metrics["total_alerts_emitted"]),
        "metrics_total_cycles_completed": int(metrics["total_cycles_completed"]),
    }


def ensure_runtime_state() -> dict[str, int]:
    """Ensure the mutable runtime stores exist and return their current counts."""
    return snapshot_runtime_state()


def reset_runtime_state(*, clear_observation_store_files: bool = False) -> dict[str, Any]:
    """Reset mutable runtime stores used by live runs, demos, and replay fixtures."""
    before = snapshot_runtime_state()

    init_db(reset=True)
    init_bus(reset=True)
    init_gallery(reset=True)
    init_missions(reset=True)
    init_metrics(reset=True)
    set_link_state(True)

    removed_observations = 0
    if clear_observation_store_files:
        removed_observations = clear_observations()

    after = snapshot_runtime_state()

    return {
        "before": before,
        "after": after,
        "observation_store_files_removed": removed_observations,
    }
