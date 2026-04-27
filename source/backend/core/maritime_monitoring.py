"""Orbit-native maritime monitoring and investigation helpers.

This module provides STAC scene discovery, temporal date deduplication, and
cardinal-direction investigation planning. It stays deterministic and
dependency-light so the core app can run without separate app scaffolding or
heavy geospatial/VLM dependencies.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import math
import os
from typing import Any

import httpx

from core.temporal_use_cases import classify_temporal_use_case


STAC_API_URL = os.environ.get("ORBIT_STAC_API_URL", "https://earth-search.aws.element84.com/v1")
STAC_COLLECTION = os.environ.get("ORBIT_STAC_COLLECTION", "sentinel-2-l2a")
STAC_PROVIDER_ID = "element84_earth_search"
MARITIME_REPORT_VERSION = "orbit_maritime_monitoring_v1"
EXPLORATION_DIRECTIONS: tuple[str, ...] = ("N", "E", "S", "W")
_BEARING_DEG = {"N": 0.0, "E": 90.0, "S": 180.0, "W": 270.0}


def normalize_maritime_timestamp(value: str | None = None) -> str:
    """Return a YYYY-MM-DD timestamp string, defaulting to today's UTC date."""
    text = str(value or "").strip()
    if not text:
        return datetime.now(timezone.utc).date().isoformat()
    try:
        normalized = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        try:
            parsed_date = date.fromisoformat(text[:10])
        except ValueError:
            raise ValueError("timestamp must be an ISO date or datetime") from exc
        return parsed_date.isoformat()
    return parsed.date().isoformat()


def bbox_from_point(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    """Convert a center point plus radius in km into a WGS84 bbox."""
    if not -90 <= lat <= 90:
        raise ValueError("lat must be between -90 and 90")
    if not -180 <= lon <= 180:
        raise ValueError("lon must be between -180 and 180")
    if radius_km <= 0:
        raise ValueError("radius_km must be positive")

    km_per_deg_lat = 111.32
    km_per_deg_lon = max(0.001, 111.32 * math.cos(math.radians(lat)))
    dlat = radius_km / km_per_deg_lat
    dlon = radius_km / km_per_deg_lon

    west = max(-180.0, lon - dlon)
    south = max(-90.0, lat - dlat)
    east = min(180.0, lon + dlon)
    north = min(90.0, lat + dlat)
    return (round(west, 6), round(south, 6), round(east, 6), round(north, 6))


def offset_point(lat: float, lon: float, direction: str, distance_km: float) -> tuple[float, float]:
    """Return a lat/lon offset from an anchor in a cardinal direction."""
    direction_key = direction.upper().strip()
    bearing = _BEARING_DEG.get(direction_key)
    if bearing is None:
        raise ValueError(f"direction must be one of {', '.join(EXPLORATION_DIRECTIONS)}")
    if distance_km <= 0:
        raise ValueError("distance_km must be positive")

    radius_earth_km = 6371.0
    angular_distance = distance_km / radius_earth_km
    bearing_rad = math.radians(bearing)
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)

    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular_distance)
        + math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing_rad)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing_rad) * math.sin(angular_distance) * math.cos(lat1),
        math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2),
    )

    lon_deg = ((math.degrees(lon2) + 180) % 360) - 180
    return (round(math.degrees(lat2), 6), round(lon_deg, 6))


def _date_range(timestamp: str, lookback_days: int) -> str:
    end_date = date.fromisoformat(normalize_maritime_timestamp(timestamp))
    start_date = end_date - timedelta(days=max(1, lookback_days))
    return f"{start_date.isoformat()}/{end_date.isoformat()}"


def _feature_center(item: dict[str, Any], fallback_lat: float, fallback_lon: float) -> tuple[float, float]:
    bbox = item.get("bbox")
    if isinstance(bbox, list) and len(bbox) == 4:
        west, south, east, north = [float(value) for value in bbox]
        return ((south + north) / 2.0, (west + east) / 2.0)
    return (fallback_lat, fallback_lon)


def _spatial_distance_key(item: dict[str, Any], lat: float, lon: float) -> tuple[float, float]:
    center_lat, center_lon = _feature_center(item, lat, lon)
    distance = abs(center_lat - lat) + abs(center_lon - lon)
    cloud = float((item.get("properties") or {}).get("eo:cloud_cover", 100.0) or 100.0)
    return (distance, cloud)


def _item_date(item: dict[str, Any]) -> str:
    props = item.get("properties") or {}
    raw = item.get("datetime") or props.get("datetime") or ""
    return str(raw)[:10]


