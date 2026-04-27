"""
timelapse.py — Multi-provider timelapse generator.

Provider priority (auto-selected, most accurate first):
  1. GEE (Google Earth Engine) — Sentinel-2 SR 10m cloud-masked median composites
  2. NASA GIBS HLS — Landsat/Sentinel-2 30m via WMS (no auth)
  3. NASA GIBS MODIS — 250m daily global (guaranteed, no auth, lowest quality)

Each provider returns one frame per calendar month.
All frames are 1280x960, with a burned-in bottom HUD (date + source).
Seeded WebM cache is checked before any network call and written after live fetches.
"""

import base64
import hashlib
import json
import logging
import os
import tempfile
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path

import httpx
import imageio.v3 as iio
import numpy as np
from PIL import Image, ImageDraw
from core.grid import normalize_bbox

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GIBS_WMS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
_GIBS_MODIS_LAYER = "MODIS_Terra_CorrectedReflectance_TrueColor"
_GIBS_HLS_LAYERS = [
    "HLS_S30_Nadir_BRDF_Adjusted_Reflectance",  # Sentinel-2, 5-day revisit, 30m
    "HLS_L30_Nadir_BRDF_Adjusted_Reflectance",  # Landsat 8/9, 16-day revisit, 30m
]

_HLS_DAY_CANDIDATES = [10, 15, 20, 5, 25, 1, 28]
_FRAME_W = 1280
_FRAME_H = 960
_TIMEOUT = 30.0

_SEEDED_DIR = Path(__file__).resolve().parent.parent / "assets" / "seeded_data"

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _chunk_sig(bbox: list[float]) -> str:
    rounded = [round(b, 3) for b in bbox]
    return hashlib.md5(str(rounded).encode()).hexdigest()[:8]


def _limit_months(months: list[tuple[int, int]], steps: int | None) -> list[tuple[int, int]]:
    if steps is None or len(months) <= steps:
        return months

    target = max(2, min(int(steps), 24))
    if len(months) <= target:
        return months

    span = len(months) - 1
    indices = [round(index * span / (target - 1)) for index in range(target)]
    limited: list[tuple[int, int]] = []
    seen: set[int] = set()
    for index in indices:
        if index in seen:
            continue
        seen.add(index)
        limited.append(months[index])
    return limited


def _month_range(start_date: str, end_date: str, steps: int | None = None) -> list[tuple[int, int]]:
    """
    Build a list of (year, month) tuples from start_date to end_date.
    Inputs accepted as 'YYYY-MM-DD', 'YYYY-MM', or 'YYYY'.
    Output capped at today and at 24 months (sub-sampled if wider).
    """
    def _parse(s: str) -> tuple[int, int]:
        parts = s.split("-")
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        date(year, month, 1)
        return year, month

    try:
        sy, sm = _parse(start_date)
        ey, em = _parse(end_date)
    except Exception as exc:
        logger.debug("[TIMELAPSE] Invalid date range %s -> %s: %s", start_date, end_date, exc)
        sy, sm, ey, em = 2024, 4, 2026, 4

    today = date.today()
    if ey > today.year or (ey == today.year and em > today.month):
        ey, em = today.year, today.month

    if (sy, sm) > (ey, em):
        return []

    months = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        months.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1

    return _limit_months(months, steps if steps is not None else 24)


def _burn_hud(img: Image.Image, iso_label: str, source: str) -> Image.Image:
    """Burn a bottom-bar HUD with date and data source onto the image."""
    draw = ImageDraw.Draw(img)
    bar_h = 30
    draw.rectangle([(0, img.height - bar_h), (img.width, img.height)], fill=(0, 0, 0))
    draw.text((8,  img.height - bar_h + 7), iso_label, fill=(255, 255, 255))
    draw.text((120, img.height - bar_h + 7), source[:80], fill=(160, 210, 160))
    return img


def _decode_and_label(raw: bytes, iso_label: str, source: str) -> np.ndarray:
    img = Image.open(BytesIO(raw)).convert("RGB").resize((_FRAME_W, _FRAME_H), Image.LANCZOS)
    img = _burn_hud(img, iso_label, source)
    return np.array(img, dtype=np.uint8)


