import json
import os
import sqlite3
from contextlib import AbstractContextManager
from typing import Any

from core.config import (
    REGION,
    imagery_origin_for_source,
    normalize_runtime_truth_mode,
    runtime_truth_mode_for_source,
    scoring_basis_for_source,
)
from core.contracts import RecentAlertsResponse
from core.paths import get_runtime_data_dir
from core.sqlite import managed_connection

DEFAULT_DB_PATH = str(get_runtime_data_dir() / "dtn_queue.sqlite")


def get_db_path() -> str:
    return os.getenv("CANOPY_SENTINEL_DB_PATH", str(get_runtime_data_dir() / "dtn_queue.sqlite"))


def _connect() -> AbstractContextManager[sqlite3.Connection]:
    db_path = get_db_path()
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=5.0)
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.row_factory = sqlite3.Row
    return managed_connection(connection)


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
            downlinked BOOLEAN DEFAULT 0,
            mission_id INTEGER,
            use_case_id TEXT,
            target_pack_id TEXT
        )
        """
    )

    candidate_columns = _column_names(connection, "candidates")
    required_candidate_columns = {"mission_id", "cell_id", "acquisition_key", "distinct_acquisition_count"}
    if candidate_columns and not required_candidate_columns.issubset(candidate_columns):
        # Candidate counts are transient and cannot be safely assigned to a
        # mission/acquisition after the schema upgrade, so discard only this
        # derived state.
        connection.execute("DROP TABLE candidates")

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS candidates (
            mission_id INTEGER NOT NULL,
            cell_id TEXT NOT NULL,
            acquisition_key TEXT NOT NULL,
            first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            distinct_acquisition_count INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (mission_id, cell_id, acquisition_key)
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_candidates_mission ON candidates (mission_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_candidates_mission_cell ON candidates (mission_id, cell_id)"
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

    if "runtime_truth_mode" not in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN runtime_truth_mode TEXT DEFAULT 'unknown'")

    if "imagery_origin" not in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN imagery_origin TEXT DEFAULT 'unknown'")

    if "scoring_basis" not in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN scoring_basis TEXT DEFAULT 'unknown'")

    if "before_window" not in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN before_window TEXT")

    if "after_window" not in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN after_window TEXT")

    if "boundary_context" not in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN boundary_context TEXT")

    if "detection_summary" not in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN detection_summary TEXT")

    if "object_deltas" not in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN object_deltas TEXT")

    if "visual_model_review" not in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN visual_model_review TEXT")

    if "wildfire_assessment" not in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN wildfire_assessment TEXT")

    if "mission_id" not in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN mission_id INTEGER")

    if "use_case_id" not in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN use_case_id TEXT")

    if "target_pack_id" not in columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN target_pack_id TEXT")

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


def upsert_candidate(mission_id: int, cell_id: str, acquisition_key: str = "legacy") -> int:
    """Record one distinct acquisition and return the cell's distinct count."""
    mission_id = int(mission_id)
    if mission_id <= 0:
        raise ValueError("mission_id must be positive")
    cell_id = str(cell_id).strip()
    if not cell_id:
        raise ValueError("cell_id is required")
    acquisition_key = str(acquisition_key).strip()
    if not acquisition_key:
        raise ValueError("acquisition_key is required")
    with _connect() as connection:
        _migrate_alerts_schema(connection)
        connection.execute(
            """
            INSERT OR IGNORE INTO candidates (mission_id, cell_id, acquisition_key)
            VALUES (?, ?, ?)
            """,
            (mission_id, cell_id, acquisition_key),
        )
        row = connection.execute(
            """
            SELECT COUNT(*) AS distinct_count
            FROM candidates
            WHERE mission_id = ? AND cell_id = ?
            """,
            (mission_id, cell_id),
        ).fetchone()
        connection.commit()
        return int(row["distinct_count"])


