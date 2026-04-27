"""
Agent Message Bus — SQLite-backed inter-agent communication channel.

Provides a durable, ordered message queue between the Satellite Pruner
and the Ground Validator agents. Zero external dependencies (no Redis, no broker).

Message schema:
  - id: auto-increment primary key
  - sender: "satellite" | "ground"
  - recipient: "ground" | "satellite" | "broadcast"
  - msg_type: "flag" | "query" | "confirmation" | "status" | "heartbeat"
  - cell_id: H3 cell identifier (nullable for non-cell messages)
  - payload: JSON blob with message-specific data
  - timestamp: ISO UTC timestamp
  - read: bool — whether the recipient has consumed the message
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

_DEFAULT_BUS_PATH = os.path.join(
    os.path.dirname(__file__), "../../../runtime-data/agent_bus.sqlite"
)


def _bus_path() -> str:
    return os.getenv("AGENT_BUS_PATH", _DEFAULT_BUS_PATH)


def _connect() -> sqlite3.Connection:
    path = _bus_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_bus(reset: bool = False) -> None:
    """Create agent_messages and map_pins tables if they don't exist."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_messages (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                sender    TEXT NOT NULL,
                recipient TEXT NOT NULL,
                msg_type  TEXT NOT NULL,
                cell_id   TEXT,
                payload   TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                read      INTEGER DEFAULT 0
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_bus_recipient ON agent_messages (recipient, read)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS map_pins (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                pin_type  TEXT NOT NULL,
                cell_id   TEXT,
                lat       REAL NOT NULL,
                lng       REAL NOT NULL,
                label     TEXT NOT NULL,
                note      TEXT,
                severity  TEXT,
                timestamp TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pins_type ON map_pins (pin_type)"
        )
        if reset:
            conn.execute("DELETE FROM agent_messages")
            conn.execute("DELETE FROM map_pins")
        conn.commit()


def post_message(
    sender: str,
    recipient: str,
    msg_type: str,
    payload: dict[str, Any],
    cell_id: str | None = None,
) -> int:
    """Post a message to the bus. Returns the new message id."""
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO agent_messages (sender, recipient, msg_type, cell_id, payload, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                sender,
                recipient,
                msg_type,
                cell_id,
                json.dumps(payload),
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            ),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]


def pull_messages(
    recipient: str,
    limit: int = 20,
    mark_read: bool = True,
) -> list[dict[str, Any]]:
    """Pull unread messages for a recipient, optionally marking them read."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, sender, recipient, msg_type, cell_id, payload, timestamp
            FROM agent_messages
            WHERE recipient IN (?, 'broadcast') AND read = 0
            ORDER BY id ASC
            LIMIT ?
            """,
            (recipient, limit),
        ).fetchall()

        if mark_read and rows:
            ids = [r["id"] for r in rows]
            conn.execute(
                f"UPDATE agent_messages SET read = 1 WHERE id IN ({','.join('?' * len(ids))})",
                ids,
            )
            conn.commit()

    return [
        {
            "id": r["id"],
            "sender": r["sender"],
            "recipient": r["recipient"],
            "msg_type": r["msg_type"],
            "cell_id": r["cell_id"],
            "payload": json.loads(r["payload"]),
            "timestamp": r["timestamp"],
        }
        for r in rows
    ]


def get_recent_dialogue(limit: int = 60) -> list[dict[str, Any]]:
    """Return the N most recent messages from both channels (for frontend display)."""
    init_bus()  # ensure table exists
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, sender, recipient, msg_type, cell_id, payload, timestamp
            FROM agent_messages
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        {
            "id": r["id"],
            "sender": r["sender"],
            "recipient": r["recipient"],
            "msg_type": r["msg_type"],
            "cell_id": r["cell_id"],
            "payload": json.loads(r["payload"]),
            "timestamp": r["timestamp"],
        }
        for r in reversed(rows)  # chronological order
    ]


def mark_messages_read(
    *,
    sender: str | None = None,
    recipient: str | None = None,
    msg_type: str | None = None,
    cell_id: str | None = None,
) -> int:
    """Mark matching messages as read without removing them from dialogue history."""
    init_bus()

    clauses = ["read = 0"]
    params: list[Any] = []
    if sender:
        clauses.append("sender = ?")
        params.append(sender)
    if recipient:
        clauses.append("recipient = ?")
        params.append(recipient)
    if msg_type:
        clauses.append("msg_type = ?")
        params.append(msg_type)
    if cell_id:
        clauses.append("cell_id = ?")
        params.append(cell_id)

    with _connect() as conn:
        cursor = conn.execute(
            f"UPDATE agent_messages SET read = 1 WHERE {' AND '.join(clauses)}",
            params,
        )
        conn.commit()
        return int(cursor.rowcount or 0)


