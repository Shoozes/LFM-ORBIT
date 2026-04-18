"""
observation_store.py — Persistent cache for agent VLM observations.

Every time the ground or satellite agent produces a VLM explanation for a
bounding-box region, the result is stored alongside the frame metadata so
the same frames can be served later without re-hitting the NASA API or
re-running inference.

Storage layout (under assets/observation_store/):
    <chunk_sig>.json   — observation record (metadata + VLM text + frame refs)

The chunk signature is the same MD5-based hash used by seed_nasa_cache so
records share the same key space. If a seeded WebM already exists, the
observation record enriches it with additional agent observations over time.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_STORE_DIR = Path(__file__).resolve().parent.parent / "assets" / "observation_store"


def _ensure_dir() -> Path:
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    return _STORE_DIR


def _chunk_sig(bbox: list[float]) -> str:
    rounded = [round(b, 3) for b in bbox]
    return hashlib.md5(str(rounded).encode()).hexdigest()[:8]


def load_observation(bbox: list[float]) -> dict | None:
    """Return stored observation record for a bbox, or None if not found."""
    sig = _chunk_sig(bbox)
    path = _STORE_DIR / f"{sig}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("[OBS] Failed to load observation %s: %s", sig, exc)
        return None


def load_observation_by_sig(sig: str) -> dict | None:
    path = _STORE_DIR / f"{sig}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("[OBS] Failed to load observation %s: %s", sig, exc)
        return None


def save_observation(
    bbox: list[float],
    agent_role: str,
    vlm_text: str,
    cell_id: str | None = None,
    frame_years: list[int] | None = None,
    source: str = "nasa_gibs",
    extra: dict | None = None,
) -> str:
    """
    Persist a VLM observation. Appends to existing record if one exists.
    Returns the chunk signature key.
    """
    sig = _chunk_sig(bbox)
    store = _ensure_dir()
    path = store / f"{sig}.json"

    now = datetime.now(timezone.utc).isoformat()

    observation_entry = {
        "timestamp": now,
        "agent_role": agent_role,
        "cell_id": cell_id,
        "vlm_text": vlm_text,
    }
    if extra:
        observation_entry.update(extra)

    if path.exists():
        try:
            with open(path, "r") as f:
                record = json.load(f)
        except Exception:
            record = {}
    else:
        record = {
            "chunk_signature": sig,
            "bbox": bbox,
            "frame_years": frame_years or [],
            "source": source,
            "created_at": now,
            "observations": [],
            "training_ready": False,
        }

    record.setdefault("observations", [])
    record["observations"].append(observation_entry)
    record["last_updated"] = now

    # Mark training-ready once we have at least one satellite + one ground observation
    roles = {o["agent_role"] for o in record["observations"]}
    record["training_ready"] = ("satellite" in roles or "ground" in roles)

    try:
        with open(path, "w") as f:
            json.dump(record, f, indent=2)
        logger.info("[OBS] Saved observation for sig=%s role=%s cell=%s", sig, agent_role, cell_id)
    except Exception as exc:
        logger.warning("[OBS] Failed to write observation %s: %s", sig, exc)

    return sig


def list_observations(training_ready_only: bool = False) -> list[dict]:
    """Return all stored observation records."""
    store = _ensure_dir()
    records = []
    for path in store.glob("*.json"):
        try:
            with open(path, "r") as f:
                rec = json.load(f)
            if training_ready_only and not rec.get("training_ready"):
                continue
            records.append(rec)
        except Exception:
            continue
    return records