def remove_candidate(mission_id: int, cell_id: str):
    """Remove a mission-scoped candidate if the anomaly fails to persist."""
    mission_id = int(mission_id)
    if mission_id <= 0:
        raise ValueError("mission_id must be positive")
    with _connect() as connection:
        _migrate_alerts_schema(connection)
        connection.execute(
            "DELETE FROM candidates WHERE mission_id = ? AND cell_id = ?",
            (mission_id, cell_id),
        )
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
    runtime_truth_mode: str | None = None,
    imagery_origin: str | None = None,
    scoring_basis: str | None = None,
    before_window: dict | None = None,
    after_window: dict | None = None,
    boundary_context: list[dict] | None = None,
    detection_summary: dict | None = None,
    object_deltas: list[dict] | None = None,
    visual_model_review: dict | None = None,
    wildfire_assessment: dict | None = None,
    downlinked: bool = False,
    mission_id: int | None = None,
    use_case_id: str | None = None,
    target_pack_id: str | None = None,
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
                runtime_truth_mode,
                imagery_origin,
                scoring_basis,
                before_window,
                after_window,
                boundary_context,
                detection_summary,
                object_deltas,
                visual_model_review,
                wildfire_assessment,
                mission_id,
                use_case_id,
                target_pack_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                runtime_truth_mode
                or runtime_truth_mode_for_source(
                    observation_source,
                    demo_forced_anomaly=demo_forced_anomaly,
                ),
                imagery_origin or imagery_origin_for_source(observation_source),
                scoring_basis or scoring_basis_for_source(observation_source),
                json.dumps(before_window) if before_window else None,
                json.dumps(after_window) if after_window else None,
                json.dumps(boundary_context) if boundary_context else None,
                json.dumps(_compact_detection_summary(detection_summary)) if detection_summary else None,
                json.dumps(object_deltas) if object_deltas else None,
                json.dumps(_compact_visual_model_review(visual_model_review)) if visual_model_review else None,
                json.dumps(wildfire_assessment) if wildfire_assessment else None,
                int(mission_id) if mission_id is not None else None,
                str(use_case_id).strip() if use_case_id else None,
                str(target_pack_id).strip() if target_pack_id else None,
            ),
        )
        connection.commit()


