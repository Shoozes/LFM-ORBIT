"""
seed_sentinel_cache.py — Seeds a seeded_data WebM timelapse cache using Sentinel Hub Process API.

Fetches real Sentinel-2 L2A imagery (with leastCC true-color composites)
from Sentinel Hub using credentials in `.tools/.secrets/sentinel.txt`.
Stores WebM timelapses + rich training metadata to assets/seeded_data/.
Also writes observation records to assets/observation_store/ for agent reuse.

Usage:
    python scripts/seed_sentinel_cache.py --target rondoniaWS --grid 3
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

import imageio.v3 as iio
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.inference import generate
from core.observation_store import save_observation
from sentinelhub import SHConfig, SentinelHubRequest, DataCollection, MimeType, BBox, CRS

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Default dates
_DEFAULT_START = "2023-01"
_DEFAULT_END   = "2025-01"

_FRAME_W = 1024
_FRAME_H = 768

# Known deforestation hotspots
HOTSPOTS = {
    "rondoniaWS": (-10.0, -63.0, "Rondônia Western Frontier", "Historically severe cattle/soy clearing"),
    "rondoniaE":  (-10.5, -62.0, "Rondônia Eastern Arc",      "Active illegal logging corridor"),
    "para":       (-6.5,  -52.5, "Pará Frontier",              "Soy expansion and land grabbing"),
    "acre":       (-9.0,  -70.5, "Acre Logging Corridor",      "Old-growth selective logging"),
    "matogrosso": (-12.5, -52.5, "Mato Grosso Arc",            "Industrial-scale deforestation front"),
}

SH_EVALSCRIPT = """//VERSION=3
function setup() {
    return {
        input: ["B04", "B03", "B02", "dataMask"],
        output: { bands: 3, sampleType: "AUTO" }
    };
}
function evaluatePixel(sample) {
    return [2.5 * sample.B04, 2.5 * sample.B03, 2.5 * sample.B02];
}
"""

def get_chunk_signature(bbox: list[float]) -> str:
    rounded = [round(b, 3) for b in bbox]
    return hashlib.md5(str(rounded).encode()).hexdigest()[:8]

def _month_range(start_ym: str, end_ym: str) -> list[tuple[int, int]]:
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
    # Sample down to 48 frames if interval is too long
    if len(months) > 48:
        step = len(months) / 48
        months = [months[int(i * step)] for i in range(48)]
    return months


def fetch_sh_month(
    year: int,
    month: int,
    bbox_coords: list[float],
    config: SHConfig
) -> tuple[np.ndarray | None, str]:
    w, s, e, n = bbox_coords
    bbox = BBox(bbox=[w, s, e, n], crs=CRS.WGS84)
    
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
        
    time_interval = (start_date, end_date)
    
    request = SentinelHubRequest(
        evalscript=SH_EVALSCRIPT,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=DataCollection.SENTINEL2_L2A,
                time_interval=time_interval,
                mosaicking_order="leastCC",
            )
        ],
        responses=[
            SentinelHubRequest.output_response("default", MimeType.PNG)
        ],
        bbox=bbox,
        size=(_FRAME_W, _FRAME_H),
        config=config
    )
    
    try:
        data = request.get_data()
        if data and len(data) > 0:
            arr = data[0]
            # Convert RGBA to RGB if needed
            if arr.shape[-1] == 4:
                arr = arr[:, :, :3]
            logger.info(f"  [SH] {start_date}  mean={arr.mean():.0f}")
            
            img = Image.fromarray(arr).convert("RGB")
            
            draw = ImageDraw.Draw(img)
            bar_h = 28
            draw.rectangle([(0, _FRAME_H - bar_h), (_FRAME_W, _FRAME_H)], fill=(0, 0, 0))
            iso_label = f"{year}-{month:02d}-15" # approx mid month
            draw.text((8, _FRAME_H - bar_h + 6), iso_label, fill=(255, 255, 255))
            draw.text((120, _FRAME_H - bar_h + 6), "Sentinel Hub Sentinel-2 L2A 10m", fill=(180, 220, 180))
            
            return np.array(img, dtype=np.uint8), f"Sentinel Hub Sentinel-2 L2A  {iso_label}"
    except Exception as e:
        logger.warning(f"  [SH] Failed {start_date}: {e}")
        
    return None, ""


def generate_vlm_metadata(lat: float, lon: float, location_name: str, start_ym: str, end_ym: str) -> str:
    prompt = (
        f"[SYSTEM] You are the Satellite VLM Agent observing a high-resolution Sentinel-2 orbital sequence.\n\n"
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


def seed_single_cell(
    lat: float,
    lon: float,
    cell_dim: float,
    start_ym: str,
    end_ym: str,
    location_name: str,
    region_note: str,
    cache_dir: Path,
    config: SHConfig,
    force: bool = False,
) -> str | None:
    from datetime import date as _date
    bbox = [lon - cell_dim, lat - cell_dim, lon + cell_dim, lat + cell_dim]
    sig = get_chunk_signature(bbox)
    webm_path = cache_dir / f"sh_{sig}.webm"
    meta_path = cache_dir / f"sh_{sig}_meta.json"

    if webm_path.exists() and not force:
        logger.info("  [SKIP] %s already cached (%s)", sig, webm_path.name)
        return sig

    logger.info("  [SEED] sig=%s  bbox=%s  %s→%s", sig, [round(b, 3) for b in bbox], start_ym, end_ym)

    months = _month_range(start_ym, end_ym)
    frames = []
    isos = []
    provider_source = "Sentinel Hub Sentinel-2 L2A"
    
    for year, month in months:
        frame, source_lbl = fetch_sh_month(year, month, bbox, config)
        if frame is not None:
            frames.append(frame)
            isos.append(source_lbl.split()[-1])

    if len(frames) < 2:
        logger.error("  Only %d frames — need ≥2. Skipping cell.", len(frames))
        return None

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

    save_observation(
        bbox=bbox,
        agent_role="seed_script",
        vlm_text=vlm_text,
        cell_id=None,
        frame_years=None,
        source="sentinelhub_process",
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
    config: SHConfig,
    cell_dim: float = 0.05,
    force: bool = False,
) -> list[str]:
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
            sig = seed_single_cell(lat, lon, cell_dim, start_ym, end_ym, label, region_note, cache_dir, config, force)
            if sig:
                sigs.append(sig)

    logger.info("Grid complete: %d/%d cells cached.", len(sigs), grid_n * grid_n)
    return sigs


def main():
    parser = argparse.ArgumentParser(description="Seed Sentinel Hub monthly timelapse cache")
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
    parser.add_argument("--cell-dim", type=float, default=0.02, # 0.02 is usually used instead of 0.05 across codebase, wait 0.05
                        help="Half-width of each cell in degrees (default 0.02)")
    parser.add_argument("--force", action="store_true", help="Re-seed even if cached")
    args = parser.parse_args()

    secrets_path = Path(__file__).resolve().parents[3] / ".tools" / ".secrets" / "sentinel.txt"
    if not secrets_path.exists():
        logger.error(f"Cannot find secrets file at {secrets_path}")
        sys.exit(1)
        
    with open(secrets_path) as f:
        lines = f.read().splitlines()
        if len(lines) < 2:
            logger.error("Sentinel secrets file format invalid.")
            sys.exit(1)
            
    config = SHConfig()
    config.sh_client_secret = lines[0].strip()
    config.sh_client_id = lines[1].strip()

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
        seed_grid(lat, lon, args.grid, args.start, args.end, display, note, config, args.cell_dim, args.force)

    logger.info("All done.")


if __name__ == "__main__":
    main()
