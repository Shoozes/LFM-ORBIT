"""Append-only mission archive for reset-safe operator intent records."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.paths import get_runtime_data_dir


ARCHIVE_SCHEMA = "orbit_mission_archive_v1"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def get_mission_archive_path() -> Path:
    raw_path = os.getenv("CANOPY_SENTINEL_MISSION_ARCHIVE_PATH")
    if raw_path:
        return Path(raw_path).expanduser()

    if os.getenv("CANOPY_SENTINEL_RUNTIME_DIR"):
        return get_runtime_data_dir() / "mission-archive" / "mission_history.jsonl"

    bus_path = os.getenv("AGENT_BUS_PATH")
    if bus_path:
        return Path(bus_path).expanduser().parent / "mission-archive" / "mission_history.jsonl"

    return get_runtime_data_dir() / "mission-archive" / "mission_history.jsonl"


def _archive_key(mission: dict[str, Any]) -> str:
    return "|".join(
        [
            str(mission.get("id") or ""),
            str(mission.get("created_at") or ""),
            str(mission.get("task_text") or ""),
            str(mission.get("target_pack_id") or ""),
        ]
    )


def _read_existing_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = row.get("archive_key")
        if key:
            keys.add(str(key))
    return keys


def append_mission_archive(
    missions: list[dict[str, Any]],
    *,
    source: str = "manual",
) -> dict[str, Any]:
    path = get_mission_archive_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_keys = _read_existing_keys(path)
    rows: list[dict[str, Any]] = []

    for mission in missions:
        if not isinstance(mission, dict):
            continue
        key = _archive_key(mission)
        if key in existing_keys:
            continue
        rows.append(
            {
                "archive_schema": ARCHIVE_SCHEMA,
                "archive_key": key,
                "archive_source": source,
                "archived_at": _now(),
                "mission": mission,
            }
        )
        existing_keys.add(key)

    if rows:
        with path.open("a", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")

    return {
        "mission_archive_path": str(path),
        "missions_archived": len(rows),
    }


def archive_current_missions(*, limit: int = 500, source: str = "runtime_reset") -> dict[str, Any]:
    from core.mission import list_missions

    missions = list_missions(limit=max(1, min(int(limit), 5000)))
    return append_mission_archive(missions, source=source)


def read_mission_archive(*, limit: int = 500) -> list[dict[str, Any]]:
    path = get_mission_archive_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("archive_schema") == ARCHIVE_SCHEMA:
            rows.append(row)
    return rows[-max(1, int(limit)) :][::-1]