# ---------------------------------------------------------------------------
# Provider 1: GEE (Sentinel-2 SR, 10m, cloud-masked median)
# ---------------------------------------------------------------------------

def _fetch_gee_frames(
    bbox: list[float],
    months: list[tuple[int, int]],
) -> list[tuple[np.ndarray, str]] | None:
    """
    Attempt to fetch one Sentinel-2 composite per month from GEE REST API.
    Returns frame list or None if GEE is unavailable/unauthenticated.
    """
    try:
        from core.gee_provider import fetch_gee_monthly_frames, gee_available
    except ImportError:
        return None

    if not gee_available():
        return None

    raw_frames = fetch_gee_monthly_frames(bbox, months)
    if not raw_frames:
        return None

    frames = []
    for raw, source in raw_frames:
        iso = source.split()[-1] if source else "unknown"
        frame = _decode_and_label(raw, iso, source)
        frames.append((frame, iso))

    logger.info("[TIMELAPSE] GEE: %d Sentinel-2 frames", len(frames))
    return frames if frames else None


# ---------------------------------------------------------------------------
# Provider 2: NASA GIBS HLS (30m) + MODIS (250m) fallback
# ---------------------------------------------------------------------------

def _fetch_gibs_month(
    year: int,
    month: int,
    bbox: list[float],
    client: httpx.Client,
) -> tuple[bytes | None, str]:
    w, s, e, n = bbox

    # HLS: try candidate days for a cloud-free 30m frame
    for day in _HLS_DAY_CANDIDATES:
        try:
            date(year, month, day)
        except ValueError:
            continue
        iso = f"{year}-{month:02d}-{day:02d}"
        for layer in _GIBS_HLS_LAYERS:
            short = "S30" if "S30" in layer else "L30"
            params = {
                "SERVICE": "WMS", "REQUEST": "GetMap", "VERSION": "1.3.0",
                "LAYERS": layer, "FORMAT": "image/jpeg", "CRS": "EPSG:4326",
                "BBOX": f"{s},{w},{n},{e}", "WIDTH": _FRAME_W, "HEIGHT": _FRAME_H,
                "TIME": iso,
            }
            try:
                resp = client.get(_GIBS_WMS, params=params)
                if resp.status_code == 200 and "image/jpeg" in resp.headers.get("content-type", ""):
                    arr = np.array(Image.open(BytesIO(resp.content)).convert("RGB"))
                    if arr.mean() > 8.0 and arr.std() > 4.0:
                        logger.info("[TIMELAPSE] GIBS HLS-%s %s  mean=%.0f", short, iso, arr.mean())
                        return resp.content, f"HLS {short}  {iso}"
            except Exception as exc:
                logger.debug("[TIMELAPSE] GIBS HLS-%s request failed for %s: %s", short, iso, exc)

    # MODIS fallback: 250m, daily global coverage
    for day in [15, 10, 20, 1]:
        try:
            date(year, month, day)
        except ValueError:
            continue
        iso = f"{year}-{month:02d}-{day:02d}"
        params = {
            "SERVICE": "WMS", "REQUEST": "GetMap", "VERSION": "1.3.0",
            "LAYERS": _GIBS_MODIS_LAYER, "FORMAT": "image/jpeg", "CRS": "EPSG:4326",
            "BBOX": f"{s},{w},{n},{e}", "WIDTH": _FRAME_W, "HEIGHT": _FRAME_H,
            "TIME": iso,
        }
        try:
            resp = client.get(_GIBS_WMS, params=params)
            if resp.status_code == 200 and "image/jpeg" in resp.headers.get("content-type", ""):
                arr = np.array(Image.open(BytesIO(resp.content)).convert("RGB"))
                if arr.mean() > 5.0:
                    logger.info("[TIMELAPSE] GIBS MODIS %s  mean=%.0f", iso, arr.mean())
                    return resp.content, f"MODIS  {iso}"
        except Exception as exc:
            logger.debug("[TIMELAPSE] GIBS MODIS request failed for %s: %s", iso, exc)

    return None, ""


