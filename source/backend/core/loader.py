"""
Temporal observation loader for Canopy Sentinel.

This module provides temporal observations (before/after windows) for
vegetation change detection. It exclusively uses direct Sentinel Hub access.
"""

import logging
from typing import Optional

from core.config import REGION
from core.contracts import ObservationPair

logger = logging.getLogger(__name__)

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
        logger.warning("Sentinel Hub direct error for cell %s: %s", cell_id, e)
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
        logger.warning("NASA API direct error for cell %s: %s", cell_id, e)
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
        logger.warning("SimSat API client error for cell %s: %s", cell_id, e)
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
    
    # 20% chance of disturbance
    if (h % 100) < 20:
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
            "label": REGION.before_label,
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
    if REGION.observation_mode != "simulate_only":
        if REGION.observation_mode == "simsat_sentinel":
            result = _try_load_simsat_observations(cell_id)
            if result is not None:
                return result
            logger.warning(f"SimSat client failed for {cell_id}.")
            import os
            if os.environ.get("DISABLE_EXTERNAL_APIS", "false").lower() == "true":
                logger.warning("External APIs disabled, skipping Sentinel Hub and NASA. Falling back to semi_real_loader_v1.")
                return _load_semi_real_observations(cell_id)
            
            logger.warning(f"Falling back to Sentinel Hub direct.")
            
            # Cascade down to Sentinel Hub
            result = _try_load_sentinelhub_observations(cell_id)
            if result is not None:
                return result
            logger.warning(f"Sentinel Hub failed for {cell_id}, falling back to NASA API.")
            
            # Cascade down to NASA
            result = _try_load_nasa_observations(cell_id)
            if result is not None:
                return result
            logger.warning(f"NASA API fallback also failed for {cell_id}, falling back to semi_real_loader_v1.")

        elif REGION.observation_mode == "nasa_api_direct":
            result = _try_load_nasa_observations(cell_id)
            if result is not None:
                return result
            logger.warning(f"NASA API failed for {cell_id}, falling back to semi_real_loader_v1.")
            
        else:
            # Default to sentinelhub_direct
            result = _try_load_sentinelhub_observations(cell_id)
            if result is not None:
                return result
                
            logger.warning(f"Sentinel Hub failed for {cell_id}, falling back to NASA API.")
            
            # Fallback to NASA API before giving up to mock
            result = _try_load_nasa_observations(cell_id)
            if result is not None:
                return result
                
            logger.warning(f"NASA API fallback also failed for {cell_id}, falling back to semi_real_loader_v1.")

    return _load_semi_real_observations(cell_id)