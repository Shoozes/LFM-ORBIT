"""Local map location resolution and preview-tile helpers."""

from __future__ import annotations

import math
import re
from typing import Any


ESRI_WORLD_IMAGERY_TILE = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def _lon_lat_to_tile(lng: float, lat: float, zoom: int) -> tuple[int, int]:
    safe_lat = _clamp(lat, -85.05112878, 85.05112878)
    lat_rad = math.radians(safe_lat)
    tile_count = 2**zoom
    x = math.floor(((lng + 180.0) / 360.0) * tile_count)
    y = math.floor(((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0) * tile_count)
    max_index = tile_count - 1
    return int(_clamp(x, 0, max_index)), int(_clamp(y, 0, max_index))


def estimate_preview_zoom(bbox: list[float]) -> int:
    west, south, east, north = bbox
    lon_span = max(0.0001, abs(east - west))
    lat_span = max(0.0001, abs(north - south))
    span = max(lon_span, lat_span)
    return int(_clamp(math.floor(math.log2(360.0 / (span * 2.4))), 4, 14))


def build_preview_tiles(bbox: list[float]) -> list[dict[str, Any]]:
    west, south, east, north = bbox
    center_lng = (west + east) / 2.0
    center_lat = (south + north) / 2.0
    zoom = estimate_preview_zoom(bbox)
    center_x, center_y = _lon_lat_to_tile(center_lng, center_lat, zoom)
    max_index = 2**zoom - 1
    tiles: list[dict[str, Any]] = []

    for dy in range(-1, 2):
        for dx in range(-1, 2):
            x = int(_clamp(center_x + dx, 0, max_index))
            y = int(_clamp(center_y + dy, 0, max_index))
            tiles.append({
                "z": zoom,
                "x": x,
                "y": y,
                "url": ESRI_WORLD_IMAGERY_TILE.format(z=zoom, x=x, y=y),
            })
    return tiles


def _score_location(query: str, location_id: str, target: dict[str, Any]) -> tuple[float, str] | None:
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return None
    aliases = [location_id.replace("_", " "), str(target["label"]), *target.get("aliases", [])]
    normalized_aliases = [_normalize_text(str(alias)) for alias in aliases]
    exact_match = normalized_query in normalized_aliases
    contained_aliases = [alias for alias in normalized_aliases if alias and alias in normalized_query]
    contains_query = any(normalized_query in alias for alias in normalized_aliases if alias)

    if not exact_match and not contained_aliases and not contains_query:
        return None

    score = 0.58
    reasons: list[str] = []
    if exact_match:
        score += 0.28
        reasons.append("Exact vetted-name match")
    if contained_aliases:
        score += min(0.18, 0.06 * len(contained_aliases))
        reasons.append("Destination phrase contains a known alias")
    if contains_query:
        score += 0.05
        reasons.append("Query matches a vetted location alias")
    if target.get("bbox"):
        score += 0.04
        reasons.append("bounded location target")
    if target.get("center"):
        score += 0.02
    confidence = round(_clamp(score, 0.0, 0.98), 2)
    return confidence, ", ".join(reasons) or "Matched local vetted location registry"


def resolve_location_candidates(
    query: str,
    targets: dict[str, dict[str, Any]],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for location_id, target in targets.items():
        scored = _score_location(query, location_id, target)
        if not scored:
            continue
        confidence, reason = scored
        bbox = [float(value) for value in target["bbox"]]
        center = [float(value) for value in target["center"]]
        candidates.append({
            "id": f"local_registry:{location_id}",
            "location_id": location_id,
            "query": query,
            "label": target["label"],
            "provider": "local_registry",
            "feature_type": target.get("place_type") or target.get("location_type") or "map context",
            "center": center,
            "bbox": bbox,
            "confidence": confidence,
            "reason": reason,
            "preview_tiles": build_preview_tiles(bbox),
        })

    candidates.sort(key=lambda item: (-float(item["confidence"]), str(item["label"])))
    return candidates[: max(1, min(limit, 10))]