def get_recent_messages(
    *,
    limit: int = 60,
    sender: str | None = None,
    recipient: str | None = None,
    msg_type: str | None = None,
    cell_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return recent bus messages filtered by optional message fields."""
    init_bus()
    safe_limit = max(1, min(int(limit), 500))

    clauses: list[str] = []
    params: list[Any] = []
    if sender:
        clauses.append("sender = ?")
        params.append(sender)
    if recipient:
        clauses.append("recipient = ?")
        params.append(recipient)
    if msg_type:
        clauses.append("msg_type = ?")
        params.append(msg_type)
    if cell_id:
        clauses.append("cell_id = ?")
        params.append(cell_id)

    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, sender, recipient, msg_type, cell_id, payload, timestamp, read
            FROM agent_messages
            {where_clause}
            ORDER BY id DESC
            LIMIT ?
            """,
            (*params, safe_limit),
        ).fetchall()

    return [
        {
            "id": r["id"],
            "sender": r["sender"],
            "recipient": r["recipient"],
            "msg_type": r["msg_type"],
            "cell_id": r["cell_id"],
            "payload": json.loads(r["payload"]),
            "timestamp": r["timestamp"],
            "read": bool(r["read"]),
        }
        for r in reversed(rows)
    ]


def get_bus_stats() -> dict[str, int]:
    init_bus()  # ensure table exists
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN read = 0 THEN 1 ELSE 0 END) AS unread,
                SUM(CASE WHEN sender = 'satellite' THEN 1 ELSE 0 END) AS from_satellite,
                SUM(CASE WHEN sender = 'ground' THEN 1 ELSE 0 END) AS from_ground
            FROM agent_messages
            """
        ).fetchone()
    return {
        "total_messages": int(row["total"] or 0),
        "unread_messages": int(row["unread"] or 0),
        "from_satellite": int(row["from_satellite"] or 0),
        "from_ground": int(row["from_ground"] or 0),
    }


# ---------------------------------------------------------------------------
# Map pin CRUD
# ---------------------------------------------------------------------------

def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def upsert_pin(
    pin_type: str,
    lat: float,
    lng: float,
    label: str,
    note: str = "",
    severity: str | None = None,
    cell_id: str | None = None,
) -> int:
    """
    Insert a map pin. If a pin of the same type+cell_id already exists,
    update it in place (so agents don't accumulate duplicate pins per cell).
    Returns the pin id.
    """
    init_bus()
    with _connect() as conn:
        if cell_id:
            existing = conn.execute(
                "SELECT id FROM map_pins WHERE pin_type = ? AND cell_id = ?",
                (pin_type, cell_id),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE map_pins
                    SET lat=?, lng=?, label=?, note=?, severity=?, timestamp=?
                    WHERE id=?
                    """,
                    (lat, lng, label, note, severity, _now_ts(), existing["id"]),
                )
                conn.commit()
                return int(existing["id"])

        cursor = conn.execute(
            """
            INSERT INTO map_pins (pin_type, cell_id, lat, lng, label, note, severity, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (pin_type, cell_id, lat, lng, label, note, severity, _now_ts()),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]


def list_pins() -> list[dict[str, Any]]:
    """Return all active map pins."""
    init_bus()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, pin_type, cell_id, lat, lng, label, note, severity, timestamp FROM map_pins ORDER BY id ASC"
        ).fetchall()
    return [
        {
            "id": r["id"],
            "pin_type": r["pin_type"],
            "cell_id": r["cell_id"],
            "lat": r["lat"],
            "lng": r["lng"],
            "label": r["label"],
            "note": r["note"] or "",
            "severity": r["severity"],
            "timestamp": r["timestamp"],
        }
        for r in rows
    ]


def get_pin_for_cell(cell_id: str, preferred_types: tuple[str, ...] = ("ground", "satellite", "operator")) -> dict[str, Any] | None:
    """Return the most relevant persisted pin for a cell when available."""
    init_bus()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, pin_type, cell_id, lat, lng, label, note, severity, timestamp
            FROM map_pins
            WHERE cell_id = ?
            ORDER BY id DESC
            """,
            (cell_id,),
        ).fetchall()

    if not rows:
        return None

    pins = [
        {
            "id": r["id"],
            "pin_type": r["pin_type"],
            "cell_id": r["cell_id"],
            "lat": r["lat"],
            "lng": r["lng"],
            "label": r["label"],
            "note": r["note"] or "",
            "severity": r["severity"],
            "timestamp": r["timestamp"],
        }
        for r in rows
    ]

    for pin_type in preferred_types:
        for pin in pins:
            if pin["pin_type"] == pin_type:
                return pin
    return pins[0]


def delete_pin(pin_id: int) -> bool:
    """Delete a pin by id. Returns True if a row was deleted."""
    init_bus()
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM map_pins WHERE id = ?", (pin_id,))
        conn.commit()
        return cursor.rowcount > 0


def clear_pins_by_type(pin_type: str) -> int:
    """Remove all pins of a given type. Returns number of rows deleted."""
    init_bus()
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM map_pins WHERE pin_type = ?", (pin_type,))
        conn.commit()
        return cursor.rowcount
