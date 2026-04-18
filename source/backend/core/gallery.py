"""
Gallery — imagery chips for confirmed deforestation cells, linked to map pins.

Populated autonomously by the ground agent when it confirms a cell.
Stores ESRI context imagery as base64. Before/after chips stored when SimSat is available.
Each gallery item now also stores the timelapse MP4 (base64) and its temporal analysis text
so the operator can review the full temporal evidence in one place.

The gallery provides the visual evidence layer — each confirmed detection
becomes a card showing the before/after state of that location, plus a
playable timelapse video derived from the ground agent's temporal analysis pass.
"""

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from core.agent_bus import _connect, init_bus

logger = logging.getLogger(__name__)

_ESRI_EXPORT = (
    "https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/export"
)
_THUMBNAIL_SIZE = 192
_IMAGERY_TIMEOUT = 10.0


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _ensure_gallery_table() -> None:
    init_bus()
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gallery_items (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                cell_id         TEXT NOT NULL UNIQUE,
                lat             REAL NOT NULL,
                lng             REAL NOT NULL,
                label           TEXT NOT NULL,
                severity        TEXT,
                change_score    REAL,
                mission_id      INTEGER,
                context_thumb   TEXT,
                timelapse_b64   TEXT,
                timelapse_analysis TEXT,
                created_at      TEXT NOT NULL
            )
            """
        )
        # Migrate: add timelapse columns if they don't exist yet
        existing_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(gallery_items)").fetchall()
        }
        if "timelapse_b64" not in existing_cols:
            conn.execute("ALTER TABLE gallery_items ADD COLUMN timelapse_b64 TEXT")
        if "timelapse_analysis" not in existing_cols:
            conn.execute("ALTER TABLE gallery_items ADD COLUMN timelapse_analysis TEXT")
        conn.commit()


def _fetch_thumbnail(lat: float, lng: float, size: int = _THUMBNAIL_SIZE) -> str | None:
    """Fetch a small ESRI World Imagery chip as base64."""
    buf = 0.05
    bbox = f"{lng-buf},{lat-buf},{lng+buf},{lat+buf}"
    try:
        with httpx.Client(timeout=_IMAGERY_TIMEOUT) as client:
            r = client.get(
                _ESRI_EXPORT,
                params={
                    "bbox": bbox,
                    "bboxSR": "4326",
                    "imageSR": "4326",
                    "size": f"{size},{size}",
                    "format": "png32",
                    "f": "image",
                },
            )
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
            return "data:image/png;base64," + base64.b64encode(r.content).decode()
    except Exception as exc:
        logger.debug("[GALLERY] Thumbnail fetch failed: %s", exc)
    
    # Fallback: colored placeholder based on lat/lng to look like a "chip"
    import random
    r_val = int((lat * 100) % 50 + 20)
    g_val = int((lng * 100) % 50 + 60)
    b_val = int(((lat + lng) * 100) % 50 + 20)
    svg = f'<svg width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg"><rect width="100%" height="100%" fill="rgb({r_val},{g_val},{b_val})"/><text x="10" y="20" fill="white" font-family="monospace" font-size="10">OFFLINE CHIP</text></svg>'
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def add_gallery_item(
    cell_id: str,
    lat: float,
    lng: float,
    severity: str,
    change_score: float,
    mission_id: int | None = None,
    fetch_thumb: bool = True,
    timelapse_b64: str | None = None,
    timelapse_analysis: str | None = None,
) -> int | None:
    """Add or update a gallery item for a confirmed cell. Returns the item id."""
    _ensure_gallery_table()

    thumb = None
    if fetch_thumb:
        try:
            thumb = _fetch_thumbnail(lat, lng)
        except Exception:
            pass

    label = f"Cell {cell_id[:8]} · {severity.upper()}"

    with _connect() as conn:
        # Use INSERT OR REPLACE so re-confirmations update the record
        cursor = conn.execute(
            """
            INSERT OR REPLACE INTO gallery_items
              (cell_id, lat, lng, label, severity, change_score, mission_id,
               context_thumb, timelapse_b64, timelapse_analysis, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cell_id, lat, lng, label, severity,
                round(change_score, 4), mission_id, thumb,
                timelapse_b64, timelapse_analysis, _now(),
            ),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]


def list_gallery(
    mission_id: int | None = None,
    severity: str | None = None,
    limit: int = 60,
) -> list[dict[str, Any]]:
    """Return gallery metadata (no large image blobs). Use get_gallery_item for images."""
    _ensure_gallery_table()
    clauses: list[str] = []
    params: list[Any] = []
    if mission_id is not None:
        clauses.append("mission_id = ?")
        params.append(mission_id)
    if severity:
        clauses.append("severity = ?")
        params.append(severity)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, cell_id, lat, lng, label, severity, change_score,
                   mission_id, created_at,
                   CASE WHEN context_thumb IS NOT NULL THEN 1 ELSE 0 END AS has_thumb,
                   CASE WHEN timelapse_b64 IS NOT NULL THEN 1 ELSE 0 END AS has_timelapse,
                   timelapse_analysis
            FROM gallery_items
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def get_gallery_item(cell_id: str) -> dict[str, Any] | None:
    """Return full gallery item including context_thumb b64 and timelapse_b64."""
    _ensure_gallery_table()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM gallery_items WHERE cell_id = ?", (cell_id,)
        ).fetchone()
    return dict(row) if row else None