def _asset_href(item: dict[str, Any]) -> str:
    assets = item.get("assets") if isinstance(item.get("assets"), dict) else {}
    for key in ("visual", "visual_10m", "rendered_preview", "thumbnail"):
        asset = assets.get(key)
        if isinstance(asset, dict) and asset.get("href"):
            return str(asset["href"])
    return ""


def normalize_stac_item(item: dict[str, Any], *, lat: float, lon: float) -> dict[str, Any]:
    """Normalize a STAC item into Orbit's compact maritime evidence shape."""
    props = item.get("properties") or {}
    center_lat, center_lon = _feature_center(item, lat, lon)
    return {
        "item_id": str(item.get("id", "")),
        "date": _item_date(item),
        "cloud_cover": props.get("eo:cloud_cover"),
        "mgrs_tile": props.get("s2:mgrs_tile") or props.get("mgrs_tile") or "",
        "bbox": item.get("bbox") or [],
        "center": {"lat": round(center_lat, 6), "lon": round(center_lon, 6)},
        "visual_href": _asset_href(item),
    }


def deduplicate_stac_items(items: list[dict[str, Any]], *, max_items: int, lat: float, lon: float) -> list[dict[str, Any]]:
    """Keep one STAC item per date, preferring spatial consistency then cloud cover."""
    by_date: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        date_key = _item_date(item)
        if date_key:
            by_date.setdefault(date_key, []).append(item)

    best_by_date = {
        date_key: min(candidates, key=lambda item: _spatial_distance_key(item, lat, lon))
        for date_key, candidates in by_date.items()
    }
    selected_dates = sorted(best_by_date.keys(), reverse=True)[:max_items]
    return [
        normalize_stac_item(best_by_date[date_key], lat=lat, lon=lon)
        for date_key in selected_dates
    ]


def search_sentinel2_stac(
    *,
    lat: float,
    lon: float,
    timestamp: str,
    radius_km: float = 10.0,
    max_items: int = 4,
    max_cloud_cover: int = 30,
    lookback_days: int = 90,
    timeout_seconds: float = 12.0,
) -> dict[str, Any]:
    """Search Element84 Earth Search for Sentinel-2 scenes without downloading COGs."""
    if os.environ.get("DISABLE_EXTERNAL_APIS", "false").lower() == "true":
        return {
            "provider": STAC_PROVIDER_ID,
            "collection": STAC_COLLECTION,
            "disabled": True,
            "items": [],
            "note": "External APIs disabled; STAC search skipped.",
        }

    bbox = bbox_from_point(lat, lon, radius_km)
    west, south, east, north = bbox
    geometry = {
        "type": "Polygon",
        "coordinates": [[
            [west, south],
            [east, south],
            [east, north],
            [west, north],
            [west, south],
        ]],
    }
    payload = {
        "collections": [STAC_COLLECTION],
        "intersects": geometry,
        "datetime": _date_range(timestamp, lookback_days),
        "query": {"eo:cloud_cover": {"lte": max_cloud_cover}},
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
        "limit": max(1, max_items * 6),
    }

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(f"{STAC_API_URL.rstrip('/')}/search", json=payload)
        response.raise_for_status()
        raw = response.json()

    features = raw.get("features") if isinstance(raw, dict) else []
    if not isinstance(features, list):
        features = []

    return {
        "provider": STAC_PROVIDER_ID,
        "collection": STAC_COLLECTION,
        "disabled": False,
        "bbox": list(bbox),
        "items": deduplicate_stac_items(features, max_items=max_items, lat=lat, lon=lon),
    }


def build_cardinal_investigation_plan(
    *,
    lat: float,
    lon: float,
    timestamp: str,
    anomaly_description: str = "",
    distance_km: float = 10.0,
    radius_km: float = 5.0,
    max_temporal_images: int = 4,
) -> list[dict[str, Any]]:
    """Build deterministic cardinal exploration targets around a maritime anomaly."""
    plan: list[dict[str, Any]] = []
    for direction in EXPLORATION_DIRECTIONS:
        target_lat, target_lon = offset_point(lat, lon, direction, distance_km)
        target_bbox = bbox_from_point(target_lat, target_lon, radius_km)
        plan.append(
            {
                "direction": direction,
                "bearing_deg": _BEARING_DEG[direction],
                "center": {"lat": target_lat, "lon": target_lon},
                "bbox": list(target_bbox),
                "distance_km": distance_km,
                "radius_km": radius_km,
                "max_temporal_images": max(1, max_temporal_images),
                "recommended_action": "explore_direction",
                "analysis_questions": [
                    "Is the area water, canal, port, coastline, anchorage, or open ocean?",
                    "How many vessel-sized bright targets, wakes, queues, slicks, or formations are visible?",
                    "Does the evidence plausibly explain or correlate with the anchor anomaly?",
                ],
                "context": {
                    "timestamp": timestamp,
                    "anomaly_description": anomaly_description,
                },
            }
        )
    return plan


