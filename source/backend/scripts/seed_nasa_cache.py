"""
seed_nasa_cache.py — Seeds a seeded_data WebM timelapse cache using NASA GIBS.

Uses the same fetch logic as timelapse.py: monthly cadence, HLS 30m → MODIS
250m fallback per month, 1024×768 resolution.

Fetches real Landsat/MODIS imagery from NASA GIBS (no auth required).
Stores WebM timelapses + rich training metadata to assets/seeded_data/.
Also writes observation records to assets/observation_store/ for agent reuse.

Known deforestation hotspot targets (--target shorthand):
    rondoniaWS  lat=-10.0  lon=-63.0   Rondônia western frontier
    rondoniaE   lat=-10.5  lon=-62.0   Rondônia eastern arc
    para        lat=-6.5   lon=-52.5   Pará soy/cattle frontier
    acre        lat=-9.0   lon=-70.5   Acre logging corridor
    matogrosso  lat=-12.5  lon=-52.5   Mato Grosso arc of deforestation

Usage:
    # Single cell at default hotspot
    python scripts/seed_nasa_cache.py

    # 3x3 grid around Rondônia
    python scripts/seed_nasa_cache.py --target rondoniaWS --grid 3

    # Custom location, 3x3 grid, specific years
    python scripts/seed_nasa_cache.py --lat -6.5 --lon -52.5 --grid 3

    # All 5 hotspots, 3x3 grid each
    python scripts/seed_nasa_cache.py --all-targets --grid 3
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import tempfile
from datetime import date
from io import BytesIO
from pathlib import Path

import httpx
import imageio.v3 as iio
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.inference import generate
from core.observation_store import save_observation

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# NASA GIBS WMS endpoint — no auth, global coverage
_GIBS_WMS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
_GIBS_MODIS_LAYER = "MODIS_Terra_CorrectedReflectance_TrueColor"
_GIBS_HLS_LAYERS = [
    "HLS_L30_Nadir_BRDF_Adjusted_Reflectance",
    "HLS_S30_Nadir_BRDF_Adjusted_Reflectance",
]

# Default date range: four years of monthly snapshots up to Jan 2026
_DEFAULT_START = "2022-01"
_DEFAULT_END   = "2026-01"

# Candidate days within a month to try for HLS (cloud-free bias)
_HLS_DAY_CANDIDATES = [10, 15, 20, 5, 25, 1, 28]

_FRAME_W = 1024
_FRAME_H = 768

# Known deforestation hotspots [lat, lon, display_name, region_note]
HOTSPOTS = {
    "rondoniaWS": (-10.0, -63.0, "Rondônia Western Frontier", "Historically severe cattle/soy clearing"),
    "rondoniaE":  (-10.5, -62.0, "Rondônia Eastern Arc",      "Active illegal logging corridor"),
    "para":       (-6.5,  -52.5, "Pará Frontier",              "Soy expansion and land grabbing"),
    "acre":       (-9.0,  -70.5, "Acre Logging Corridor",      "Old-growth selective logging"),
    "matogrosso": (-12.5, -52.5, "Mato Grosso Arc",            "Industrial-scale deforestation front"),
}


def get_chunk_signature(bbox: list[float]) -> str:
    rounded = [round(b, 3) for b in bbox]
    return hashlib.md5(str(rounded).encode()).hexdigest()[:8]


def _fetch_month_frame(
    year: int,
    month: int,
    bbox: list[float],
    client: httpx.Client,
) -> tuple[bytes | None, str]:
    """
    Fetch the best available frame for a given year-month.
    HLS 30m priority → MODIS 250m fallback.
    Returns (jpeg_bytes, source_label).
    """
    from datetime import date as _date
    w, s, e, n = bbox

    for day in _HLS_DAY_CANDIDATES:
        try:
            _date(year, month, day)
        except ValueError:
            continue
        iso = f"{year}-{month:02d}-{day:02d}"
        for layer in _GIBS_HLS_LAYERS:
            short = "S30" if "S30" in layer else "L30"
            params = {
                "SERVICE": "WMS",
                "REQUEST": "GetMap",
                "LAYERS": layer,
                "VERSION": "1.3.0",
                "FORMAT": "image/jpeg",
                "CRS": "EPSG:4326",
                "BBOX": f"{s},{w},{n},{e}",
                "WIDTH": _FRAME_W,
                "HEIGHT": _FRAME_H,
                "TIME": iso,
            }
            try:
                resp = client.get(_GIBS_WMS, params=params)
                if resp.status_code == 200 and "image/jpeg" in resp.headers.get("content-type", ""):
                    img = Image.open(BytesIO(resp.content)).convert("RGB")
                    arr = np.array(img)
                    if arr.mean() > 8.0 and arr.std() > 4.0:
                        logger.info(f"  [HLS-{short}] {iso}  mean={arr.mean():.0f}")
                        return resp.content, f"HLS {short}  {iso}"
            except Exception as exc:
                logger.debug("HLS %s fetch failed for %s: %s", short, iso, exc)

    # MODIS fallback
    logger.warning(f"  [MODIS fallback] {year}-{month:02d}")
    for day in [15, 10, 20, 1]:
        try:
            _date(year, month, day)
        except ValueError:
            continue
        iso = f"{year}-{month:02d}-{day:02d}"
        params = {
            "SERVICE": "WMS",
            "REQUEST": "GetMap",
            "LAYERS": _GIBS_MODIS_LAYER,
            "VERSION": "1.3.0",
            "FORMAT": "image/jpeg",
            "CRS": "EPSG:4326",
            "BBOX": f"{s},{w},{n},{e}",
            "WIDTH": _FRAME_W,
            "HEIGHT": _FRAME_H,
            "TIME": iso,
        }
        try:
            resp = client.get(_GIBS_WMS, params=params)
            if resp.status_code == 200 and "image/jpeg" in resp.headers.get("content-type", ""):
                arr = np.array(Image.open(BytesIO(resp.content)).convert("RGB"))
                if arr.mean() > 5.0:
                    logger.info(f"  [MODIS] {iso}  mean={arr.mean():.0f}")
                    return resp.content, f"MODIS  {iso}"
        except Exception as exc:
            logger.debug("MODIS fetch failed for %s: %s", iso, exc)

    return None, ""


def _month_range(start_ym: str, end_ym: str) -> list[tuple[int, int]]:
    """Return list of (year, month) from 'YYYY-MM' to 'YYYY-MM' inclusive."""
    from datetime import date as _date
    sy, sm = int(start_ym[:4]), int(start_ym[5:7])
    ey, em = int(end_ym[:4]), int(end_ym[5:7])
    today = _date.today()
    if ey > today.year or (ey == today.year and em > today.month):
        ey, em = today.year, today.month
    months = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    if len(months) > 48:
        step = len(months) / 48
        months = [months[int(i * step)] for i in range(48)]
    return months


def _build_frame(tile_bytes: bytes, iso_label: str, source: str) -> np.ndarray:
    """Decode JPEG, resize to standard HD dimensions, burn date + source HUD."""
    img = Image.open(BytesIO(tile_bytes)).convert("RGB").resize((_FRAME_W, _FRAME_H), Image.LANCZOS)
    draw = ImageDraw.Draw(img)
    bar_h = 28
    draw.rectangle([(0, _FRAME_H - bar_h), (_FRAME_W, _FRAME_H)], fill=(0, 0, 0))
    draw.text((8, _FRAME_H - bar_h + 6), iso_label, fill=(255, 255, 255))
    draw.text((120, _FRAME_H - bar_h + 6), source[:60], fill=(180, 220, 180))
    return np.array(img, dtype=np.uint8)


def generate_vlm_metadata(lat: float, lon: float, location_name: str, start_ym: str, end_ym: str) -> str:
    prompt = (
        f"[SYSTEM] You are the Satellite VLM Agent observing a Landsat/MODIS orbital sequence.\n\n"
        f"Location: {location_name} (lat={lat:.3f}, lon={lon:.3f})\n"
        f"Time span: {start_ym} to {end_ym}\n"
        f"This region is a known deforestation hotspot in the Brazilian Amazon.\n\n"
        "Describe in 2-3 sentences: (1) explicitly confirm whether the change is true structural decay "
        "(long-term land clearing, agricultural expansion) or merely a seasonal phenology shift/brown-out, "
        "(2) what specific vegetation changes are evident in the multi-year sequence to support this, "
        "and (3) the ecological significance of this occurrence."
    )
    logger.info("  Running LFM VLM inference for metadata…")
    result = generate(prompt=prompt, max_tokens=200)
    return result.get("response", "").strip() if isinstance(result, dict) else str(result).strip()


def fetch_monthly_frames(
    bbox: list[float],
    lat: float,
    lon: float,
    start_ym: str,
    end_ym: str,
) -> tuple[list[tuple[np.ndarray, str]], str]:
    """
    Fetch one frame per month using the timelapse provider stack (GEE → GIBS).
    Returns (list_of_frames, provider_name).
    """
    from core.timelapse import _month_range, _fetch_gee_frames, _fetch_gibs_frames
    months = _month_range(start_ym, end_ym)
    if not months:
        return [], "none"

    # Try GEE first
    gee_frames = _fetch_gee_frames(bbox, months)
    if gee_frames and len(gee_frames) >= 2:
        logger.info("  [GEE] %d Sentinel-2 frames", len(gee_frames))
        return gee_frames, "GEE Sentinel-2 SR 10m cloud-masked"

    # Fall back to GIBS
    logger.info("  [GIBS] GEE unavailable, falling back to NASA GIBS")
    gibs_frames = _fetch_gibs_frames(bbox, months)
    return gibs_frames, "NASA GIBS (HLS 30m / MODIS 250m fallback)"



def seed_single_cell(
    lat: float,
    lon: float,
    cell_dim: float,
    start_ym: str,
    end_ym: str,
    location_name: str,
    region_note: str,
    cache_dir: Path,
    force: bool = False,
) -> str | None:
    """Fetch monthly frames for one bbox cell, write WebM + metadata. Returns chunk_sig or None."""
    from datetime import date as _date
    bbox = [lon - cell_dim, lat - cell_dim, lon + cell_dim, lat + cell_dim]
    sig = get_chunk_signature(bbox)
    webm_path = cache_dir / f"nasa_{sig}.webm"
    meta_path = cache_dir / f"nasa_{sig}_meta.json"

    if webm_path.exists() and not force:
        logger.info("  [SKIP] %s already cached (%s)", sig, webm_path.name)
        return sig

    logger.info("  [SEED] sig=%s  bbox=%s  %s→%s", sig, [round(b, 3) for b in bbox], start_ym, end_ym)

    frame_data, provider_source = fetch_monthly_frames(bbox, lat, lon, start_ym, end_ym)

    if len(frame_data) < 2:
        logger.error("  Only %d frames — need ≥2. Skipping cell.", len(frame_data))
        return None

    frames = [arr for arr, _ in frame_data]
    isos   = [iso for _, iso in frame_data]

    fd, tmp = tempfile.mkstemp(suffix=".webm")
    os.close(fd)
    try:
        iio.imwrite(tmp, frames, plugin="pyav", fps=1.5, codec="libvpx-vp9")
        import shutil
        shutil.move(tmp, str(webm_path))
        logger.info("  WebM -> %s  (%d KB)", webm_path.name, webm_path.stat().st_size // 1024)
    except Exception as exc:
        logger.error("  WebM write failed: %s", exc)
        if os.path.exists(tmp):
            os.remove(tmp)
        return None

    vlm_text = generate_vlm_metadata(lat, lon, location_name, start_ym, end_ym)

    meta = {
        "chunk_signature": sig,
        "bbox": bbox,
        "lat": lat,
        "lon": lon,
        "location_name": location_name,
        "region_note": region_note,
        "start_date": start_ym,
        "end_date": end_ym,
        "frames_count": len(frames),
        "frame_dates": isos,
        "vlm_explanation": vlm_text,
        "source": provider_source,
        "seeded_at": _date.today().isoformat(),
        "training_ready": True,
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    logger.info("  Meta -> %s", meta_path.name)
    logger.info("  VLM: %s", vlm_text[:120] if vlm_text else "(model not loaded)")

    save_observation(
        bbox=bbox,
        agent_role="seed_script",
        vlm_text=vlm_text,
        cell_id=None,
        frame_years=None,
        source="nasa_gibs",
        extra={"location_name": location_name, "frame_dates": isos, "seeded_at": meta["seeded_at"]},
    )
    return sig


def seed_grid(
    center_lat: float,
    center_lon: float,
    grid_n: int,
    start_ym: str,
    end_ym: str,
    location_name: str,
    region_note: str,
    cell_dim: float = 0.05,
    force: bool = False,
) -> list[str]:
    """Seed an NxN grid of cells centred on center_lat/lon."""
    cache_dir = Path(__file__).resolve().parents[1] / "assets" / "seeded_data"
    cache_dir.mkdir(parents=True, exist_ok=True)

    half = (grid_n - 1) / 2
    step = cell_dim * 2
    offsets = [i - half for i in range(grid_n)]

    logger.info(
        "Seeding %dx%d grid at (%+.3f, %+.3f) | %s→%s | cell_dim=%.3f",
        grid_n, grid_n, center_lat, center_lon, start_ym, end_ym, cell_dim,
    )

    sigs = []
    for dlat in offsets:
        for dlon in offsets:
            lat = center_lat + dlat * step
            lon = center_lon + dlon * step
            label = f"{location_name} [{dlat:+.0f},{dlon:+.0f}]"
            sig = seed_single_cell(lat, lon, cell_dim, start_ym, end_ym, label, region_note, cache_dir, force)
            if sig:
                sigs.append(sig)

    logger.info("Grid complete: %d/%d cells cached.", len(sigs), grid_n * grid_n)
    return sigs


def main():
    parser = argparse.ArgumentParser(description="Seed NASA GIBS monthly timelapse cache")
    parser.add_argument("--lat", type=float, default=None)
    parser.add_argument("--lon", type=float, default=None)
    parser.add_argument("--grid", type=int, default=1, metavar="N", help="NxN grid size (default 1)")
    parser.add_argument("--target", choices=list(HOTSPOTS.keys()), default=None,
                        help="Named deforestation hotspot shorthand")
    parser.add_argument("--all-targets", action="store_true",
                        help="Seed all known hotspots (respects --grid)")
    parser.add_argument("--start", default=_DEFAULT_START, metavar="YYYY-MM",
                        help="Start month (default %(default)s)")
    parser.add_argument("--end", default=_DEFAULT_END, metavar="YYYY-MM",
                        help="End month (default %(default)s)")
    parser.add_argument("--cell-dim", type=float, default=0.02,
                        help="Half-width of each cell in degrees (default 0.02 ≈ 2.2 km)")
    parser.add_argument("--force", action="store_true", help="Re-seed even if cached")
    args = parser.parse_args()

    targets: list[tuple[float, float, str, str]] = []
    if args.all_targets:
        for lat, lon, display, note in HOTSPOTS.values():
            targets.append((lat, lon, display, note))
    elif args.target:
        lat, lon, display, note = HOTSPOTS[args.target]
        targets.append((lat, lon, display, note))
    elif args.lat is not None and args.lon is not None:
        targets.append((args.lat, args.lon, "Custom Location", "User-specified"))
    else:
        lat, lon, display, note = HOTSPOTS["rondoniaWS"]
        targets.append((lat, lon, display, note))

    for lat, lon, display, note in targets:
        seed_grid(lat, lon, args.grid, args.start, args.end, display, note, args.cell_dim, args.force)

    logger.info("All done.")


if __name__ == "__main__":
    main()
