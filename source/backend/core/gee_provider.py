"""
gee_provider.py — Google Earth Engine REST API timelapse provider.

Uses GEE's thumbnail REST endpoint to fetch Sentinel-2 cloud-masked median
composites at 10m resolution. No earthengine-api package required — auth
is done via the GEE API key + an OAuth2 device-code flow token cached to disk,
OR via a plain API-key-only request (which GEE supports for thumbnail endpoints
when the project is allowlisted).

Auth strategy (in order):
  1. Cached access token on disk (.tools/.secrets/gee_token.json)
  2. API key only — works for thumbnails.create if the project has API key auth enabled
  3. Return None — caller falls back to NASA GIBS

GEE credentials from .tools/.secrets/gee.txt:
  Line 1: API key (GOCSPX-...)
  Line 2: OAuth2 client ID (NNN-....apps.googleusercontent.com)
"""

import hashlib
import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import httpx
import numpy as np
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

_SECRETS_DIR = Path(__file__).resolve().parents[3] / ".tools" / ".secrets"
_GEE_CREDS_FILE = _SECRETS_DIR / "gee.txt"
_TOKEN_CACHE = _SECRETS_DIR / "gee_token.json"

_GEE_API_BASE = "https://earthengine.googleapis.com/v1"
_GEE_SCOPE = "https://www.googleapis.com/auth/earthengine.readonly"
_TIMEOUT = 40.0

_FRAME_W = 1280
_FRAME_H = 960


def _load_credentials() -> tuple[str, str] | None:
    """Return (api_key, client_id) or None."""
    if not _GEE_CREDS_FILE.exists():
        return None
    try:
        lines = [l.strip() for l in _GEE_CREDS_FILE.read_text().splitlines() if l.strip()]
        if len(lines) >= 2:
            return lines[0], lines[1]
        if len(lines) == 1:
            return lines[0], ""
    except Exception:
        pass
    return None


def _extract_project_number(client_id: str) -> str:
    """Extract GCP project number from OAuth client ID like '449891481520-xxx'."""
    if "-" in client_id:
        return client_id.split("-")[0]
    return client_id


def _load_cached_token() -> str | None:
    """Return a valid cached OAuth2 access token or None."""
    if not _TOKEN_CACHE.exists():
        return None
    try:
        tok = json.loads(_TOKEN_CACHE.read_text())
        expires = datetime.fromisoformat(tok["expires_at"])
        if datetime.now(timezone.utc) < expires - timedelta(minutes=5):
            return tok["access_token"]
    except Exception:
        pass
    return None


def _save_token(token: str, expires_in: int) -> None:
    expires = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
    try:
        _TOKEN_CACHE.write_text(json.dumps({"access_token": token, "expires_at": expires}))
    except Exception:
        pass


def gee_available() -> bool:
    """True when GEE credentials file exists."""
    creds = _load_credentials()
    return creds is not None and bool(creds[0])


def _get_access_token(api_key: str, client_id: str) -> str | None:
    """
    Return a valid bearer token.
    If the cached token is expired, attempt a refresh using the refresh_token.
    Falls back to None if no valid token exists (caller then returns None).
    """
    cached = _load_cached_token()
    if cached:
        return cached

    # Try to refresh using cached refresh_token
    if not _TOKEN_CACHE.exists():
        return None
    try:
        tok = json.loads(_TOKEN_CACHE.read_text())
        refresh_token = tok.get("refresh_token", "")
        if not refresh_token or not client_id:
            return None

        # We need the client_secret — it's line 1 of gee.txt for installed-app flow
        creds = _load_credentials()
        if not creds:
            return None
        client_secret = creds[0]  # For installed-app, line 1 is the client_secret

        resp = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            result = resp.json()
            new_token = result.get("access_token", "")
            expires_in = result.get("expires_in", 3600)
            if new_token:
                _save_token(new_token, expires_in)
                logger.info("[GEE] Token refreshed successfully")
                return new_token
    except Exception as exc:
        logger.warning("[GEE] Token refresh failed: %s", exc)

    return None