def _fetch_gibs_frames(
    bbox: list[float],
    months: list[tuple[int, int]],
) -> list[tuple[np.ndarray, str]]:
    frames = []
    with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
        for year, month in months:
            raw, source = _fetch_gibs_month(year, month, bbox, client)
            if raw:
                iso = f"{year}-{month:02d}"
                frame = _decode_and_label(raw, iso, source)
                frames.append((frame, iso))
            else:
                logger.warning("[TIMELAPSE] GIBS: no tile for %d-%02d", year, month)
    return frames


# ---------------------------------------------------------------------------
# WebM encoding + cache
# ---------------------------------------------------------------------------

def _encode_webm(frames: list[np.ndarray]) -> bytes:
    fd, path = tempfile.mkstemp(suffix=".webm")
    os.close(fd)
    try:
        iio.imwrite(path, frames, plugin="pyav", fps=3, codec="libvpx-vp9")
        return Path(path).read_bytes()
    finally:
        if os.path.exists(path):
            os.remove(path)


def _write_cache(sig: str, webm: bytes, meta: dict) -> None:
    _SEEDED_DIR.mkdir(parents=True, exist_ok=True)
    (_SEEDED_DIR / f"nasa_{sig}.webm").write_bytes(webm)
    (_SEEDED_DIR / f"nasa_{sig}_meta.json").write_text(json.dumps(meta, indent=2))
    logger.info("[TIMELAPSE] Cached %s (%d KB)", sig, len(webm) // 1024)


def _read_cache(sig: str) -> dict | None:
    # Prefer high-quality Sentinel Hub cache
    sh_webm_path = _SEEDED_DIR / f"sh_{sig}.webm"
    sh_meta_path = _SEEDED_DIR / f"sh_{sig}_meta.json"
    
    nasa_webm_path = _SEEDED_DIR / f"nasa_{sig}.webm"
    nasa_meta_path = _SEEDED_DIR / f"nasa_{sig}_meta.json"
    
    if sh_webm_path.exists():
        webm_path = sh_webm_path
        meta_path = sh_meta_path
        cache_family = "sentinelhub"
    elif nasa_webm_path.exists():
        webm_path = nasa_webm_path
        meta_path = nasa_meta_path
        cache_family = "nasa_gibs"
    else:
        return None

    frames_count = 4
    meta: dict = {}
    try:
        meta = json.loads(meta_path.read_text())
        frames_count = meta.get("frames_count", 4)
    except Exception as exc:
        logger.debug("[TIMELAPSE] Invalid cache metadata for %s: %s", sig, exc)
    data_b64 = base64.b64encode(webm_path.read_bytes()).decode("ascii")
    return {
        "video_b64": f"data:video/webm;base64,{data_b64}",
        "frames_count": frames_count,
        "format": "webm",
        "source": "seeded_cache",
        "provider": meta.get("provider", cache_family),
        "provenance": {
            "kind": "seeded_cache",
            "label": "Seeded local WebM cache",
            "provider": meta.get("provider", cache_family),
            "cache_family": cache_family,
            "cache_key": sig,
        },
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_provider_status() -> dict:
    """Return status of all timelapse providers for the settings panel."""
    try:
        from core.gee_provider import get_gee_status
        gee = get_gee_status()
    except Exception as exc:
        logger.debug("[TIMELAPSE] GEE status unavailable: %s", exc)
        gee = {"available": False, "reason": "gee_provider not loaded"}
    return {
        "gee": gee,
        "nasa_gibs": {
            "available": True,
            "layers": ["HLS S30 (30m)", "HLS L30 (30m)", "MODIS (250m)"],
            "note": "No auth required. MODIS: guaranteed daily global coverage.",
        },
        "priority": ["gee", "nasa_gibs"],
    }


def generate_timelapse_frames(
    bbox: list[float],
    start_date: str,
    end_date: str,
    steps: int = 12,
    prefer_provider: str | None = None,
) -> dict:
    """
    Generate a WebM timelapse for the given bbox + date range.

    Args:
        bbox: [west, south, east, north] in EPSG:4326
        start_date: 'YYYY-MM-DD' or 'YYYY-MM'
        end_date: 'YYYY-MM-DD' or 'YYYY-MM'
        steps: target frame count; wider date windows are sampled down
        prefer_provider: 'gee' | 'nasa_gibs' | None (auto)

    Returns dict with video_b64, frames_count, format, source.
    """
    try:
        bbox = normalize_bbox(bbox)
    except ValueError as exc:
        return {"video_b64": "", "frames_count": 0, "format": "none",
                "error": f"Invalid bbox: {exc}",
                "provenance": {"kind": "unavailable", "label": "Invalid request"}}

    if os.environ.get("DISABLE_EXTERNAL_APIS", "false").lower() == "true":
        return {"video_b64": "", "frames_count": 0, "format": "none",
                "error": "External APIs disabled.",
                "provenance": {"kind": "unavailable", "label": "External APIs disabled"}}

    sig = _chunk_sig(bbox)

    # Serve from cache if available
    cached = _read_cache(sig)
    if cached:
        logger.info("[TIMELAPSE] Serving cache %s", sig)
        return cached

    months = _month_range(start_date, end_date, steps=steps)
    if not months:
        return {"video_b64": "", "frames_count": 0, "format": "none",
                "error": "No months in date range.",
                "provenance": {"kind": "unavailable", "label": "No monthly frame window"}}

    logger.info("[TIMELAPSE] Fetching %d months | %s → %s | bbox=%s",
                len(months), start_date, end_date, [round(b, 2) for b in bbox])

    frame_data: list[tuple[np.ndarray, str]] = []
    provider_used = "none"

    # Provider 1: GEE (unless explicitly skipped)
    if prefer_provider != "nasa_gibs":
        gee_frames = _fetch_gee_frames(bbox, months)
        if gee_frames and len(gee_frames) >= 2:
            frame_data = gee_frames
            provider_used = "gee"
            logger.info("[TIMELAPSE] Using GEE Sentinel-2 (%d frames)", len(frame_data))

    # Provider 2: NASA GIBS
    if not frame_data:
        logger.info("[TIMELAPSE] GEE unavailable — trying NASA GIBS")
        gibs_frames = _fetch_gibs_frames(bbox, months)
        if gibs_frames and len(gibs_frames) >= 2:
            frame_data = gibs_frames
            provider_used = "nasa_gibs"
            logger.info("[TIMELAPSE] Using NASA GIBS (%d frames)", len(frame_data))

    if len(frame_data) < 2:
        return {"video_b64": "", "frames_count": 0, "format": "none",
                "error": f"Insufficient imagery ({len(frame_data)} frames) for this area and date range.",
                "provenance": {"kind": "unavailable", "label": "Insufficient imagery"}}

    try:
        webm = _encode_webm([arr for arr, _ in frame_data])
    except Exception as exc:
        logger.error("[TIMELAPSE] Encode error: %s", exc)
        return {"video_b64": "", "frames_count": 0, "format": "none",
                "error": f"Video encoding failed: {exc}",
                "provenance": {"kind": "unavailable", "label": "Video encoding failed"}}

    meta = {
        "chunk_signature": sig,
        "bbox": bbox,
        "start_date": start_date,
        "end_date": end_date,
        "frames_count": len(frame_data),
        "frame_dates": [iso for _, iso in frame_data],
        "provider": provider_used,
        "source": "NASA GIBS (HLS 30m / MODIS 250m)" if provider_used == "nasa_gibs"
                  else "GEE Sentinel-2 SR 10m cloud-masked",
        "cached_at": date.today().isoformat(),
    }
    _write_cache(sig, webm, meta)

    return {
        "video_b64": f"data:video/webm;base64,{base64.b64encode(webm).decode()}",
        "frames_count": len(frame_data),
        "format": "webm",
        "frame_dates": [iso for _, iso in frame_data],
        "provider": provider_used,
        "source": meta["source"],
        "provenance": {
            "kind": "live_fetch",
            "label": meta["source"],
            "provider": provider_used,
            "cache_key": sig,
        },
    }