def estimate_payload_bytes(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def estimate_object_proof_payload_bytes(
    *,
    event_id: str,
    cell_id: str,
    action: str,
    detection_summary: dict | None = None,
    object_deltas: list[dict] | None = None,
    provenance: dict | None = None,
) -> int:
    payload: dict[str, Any] = {
        "event_id": event_id,
        "cell_id": cell_id,
        "action": action,
    }
    compact_summary = _compact_detection_summary(detection_summary)
    if compact_summary:
        payload["detections"] = compact_summary
    if object_deltas:
        payload["object_deltas"] = object_deltas
    if provenance:
        payload["provenance"] = provenance
    return estimate_payload_bytes(payload)


def _compact_detection_summary(summary: dict | None) -> dict | None:
    if not isinstance(summary, dict):
        return None
    compact: dict[str, Any] = {
        "target_pack_id": summary.get("target_pack_id"),
        "total_boxes": int(summary.get("total_boxes") or 0),
        "counts_by_label": summary.get("counts_by_label") if isinstance(summary.get("counts_by_label"), dict) else {},
        "top_boxes": [],
        "provenance": summary.get("provenance") if isinstance(summary.get("provenance"), dict) else {},
    }
    for box in summary.get("top_boxes") or []:
        if not isinstance(box, dict):
            continue
        compact["top_boxes"].append({
            "id": box.get("id"),
            "label": box.get("label"),
            "bbox": box.get("bbox"),
            "bbox_format": box.get("bbox_format"),
            "confidence": box.get("confidence"),
            "color_key": box.get("color_key"),
            "source_model": box.get("source_model"),
            "runtime_truth_mode": box.get("runtime_truth_mode"),
            "imagery_origin": box.get("imagery_origin"),
            "scoring_basis": box.get("scoring_basis"),
            "count_quality": box.get("count_quality"),
        })
    return compact


def _compact_visual_model_review(review: dict | None) -> dict | None:
    if not isinstance(review, dict):
        return None
    compact: dict[str, Any] = {
        "status": str(review.get("status") or ("image_conditioned" if review.get("image_conditioned") else "unavailable")),
        "enabled": bool(review.get("enabled", review.get("image_conditioned", False))),
        "image_conditioned": bool(review.get("image_conditioned", False)),
        "abstained": bool(review.get("abstained", False)),
        "runtime_backend": str(review.get("runtime_backend") or ""),
        "runtime_inference_mode": str(review.get("runtime_inference_mode") or ""),
        "response": str(review.get("response") or "").strip(),
        "reason": str(review.get("reason") or "").strip(),
        "visual_model": str(review.get("visual_model") or ""),
        "image_source": str(review.get("image_source") or ""),
        "frame_id": str(review.get("frame_id") or ""),
        "runtime_truth_mode": str(review.get("runtime_truth_mode") or ""),
        "imagery_origin": str(review.get("imagery_origin") or ""),
        "scoring_basis": str(review.get("scoring_basis") or ""),
        "model_revision": str(review.get("model_revision") or ""),
    }
    bbox = review.get("bbox")
    if isinstance(bbox, list):
        compact["bbox"] = bbox[:4]
    reviewed_at = str(review.get("reviewed_at") or "").strip()
    if reviewed_at:
        compact["reviewed_at"] = reviewed_at
    return compact


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
                runtime_truth_mode,
                imagery_origin,
                scoring_basis,
                before_window,
                after_window,
                boundary_context,
                detection_summary,
                object_deltas,
                visual_model_review,
                wildfire_assessment,
                mission_id,
                use_case_id,
                target_pack_id
            FROM alerts
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    alerts: list[dict[str, Any]] = []
    for row in rows:
        observation_source = row["observation_source"] if "observation_source" in row.keys() else "unknown"
        stored_truth_mode = normalize_runtime_truth_mode(
            row["runtime_truth_mode"] if "runtime_truth_mode" in row.keys() else None
        )
        runtime_truth_mode = (
            stored_truth_mode
            if stored_truth_mode != "unknown"
            else runtime_truth_mode_for_source(
                observation_source,
                demo_forced_anomaly=bool(row["demo_forced_anomaly"]),
            )
        )
        stored_imagery_origin = row["imagery_origin"] if "imagery_origin" in row.keys() and row["imagery_origin"] else ""
        stored_scoring_basis = row["scoring_basis"] if "scoring_basis" in row.keys() and row["scoring_basis"] else ""
        imagery_origin = (
            stored_imagery_origin
            if stored_imagery_origin and stored_imagery_origin != "unknown"
            else imagery_origin_for_source(observation_source)
        )
        scoring_basis = (
            stored_scoring_basis
            if stored_scoring_basis and stored_scoring_basis != "unknown"
            else scoring_basis_for_source(observation_source)
        )
        alerts.append(
            {
                "event_id": row["event_id"],
                "region_id": row["region_id"],
                "cell_id": row["cell_id"],
                "mission_id": int(row["mission_id"]) if "mission_id" in row.keys() and row["mission_id"] is not None else None,
                "use_case_id": row["use_case_id"] if "use_case_id" in row.keys() else None,
                "target_pack_id": row["target_pack_id"] if "target_pack_id" in row.keys() else None,
                "change_score": float(row["change_score"]),
                "confidence": float(row["confidence"]),
                "priority": row["priority"],
                "reason_codes": json.loads(row["reason_codes"]),
                "payload_bytes": int(row["payload_bytes"]),
                "timestamp": row["timestamp"],
                "downlinked": bool(row["downlinked"]),
                "demo_forced_anomaly": bool(row["demo_forced_anomaly"]),
                "observation_source": observation_source,
                "runtime_truth_mode": runtime_truth_mode,
                "imagery_origin": imagery_origin,
                "scoring_basis": scoring_basis,
                "before_window": json.loads(row["before_window"]) if "before_window" in row.keys() and row["before_window"] else None,
                "after_window": json.loads(row["after_window"]) if "after_window" in row.keys() and row["after_window"] else None,
                "boundary_context": json.loads(row["boundary_context"]) if "boundary_context" in row.keys() and row["boundary_context"] else None,
                "detection_summary": json.loads(row["detection_summary"]) if "detection_summary" in row.keys() and row["detection_summary"] else None,
                "object_deltas": json.loads(row["object_deltas"]) if "object_deltas" in row.keys() and row["object_deltas"] else None,
                "visual_model_review": json.loads(row["visual_model_review"]) if "visual_model_review" in row.keys() and row["visual_model_review"] else None,
                "wildfire_assessment": json.loads(row["wildfire_assessment"]) if "wildfire_assessment" in row.keys() and row["wildfire_assessment"] else None,
            }
        )

    return {
        "region_id": REGION.region_id,
        "alerts": alerts,
    }