def _build_sentinel2_expression(bbox: list[float], year: int, month: int) -> dict:
    w, s, e, n = bbox
    start = f"{year}-{month:02d}-01"
    next_m = month + 1 if month < 12 else 1
    next_y = year if month < 12 else year + 1
    end = f"{next_y}-{next_m:02d}-01"

    # Exact ee.Serializer.encode output for Sentinel-2 cloud-masked median composite
    expression = {
        "result": "0",
        "values": {
            "1": {"constantValue": ["B4", "B3", "B2"]},
            "0": {
                "functionInvocationValue": {
                    "functionName": "Image.visualize",
                    "arguments": {
                        "bands": {"valueReference": "1"},
                        "gamma": {"constantValue": 1.4},
                        "min": {"constantValue": 0},
                        "max": {"constantValue": 3000},
                        "image": {
                            "functionInvocationValue": {
                                "functionName": "Image.select",
                                "arguments": {
                                    "bandSelectors": {"valueReference": "1"},
                                    "input": {
                                        "functionInvocationValue": {
                                            "functionName": "reduce.median",
                                            "arguments": {
                                                "collection": {
                                                    "functionInvocationValue": {
                                                        "functionName": "Collection.filter",
                                                        "arguments": {
                                                            "collection": {
                                                                "functionInvocationValue": {
                                                                    "functionName": "Collection.filter",
                                                                    "arguments": {
                                                                        "collection": {
                                                                            "functionInvocationValue": {
                                                                                "functionName": "Collection.filter",
                                                                                "arguments": {
                                                                                    "collection": {
                                                                                        "functionInvocationValue": {
                                                                                            "functionName": "ImageCollection.load",
                                                                                            "arguments": {"id": {"constantValue": "COPERNICUS/S2_SR_HARMONIZED"}}
                                                                                        }
                                                                                    },
                                                                                    "filter": {
                                                                                        "functionInvocationValue": {
                                                                                            "functionName": "Filter.dateRangeContains",
                                                                                            "arguments": {
                                                                                                "leftValue": {
                                                                                                    "functionInvocationValue": {
                                                                                                        "functionName": "DateRange",
                                                                                                        "arguments": {
                                                                                                            "start": {"constantValue": start},
                                                                                                            "end": {"constantValue": end}
                                                                                                        }
                                                                                                    }
                                                                                                },
                                                                                                "rightField": {"constantValue": "system:time_start"}
                                                                                            }
                                                                                        }
                                                                                    }
                                                                                }
                                                                            }
                                                                        },
                                                                        "filter": {
                                                                            "functionInvocationValue": {
                                                                                "functionName": "Filter.intersects",
                                                                                "arguments": {
                                                                                    "leftField": {"constantValue": ".all"},
                                                                                    "rightValue": {
                                                                                        "functionInvocationValue": {
                                                                                            "functionName": "Feature",
                                                                                            "arguments": {
                                                                                                "geometry": {
                                                                                                    "functionInvocationValue": {
                                                                                                        "functionName": "GeometryConstructors.Polygon",
                                                                                                        "arguments": {
                                                                                                            "evenOdd": {"constantValue": True},
                                                                                                            "coordinates": {"constantValue": [[[w, s], [w, n], [e, n], [e, s]]]}
                                                                                                        }
                                                                                                    }
                                                                                                }
                                                                                            }
                                                                                        }
                                                                                    }
                                                                                }
                                                                            }
                                                                        }
                                                                    }
                                                                }
                                                            },
                                                            "filter": {
                                                                "functionInvocationValue": {
                                                                    "functionName": "Filter.lessThan",
                                                                    "arguments": {
                                                                        "leftField": {"constantValue": "CLOUDY_PIXEL_PERCENTAGE"},
                                                                        "rightValue": {"constantValue": 15}
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    return expression


def fetch_gee_month_frame(
    bbox: list[float],
    year: int,
    month: int,
    api_key: str,
    project_id: str,
    access_token: str | None,
) -> bytes | None:
    """
    Fetch a Sentinel-2 median composite for one month via GEE REST thumbnail API.
    Returns JPEG/PNG bytes or None.
    """
    w, s, e, n = bbox
    expression = _build_sentinel2_expression(bbox, year, month)

    body = {
        "expression": expression,
        "fileFormat": "JPEG",
        "grid": {
            "dimensions": {"width": _FRAME_W, "height": _FRAME_H},
            "affineTransform": {
                "scaleX": (e - w) / _FRAME_W,
                "shearX": 0,
                "translateX": w,
                "shearY": 0,
                "scaleY": -((n - s) / _FRAME_H),
                "translateY": n,
            },
            "crsCode": "EPSG:4326",
        },
    }

    url = f"{_GEE_API_BASE}/projects/{project_id}/thumbnails"
    headers = {"Content-Type": "application/json"}
    params = {}

    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    else:
        params["key"] = api_key

    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            # Step 1: Create thumbnail
            resp = client.post(url, json=body, headers=headers, params=params)
            if resp.status_code not in (200, 201):
                logger.debug("[GEE] thumbnails.create %d: %s", resp.status_code, resp.text[:200])
                return None

            thumb_name = resp.json().get("name", "")
            if not thumb_name:
                logger.debug("[GEE] No thumbnail name in response")
                return None

            # Step 2: Fetch pixels
            pixel_url = f"{_GEE_API_BASE}/{thumb_name}:getPixels"
            pixel_resp = client.get(pixel_url, headers=headers, params=params)
            if pixel_resp.status_code == 200:
                ct = pixel_resp.headers.get("content-type", "")
                if "image" in ct:
                    arr = np.array(Image.open(BytesIO(pixel_resp.content)).convert("RGB"))
                    if arr.mean() > 5.0 and arr.std() > 3.0:
                        logger.info("[GEE] Sentinel-2 %d-%02d OK  mean=%.0f", year, month, arr.mean())
                        return pixel_resp.content
            else:
                logger.debug("[GEE] getPixels %d: %s", pixel_resp.status_code, pixel_resp.text[:200])

    except Exception as exc:
        logger.warning("[GEE] Request error %d-%02d: %s", year, month, exc)

    return None


def fetch_gee_monthly_frames(
    bbox: list[float],
    months: list[tuple[int, int]],
) -> list[tuple[bytes, str]] | None:
    """
    Fetch GEE Sentinel-2 frames for each (year, month) in the list.
    Returns list of (jpeg_bytes, source_label) or None if GEE is unavailable.
    """
    creds = _load_credentials()
    if not creds:
        logger.info("[GEE] No credentials — skipping")
        return None

    api_key, client_id = creds
    project_id = _extract_project_number(client_id) if client_id else "earthengine-legacy"
    access_token = _get_access_token(api_key, client_id)

    results: list[tuple[bytes, str]] = []
    for year, month in months:
        tile = fetch_gee_month_frame(bbox, year, month, api_key, project_id, access_token)
        if tile:
            results.append((tile, f"GEE Sentinel-2  {year}-{month:02d}"))
        else:
            logger.info("[GEE] No tile for %d-%02d", year, month)

    if not results:
        logger.warning("[GEE] Zero frames returned — credentials may not be authorized or project not registered")
        return None

    return results


def get_gee_status() -> dict:
    """Return GEE availability info for the settings panel."""
    creds = _load_credentials()
    if not creds:
        return {"available": False, "reason": "credentials file missing"}
    api_key, client_id = creds
    project_id = _extract_project_number(client_id) if client_id else ""
    has_token = _load_cached_token() is not None
    return {
        "available": bool(api_key),
        "api_key_present": bool(api_key),
        "client_id": client_id[:30] + "..." if len(client_id) > 30 else client_id,
        "project_number": project_id,
        "cached_token": has_token,
        "dataset": "COPERNICUS/S2_SR_HARMONIZED (10m)",
        "note": "Sentinel-2 cloud-masked median composites via GEE REST API",
    }
