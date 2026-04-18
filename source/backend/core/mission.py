"""
Mission — task-oriented scan orchestration stored in agent_bus.sqlite.

A mission is an operator-defined goal:
  - task_text: natural-language instruction ("Find deforestation in Amazonas N sector")
  - bbox: optional [west, south, east, north] bounding box to focus the scan
  - start/end dates: optional temporal window (used by timelapse)
  - status: idle | active | complete

The satellite agent reads the active mission each cycle and:
  1. Restricts scanning to cells inside bbox (if set)
  2. Announces the mission objective on the bus at cycle start
  3. Tags flag messages with mission_id
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from core.agent_bus import _connect, init_bus

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _ensure_missions_table() -> None:
    init_bus()
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS missions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                task_text    TEXT NOT NULL,
                bbox         TEXT,
                start_date   TEXT,
                end_date     TEXT,
                status       TEXT NOT NULL DEFAULT 'active',
                cells_scanned INTEGER DEFAULT 0,
                flags_found  INTEGER DEFAULT 0,
                created_at   TEXT NOT NULL,
                completed_at TEXT
            )
            """
        )
        # We don't delete here by default, we'll expose a reset function
        conn.commit()

def reset_missions() -> None:
    _ensure_missions_table()
    with _connect() as conn:
        conn.execute("DELETE FROM missions")
        conn.commit()


def start_mission(
    task_text: str,
    bbox: list[float] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Create a new mission and set it as active. Deactivates any previous active mission."""
    _ensure_missions_table()
    with _connect() as conn:
        # Complete any running missions
        conn.execute(
            "UPDATE missions SET status='complete', completed_at=? WHERE status='active'",
            (_now(),),
        )
        cursor = conn.execute(
            """
            INSERT INTO missions (task_text, bbox, start_date, end_date, status, created_at)
            VALUES (?, ?, ?, ?, 'active', ?)
            """,
            (
                task_text,
                json.dumps(bbox) if bbox else None,
                start_date,
                end_date,
                _now(),
            ),
        )
        mission_id = cursor.lastrowid
        conn.commit()

    mission = get_mission(mission_id)
    logger.info("[MISSION] Started #%d: %s", mission_id, task_text[:60])
    return mission  # type: ignore[return-value]


def stop_mission() -> None:
    """Deactivate all active missions."""
    _ensure_missions_table()
    with _connect() as conn:
        conn.execute(
            "UPDATE missions SET status='complete', completed_at=? WHERE status='active'",
            (_now(),),
        )
        conn.commit()


def get_active_mission() -> dict[str, Any] | None:
    """Return the currently active mission, or None."""
    _ensure_missions_table()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM missions WHERE status='active' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def get_mission(mission_id: int) -> dict[str, Any] | None:
    _ensure_missions_table()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM missions WHERE id=?", (mission_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def update_mission_progress(mission_id: int, cells_scanned: int, flags_found: int) -> None:
    _ensure_missions_table()
    with _connect() as conn:
        conn.execute(
            "UPDATE missions SET cells_scanned=?, flags_found=? WHERE id=?",
            (cells_scanned, flags_found, mission_id),
        )
        conn.commit()


def list_missions(limit: int = 20) -> list[dict[str, Any]]:
    _ensure_missions_table()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM missions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row) -> dict[str, Any]:
    d = dict(row)
    if d.get("bbox"):
        try:
            d["bbox"] = json.loads(d["bbox"])
        except Exception:
            d["bbox"] = None
    return d
