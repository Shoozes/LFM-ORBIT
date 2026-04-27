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
from core.grid import normalize_bbox
from core.temporal_use_cases import classify_temporal_use_case

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
                mission_mode TEXT NOT NULL DEFAULT 'live',
                replay_id    TEXT,
                summary      TEXT,
                use_case_id  TEXT,
                use_case_confidence REAL,
                use_case_decision TEXT,
                cells_scanned INTEGER DEFAULT 0,
                flags_found  INTEGER DEFAULT 0,
                created_at   TEXT NOT NULL,
                completed_at TEXT
            )
            """
        )
        existing_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(missions)").fetchall()
        }
        if "mission_mode" not in existing_cols:
            conn.execute("ALTER TABLE missions ADD COLUMN mission_mode TEXT NOT NULL DEFAULT 'live'")
        if "replay_id" not in existing_cols:
            conn.execute("ALTER TABLE missions ADD COLUMN replay_id TEXT")
        if "summary" not in existing_cols:
            conn.execute("ALTER TABLE missions ADD COLUMN summary TEXT")
        if "use_case_id" not in existing_cols:
            conn.execute("ALTER TABLE missions ADD COLUMN use_case_id TEXT")
        if "use_case_confidence" not in existing_cols:
            conn.execute("ALTER TABLE missions ADD COLUMN use_case_confidence REAL")
        if "use_case_decision" not in existing_cols:
            conn.execute("ALTER TABLE missions ADD COLUMN use_case_decision TEXT")
        # We don't delete here by default, we'll expose a reset function
        conn.commit()

def init_missions(reset: bool = False) -> None:
    _ensure_missions_table()
    if not reset:
        return
    with _connect() as conn:
        conn.execute("DELETE FROM missions")
        conn.commit()


def reset_missions() -> None:
    init_missions(reset=True)


def start_mission(
    task_text: str,
    bbox: list[float] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    *,
    mission_mode: str = "live",
    replay_id: str | None = None,
    summary: str | None = None,
    use_case_id: str | None = None,
) -> dict[str, Any]:
    """Create a new mission and set it as active. Deactivates any previous active mission."""
    task_text = task_text.strip()
    if not task_text:
        raise ValueError("task_text is required")
    bbox = normalize_bbox(bbox) if bbox is not None else None
    if mission_mode not in {"live", "replay"}:
        raise ValueError("mission_mode must be 'live' or 'replay'")
    use_case_decision = classify_temporal_use_case(
        {
            "task_text": task_text,
            "bbox": bbox,
            "start_date": start_date,
            "end_date": end_date,
        },
        requested_use_case_id=use_case_id,
    )

    _ensure_missions_table()
    with _connect() as conn:
        # Complete any running missions
        conn.execute(
            "UPDATE missions SET status='complete', completed_at=? WHERE status='active'",
            (_now(),),
        )
        cursor = conn.execute(
            """
            INSERT INTO missions (
                task_text,
                bbox,
                start_date,
                end_date,
                status,
                mission_mode,
                replay_id,
                summary,
                use_case_id,
                use_case_confidence,
                use_case_decision,
                created_at
            )
            VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_text,
                json.dumps(bbox) if bbox else None,
                start_date,
                end_date,
                mission_mode,
                replay_id,
                summary,
                use_case_decision["id"],
                float(use_case_decision["confidence"]),
                json.dumps(use_case_decision),
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
        except Exception as exc:
            logger.debug("[MISSION] Invalid bbox payload for mission %s: %s", d.get("id"), exc)
            d["bbox"] = None
    d["mission_mode"] = str(d.get("mission_mode") or "live")
    d["replay_id"] = str(d["replay_id"]) if d.get("replay_id") else None
    d["summary"] = str(d["summary"]) if d.get("summary") else None
    d["use_case_id"] = str(d["use_case_id"]) if d.get("use_case_id") else None
    d["use_case_confidence"] = (
        float(d["use_case_confidence"]) if d.get("use_case_confidence") is not None else None
    )
    if d.get("use_case_decision"):
        try:
            d["use_case_decision"] = json.loads(d["use_case_decision"])
        except Exception as exc:
            logger.debug("[MISSION] Invalid use-case payload for mission %s: %s", d.get("id"), exc)
            d["use_case_decision"] = None
    else:
        d["use_case_decision"] = None
    return d
