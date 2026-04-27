"""
Temporal observation loader for LFM Orbit.

This module provides temporal observations (before/after windows) for
vegetation change detection. It exclusively uses direct Sentinel Hub access.
"""

import logging
from typing import Optional
import json
import sqlite3
import os
from pathlib import Path

from core.config import PROVIDER_SIMSAT_MAPBOX, PROVIDER_SIMSAT_SENTINEL, REGION
from core.contracts import ObservationPair
from core.observability import log_throttled
from core.paths import get_api_cache_path

logger = logging.getLogger(__name__)

CACHE_PATH = str(get_api_cache_path())


def _cache_key_for_cell(cell_id: str) -> str:
    return f"{REGION.observation_mode}:{REGION.before_label}:{REGION.after_label}:{cell_id}"


def _init_cache():
    os.makedirs(Path(CACHE_PATH).parent, exist_ok=True)
    with sqlite3.connect(CACHE_PATH) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS obs_cache (cell_id TEXT PRIMARY KEY, observation_json TEXT)"
        )

try:
    _init_cache()
except Exception as e:
    logger.warning(f"Failed to initialize API cache DB: {e}")

def _get_cached_obs(cell_id: str) -> Optional[ObservationPair]:
    cache_key = _cache_key_for_cell(cell_id)
    try:
        with sqlite3.connect(CACHE_PATH) as conn:
            cursor = conn.execute("SELECT observation_json FROM obs_cache WHERE cell_id = ?", (cache_key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
    except Exception as exc:
        logger.debug("Failed reading observation cache for %s: %s", cache_key, exc)
    return None

def _set_cached_obs(cell_id: str, obs: ObservationPair):
    cache_key = _cache_key_for_cell(cell_id)
    try:
        with sqlite3.connect(CACHE_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO obs_cache (cell_id, observation_json) VALUES (?, ?)",
                (cache_key, json.dumps(obs))
            )
    except Exception as exc:
        logger.debug("Failed writing observation cache for %s: %s", cache_key, exc)

SOURCE_SENTINELHUB_DIRECT = "sentinelhub_direct_imagery"


def _try_load_sentinelhub_observations(cell_id: str) -> Optional[ObservationPair]:
    """Attempt to load observations via direct Sentinel Hub access."""
    try:
        from core.sentinel_provider import fetch_sentinelhub_observations

        result = fetch_sentinelhub_observations(cell_id)
        return result
    except ImportError:
        logger.debug("sentinel_provider module not available")
        return None
    except Exception as e:
        log_throttled(
            logger,
            logging.WARNING,
            f"loader:sentinelhub_direct_error:{type(e).__name__}:{str(e)}",
            "Sentinel Hub direct error for cell %s: %s",
            cell_id,
            e,
        )
        return None

def _try_load_nasa_observations(cell_id: str) -> Optional[ObservationPair]:
    """Attempt to load observations via direct NASA API access."""
    try:
        from core.nasa_provider import fetch_nasa_observations

        result = fetch_nasa_observations(cell_id)
        return result
    except ImportError:
        logger.debug("nasa_provider module not available")
        return None
    except Exception as e:
        log_throttled(
            logger,
            logging.WARNING,
            f"loader:nasa_direct_error:{type(e).__name__}:{str(e)}",
            "NASA API direct error for cell %s: %s",
            cell_id,
            e,
        )
        return None

def _try_load_simsat_observations(cell_id: str) -> Optional[ObservationPair]:
    """Attempt to load observations via local SimSat API."""
    try:
        from core.simsat_provider import fetch_simsat_observations

        result = fetch_simsat_observations(cell_id)
        return result
    except ImportError:
        logger.debug("simsat_provider module not available")
        return None
    except Exception as e:
        log_throttled(
            logger,
            logging.WARNING,
            f"loader:simsat_api_error:{type(e).__name__}:{str(e)}",
            "SimSat API client error for cell %s: %s",
            cell_id,
            e,
        )
        return None


def _try_load_simsat_mapbox_observations(cell_id: str) -> Optional[ObservationPair]:
    """Attempt to load observations via SimSat's optional Mapbox endpoint."""
    if not (os.environ.get("MAPBOX_ACCESS_TOKEN") or os.environ.get("MAPBOX_API_TOKEN")):
        return None
    try:
        from core.simsat_provider import fetch_simsat_observations

        return fetch_simsat_observations(cell_id, provider=PROVIDER_SIMSAT_MAPBOX)
    except ImportError:
        logger.debug("simsat_provider module not available")
        return None
    except Exception as e:
        log_throttled(
            logger,
            logging.WARNING,
            f"loader:simsat_mapbox_error:{type(e).__name__}:{str(e)}",
            "SimSat Mapbox client error for cell %s: %s",
            cell_id,
            e,
        )
        return None


import hashlib
from core.grid import cell_to_latlng

SOURCE_SEMI_REAL = "semi_real_loader_v1"

def _load_semi_real_observations(cell_id: str) -> ObservationPair:
    """Deterministic mock based on cell_id hash."""
    centroid_lat, centroid_lng = cell_to_latlng(cell_id)

    h = int(hashlib.md5(cell_id.encode()).hexdigest(), 16)

    # Base bands (healthy vegetation)
    before_bands = {
        "nir": 0.65 + (h % 10) * 0.01,
        "red": 0.08 + ((h >> 4) % 10) * 0.005,
        "swir": 0.15 + ((h >> 8) % 10) * 0.01,
    }

    after_bands = dict(before_bands)

    before_flags = []
    after_flags = []

    # 5% chance of QC rejection due to mock clouds
    if (h % 100) < 5:
        raise ValueError("Scene Quality Rejected: Insufficient Valid Pixels")

    # 20% chance of disturbance
    if (h % 100) < 25:
        after_bands["nir"] *= 0.4
        after_bands["red"] *= 1.8
        after_bands["swir"] *= 1.5
        after_flags.append("disturbance_pattern")

    return {
        "source": SOURCE_SEMI_REAL,
        "cell_id": cell_id,
        "centroid_lat": round(centroid_lat, 6),
        "centroid_lng": round(centroid_lng, 6),
        "before": {
            "label": f"Baseline {REGION.after_label} (-2Y)",
            "quality": 0.95,
            "bands": before_bands,
            "flags": before_flags,
        },
        "after": {
            "label": REGION.after_label,
            "quality": 0.95,
            "bands": after_bands,
            "flags": after_flags,
        },
    }

def load_temporal_observations(cell_id: str) -> ObservationPair:
    """Load temporal observations for a cell.

    Args:
        cell_id: H3 cell identifier

    Returns:
        ObservationPair containing before and after windows with band values
    """
    cached = _get_cached_obs(cell_id)
    if cached:
        return cached

    result = None

    if REGION.observation_mode != "simulate_only":
        if REGION.observation_mode in (PROVIDER_SIMSAT_SENTINEL, PROVIDER_SIMSAT_MAPBOX):
            result = _try_load_simsat_observations(cell_id)
            if result is None:
                log_throttled(
                    logger,
                    logging.WARNING,
                    "loader:simsat_client_failed",
                    "SimSat client failed for %s.",
                    cell_id,
                )
                if (
                    REGION.observation_mode == PROVIDER_SIMSAT_SENTINEL
                    and os.environ.get("DISABLE_EXTERNAL_APIS", "false").lower() != "true"
                ):
                    result = _try_load_simsat_mapbox_observations(cell_id)
                    if result is not None:
                        log_throttled(
                            logger,
                            logging.INFO,
                            "loader:fallback_to_simsat_mapbox",
                            "Falling back to SimSat Mapbox.",
                        )
                if os.environ.get("DISABLE_EXTERNAL_APIS", "false").lower() == "true":
                    log_throttled(
                        logger,
                        logging.WARNING,
                        "loader:external_apis_disabled",
                        "External APIs disabled, skipping Sentinel Hub and NASA. Falling back to %s.",
                        SOURCE_SEMI_REAL,
                    )
                    result = _load_semi_real_observations(cell_id)
                elif result is None:
                    log_throttled(
                        logger,
                        logging.WARNING,
                        "loader:fallback_to_sentinelhub",
                        "Falling back to Sentinel Hub direct.",
                    )
                    result = _try_load_sentinelhub_observations(cell_id)
                    if result is None:
                        log_throttled(
                            logger,
                            logging.WARNING,
                            "loader:sentinelhub_failed_fallback_nasa",
                            "Sentinel Hub failed for %s, falling back to NASA API.",
                            cell_id,
                        )
                        result = _try_load_nasa_observations(cell_id)
                        if result is None:
                            log_throttled(
                                logger,
                                logging.WARNING,
                                "loader:nasa_failed_fallback_semi_real",
                                "NASA API fallback also failed for %s, falling back to %s.",
                                cell_id,
                                SOURCE_SEMI_REAL,
                            )

        elif REGION.observation_mode == "nasa_api_direct":
            result = _try_load_nasa_observations(cell_id)
            if result is None:
                log_throttled(
                    logger,
                    logging.WARNING,
                    "loader:nasa_failed_fallback_semi_real_direct",
                    "NASA API failed for %s, falling back to %s.",
                    cell_id,
                    SOURCE_SEMI_REAL,
                )

        else:
            result = _try_load_sentinelhub_observations(cell_id)
            if result is None:
                log_throttled(
                    logger,
                    logging.WARNING,
                    "loader:sentinelhub_failed_fallback_nasa_direct",
                    "Sentinel Hub failed for %s, falling back to NASA API.",
                    cell_id,
                )
                result = _try_load_nasa_observations(cell_id)
                if result is None:
                    log_throttled(
                        logger,
                        logging.WARNING,
                        "loader:nasa_failed_fallback_semi_real_general",
                        "NASA API fallback also failed for %s, falling back to %s.",
                        cell_id,
                        SOURCE_SEMI_REAL,
                    )

    if result is None:
        result = _load_semi_real_observations(cell_id)

    if result is not None:
        _set_cached_obs(cell_id, result)

    return result