def build_maritime_monitor_report(
    *,
    lat: float,
    lon: float,
    timestamp: str | None = None,
    task_text: str = "",
    anomaly_description: str = "",
    include_stac: bool = False,
    radius_km: float = 10.0,
    distance_km: float = 10.0,
    max_items: int = 4,
    max_cloud_cover: int = 30,
) -> dict[str, Any]:
    """Build an Orbit-native maritime monitoring report and investigation plan."""
    normalized_timestamp = normalize_maritime_timestamp(timestamp)
    mission_text = task_text.strip() or (
        "Monitor maritime traffic, vessel wakes, port congestion, canal blockage, "
        "oil slicks, and AIS-dark vessel candidates."
    )
    use_case = classify_temporal_use_case(
        {
            "task_text": mission_text,
            "reason_codes": ["vessel_presence", "ship_wake", "maritime_anomaly"],
            "target_category": "maritime",
        },
        "maritime_activity",
    )

    stac_payload: dict[str, Any] = {
        "provider": STAC_PROVIDER_ID,
        "collection": STAC_COLLECTION,
        "disabled": not include_stac,
        "items": [],
        "note": "Set include_stac=true to query Element84 Sentinel-2 metadata.",
    }
    if include_stac:
        try:
            stac_payload = search_sentinel2_stac(
                lat=lat,
                lon=lon,
                timestamp=normalized_timestamp,
                radius_km=radius_km,
                max_items=max_items,
                max_cloud_cover=max_cloud_cover,
            )
        except Exception as exc:
            stac_payload = {
                "provider": STAC_PROVIDER_ID,
                "collection": STAC_COLLECTION,
                "disabled": False,
                "items": [],
                "error": f"{type(exc).__name__}: {exc}",
            }

    return {
        "mode": MARITIME_REPORT_VERSION,
        "target": {
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "timestamp": normalized_timestamp,
            "anchor_bbox": list(bbox_from_point(lat, lon, radius_km)),
        },
        "use_case": use_case,
        "monitor": {
            "objective": mission_text,
            "anomaly_description": anomaly_description,
            "signals": [
                "vessel_presence",
                "ship_wake",
                "port_activity_change",
                "ais_mismatch",
                "oil_slick",
                "channel_blockage",
                "traffic_congestion",
            ],
            "quality_gates": [
                "prefer distinct Sentinel-2 dates over repeated same-day overlapping tiles",
                "separate cloud, haze, sunglint, and shoreline artifacts from vessel evidence",
                "treat Sentinel-2 10 m optical detections as review cues, not AIS truth",
                "preserve asset URLs and bbox metadata for dataset export and replay",
            ],
        },
        "stac": stac_payload,
        "investigation": {
            "strategy": "Explore or skip each cardinal direction, then submit one primary explanation.",
            "directions": build_cardinal_investigation_plan(
                lat=lat,
                lon=lon,
                timestamp=normalized_timestamp,
                anomaly_description=anomaly_description,
                distance_km=distance_km,
                radius_km=max(0.1, radius_km / 2.0),
                max_temporal_images=max_items,
            ),
            "tool_contract": [
                "explore_direction(direction, distance_km, radius_km, max_temporal_images)",
                "skip_direction(direction, reason)",
                "analyze_image(asset_href_or_local_path, question)",
                "submit_finding(title, description, evidence_images, confidence)",
            ],
        },
        "training_export": {
            "format": "orbit_temporal_sft_v1",
            "recommended_labels": ["review", "alert", "prune"],
            "recommended_assets": ["visual_href", "bbox", "sample.json", "training.jsonl row"],
            "handoff": "Use scripts/export_orbit_dataset.py after alerts or replay evidence are persisted.",
        },
        "orbit_integration": {
            "external_vlm_api_required": False,
            "separate_streamlit_app_required": False,
            "deterministic_offline_plan_available": True,
            "fits_existing_mission_replay_and_training_export": True,
        },
    }
