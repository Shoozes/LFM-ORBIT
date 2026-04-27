import json
import os
import sqlite3
from typing import Any

from core.config import REGION
from core.contracts import RecentAlertsResponse

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "../../../runtime-data/dtn_queue.sqlite")


def get_db_path() -> str:
    return os.getenv("CANOPY_SENTINEL_DB_PATH", DEFAULT_DB_PATH)


def _connect() -> sqlite3.Connection:
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def _column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"]) for row in rows}


def _migrate_alerts_schema(connection: sqlite3.Connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            region_id TEXT NOT NULL,
            cell_id TEXT NOT NULL,
            change_score REAL NOT NULL,
            confidence REAL NOT NULL,
            priority TEXT NOT NULL,
            reason_codes TEXT NOT NULL,
            payload_bytes INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            downlinked BOOLEAN DEFAULT 0
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS candidates (
            cell_id TEXT PRIMARY KEY,
            first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            consecutive_anomaly_count INTEGER DEFAULT 1
        )
        """
    )

    columns = _column_names(connection, "alerts")

    if "cell_id" not in columns and "hex_id" in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN cell_id TEXT")
        connection.execute("UPDATE alerts SET cell_id = hex_id WHERE cell_id IS NULL")

    if "downlinked" not in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN downlinked BOOLEAN DEFAULT 0")

    if "demo_forced_anomaly" not in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN demo_forced_anomaly BOOLEAN DEFAULT 0")

    if "observation_source" not in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN observation_source TEXT DEFAULT 'unknown'")

    if "before_window" not in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN before_window TEXT")

    if "after_window" not in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN after_window TEXT")

    if "boundary_context" not in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN boundary_context TEXT")

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_alerts_event_id
        ON alerts (event_id)
        """
    )


def init_db(reset: bool = False):
    with _connect() as connection:
        _migrate_alerts_schema(connection)
        if reset:
            connection.execute("DELETE FROM alerts")
            connection.execute("DELETE FROM candidates")
        connection.commit()

def upsert_candidate(cell_id: str) -> int:
    """Record or update a candidate, returning the new consecutive anomaly count."""
    with _connect() as connection:
        _migrate_alerts_schema(connection)
        row = connection.execute("SELECT consecutive_anomaly_count FROM candidates WHERE cell_id = ?", (cell_id,)).fetchone()
        if row:
            new_count = row["consecutive_anomaly_count"] + 1
            connection.execute("UPDATE candidates SET consecutive_anomaly_count = ? WHERE cell_id = ?", (new_count, cell_id))
        else:
            new_count = 1
            connection.execute("INSERT INTO candidates (cell_id, consecutive_anomaly_count) VALUES (?, 1)", (cell_id,))
        connection.commit()
        return new_count

def remove_candidate(cell_id: str):
    """Remove a candidate if the anomaly fails to persist."""
    with _connect() as connection:
        _migrate_alerts_schema(connection)
        connection.execute("DELETE FROM candidates WHERE cell_id = ?", (cell_id,))
        connection.commit()


def push_alert(
    event_id: str,
    region_id: str,
    cell_id: str,
    change_score: float,
    confidence: float,
    priority: str,
    reason_codes: list[str],
    payload_bytes: int,
    demo_forced_anomaly: bool = False,
    observation_source: str = "unknown",
    before_window: dict | None = None,
    after_window: dict | None = None,
    boundary_context: list[dict] | None = None,
    downlinked: bool = False,
):
    with _connect() as connection:
        _migrate_alerts_schema(connection)
        connection.execute(
            """
            INSERT INTO alerts (
                event_id,
                region_id,
                cell_id,
                change_score,
                confidence,
                priority,
                reason_codes,
                payload_bytes,
                downlinked,
                demo_forced_anomaly,
                observation_source,
                before_window,
                after_window,
                boundary_context
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                region_id,
                cell_id,
                change_score,
                confidence,
                priority,
                json.dumps(reason_codes),
                payload_bytes,
                1 if downlinked else 0,
                1 if demo_forced_anomaly else 0,
                observation_source,
                json.dumps(before_window) if before_window else None,
                json.dumps(after_window) if after_window else None,
                json.dumps(boundary_context) if boundary_context else None,
            ),
        )
        connection.commit()


def estimate_payload_bytes(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def get_alert_counts() -> dict[str, int]:
    with _connect() as connection:
        _migrate_alerts_schema(connection)
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_alerts,
                COALESCE(SUM(payload_bytes), 0) AS total_payload_bytes
            FROM alerts
            """
        ).fetchone()

    return {
        "total_alerts": int(row["total_alerts"]),
        "total_payload_bytes": int(row["total_payload_bytes"]),
    }


def get_recent_alerts(limit: int = 50) -> RecentAlertsResponse:
    safe_limit = max(1, min(limit, 200))

    with _connect() as connection:
        _migrate_alerts_schema(connection)
        columns = _column_names(connection, "alerts")
        has_hex_id = "hex_id" in columns

        if has_hex_id:
            cell_id_expr = "COALESCE(cell_id, hex_id)"
        else:
            cell_id_expr = "cell_id"

        rows = connection.execute(
            f"""
            SELECT
                event_id,
                region_id,
                {cell_id_expr} AS cell_id,
                change_score,
                confidence,
                priority,
                reason_codes,
                payload_bytes,
                timestamp,
                downlinked,
                demo_forced_anomaly,
                observation_source,
                before_window,
                after_window,
                boundary_context
            FROM alerts
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    alerts: list[dict[str, Any]] = []
    for row in rows:
        alerts.append(
            {
                "event_id": row["event_id"],
                "region_id": row["region_id"],
                "cell_id": row["cell_id"],
                "change_score": float(row["change_score"]),
                "confidence": float(row["confidence"]),
                "priority": row["priority"],
                "reason_codes": json.loads(row["reason_codes"]),
                "payload_bytes": int(row["payload_bytes"]),
                "timestamp": row["timestamp"],
                "downlinked": bool(row["downlinked"]),
                "demo_forced_anomaly": bool(row["demo_forced_anomaly"]),
                "observation_source": row["observation_source"] if "observation_source" in row.keys() else "unknown",
                "before_window": json.loads(row["before_window"]) if "before_window" in row.keys() and row["before_window"] else None,
                "after_window": json.loads(row["after_window"]) if "after_window" in row.keys() and row["after_window"] else None,
                "boundary_context": json.loads(row["boundary_context"]) if "boundary_context" in row.keys() and row["boundary_context"] else None,
            }
        )

    return {
        "region_id": REGION.region_id,
        "alerts": alerts,
    }
