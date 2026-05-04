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
from core.object_targets import get_target_pack, merge_custom_targets, normalize_object_targets
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
                target_pack_id TEXT,
                object_targets TEXT,
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
        if "target_pack_id" not in existing_cols:
            conn.execute("ALTER TABLE missions ADD COLUMN target_pack_id TEXT")
        if "object_targets" not in existing_cols:
            conn.execute("ALTER TABLE missions ADD COLUMN object_targets TEXT")
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
    target_pack_id: str | None = None,
    object_targets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a new mission and set it as active. Deactivates any previous active mission."""
    task_text = task_text.strip()
    if not task_text:
        raise ValueError("task_text is required")
    bbox = normalize_bbox(bbox) if bbox is not None else None
    if mission_mode not in {"live", "replay"}:
        raise ValueError("mission_mode must be 'live' or 'replay'")
    normalized_pack_id = target_pack_id.strip().lower() if target_pack_id else None
    pack_targets: list[dict[str, Any]] = []
    if normalized_pack_id:
        pack = get_target_pack(normalized_pack_id)
        if pack is None:
            raise ValueError(f"Unknown target_pack_id: {normalized_pack_id}")
        normalized_pack_id = pack["id"]
        pack_targets = list(pack["targets"])
    normalized_targets: list[dict[str, Any]] = []
    if object_targets:
        normalized_targets = normalize_object_targets(object_targets)
    elif pack_targets:
        normalized_targets = pack_targets
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
                target_pack_id,
                object_targets,
                use_case_confidence,
                use_case_decision,
                created_at
            )
            VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                normalized_pack_id,
                json.dumps(normalized_targets) if normalized_targets else None,
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


def _resolve_mission(mission_id: int | None) -> dict[str, Any]:
    mission = get_mission(mission_id) if mission_id is not None else get_active_mission()
    if mission is None:
        raise LookupError("Mission not found")
    return mission


def get_mission_target_state(mission_id: int | None = None) -> dict[str, Any]:
    mission = _resolve_mission(mission_id)
    return {
        "mission_id": mission["id"],
        "target_pack_id": mission.get("target_pack_id"),
        "object_targets": mission.get("object_targets") or [],
        "mission": mission,
    }


def set_mission_target_pack(mission_id: int | None, target_pack_id: str) -> dict[str, Any]:
    mission = _resolve_mission(mission_id)
    pack = get_target_pack(target_pack_id)
    if pack is None:
        raise ValueError(f"Unknown target_pack_id: {target_pack_id}")
    return _write_mission_targets(
        int(mission["id"]),
        target_pack_id=pack["id"],
        object_targets=pack["targets"],
    )


def add_mission_targets(
    mission_id: int | None,
    targets: list[dict[str, Any] | str],
) -> dict[str, Any]:
    mission = _resolve_mission(mission_id)
    existing = mission.get("object_targets") or []
    normalized = merge_custom_targets(existing, targets)
    return _write_mission_targets(
        int(mission["id"]),
        target_pack_id=mission.get("target_pack_id"),
        object_targets=normalized,
    )


def remove_mission_targets(mission_id: int | None, labels: list[str]) -> dict[str, Any]:
    mission = _resolve_mission(mission_id)
    remove_labels = {" ".join(str(label).strip().lower().split()) for label in labels if str(label).strip()}
    if not remove_labels:
        raise ValueError("At least one target label is required")
    existing = mission.get("object_targets") or []
    remaining = [
        target
        for target in normalize_object_targets(existing)
        if target["label"] not in remove_labels
    ]
    return _write_mission_targets(
        int(mission["id"]),
        target_pack_id=mission.get("target_pack_id"),
        object_targets=remaining,
    )


def clear_mission_targets(mission_id: int | None) -> dict[str, Any]:
    mission = _resolve_mission(mission_id)
    return _write_mission_targets(int(mission["id"]), target_pack_id=None, object_targets=[])


def _write_mission_targets(
    mission_id: int,
    *,
    target_pack_id: str | None,
    object_targets: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized_targets = normalize_object_targets(object_targets) if object_targets else []
    normalized_pack_id = target_pack_id.strip().lower() if target_pack_id else None
    _ensure_missions_table()
    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE missions
            SET target_pack_id=?, object_targets=?
            WHERE id=?
            """,
            (
                normalized_pack_id,
                json.dumps(normalized_targets) if normalized_targets else None,
                mission_id,
            ),
        )
        conn.commit()
    if cursor.rowcount == 0:
        raise LookupError("Mission not found")
    mission = get_mission(mission_id)
    if mission is None:
        raise LookupError("Mission not found")
    return mission


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
    d["target_pack_id"] = str(d["target_pack_id"]) if d.get("target_pack_id") else None
    if d.get("object_targets"):
        try:
            loaded_targets = json.loads(d["object_targets"])
            d["object_targets"] = normalize_object_targets(loaded_targets)
        except Exception as exc:
            logger.debug("[MISSION] Invalid object target payload for mission %s: %s", d.get("id"), exc)
            d["object_targets"] = []
    else:
        d["object_targets"] = []
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
