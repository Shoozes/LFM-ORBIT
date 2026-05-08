"""
seed_sentinel_cache.py — Seeds a seeded_data WebM timelapse cache using Sentinel Hub Process API.

Fetches real Sentinel-2 L2A imagery (with leastCC true-color composites)
from Sentinel Hub using environment credentials or local developer secret files.
Stores WebM timelapses + rich training metadata to assets/seeded_data/.
Also writes observation records to assets/observation_store/ for agent reuse.

Usage:
    python scripts/seed_sentinel_cache.py --target rondoniaWS --grid 3
    python scripts/seed_sentinel_cache.py --target rondoniaWS --grid 3 --skip-vlm-metadata
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
from core.config import DETECTION, resolve_sentinel_credentials
from core.inference import generate
from core.indices import compute_blue_green_haze_score, compute_visible_whiteness
from core.observation_store import save_observation
from core.scene_qc import INVALID_SCL_CLASSES, evaluate_scene_quality
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

SH_EVALSCRIPTS = {
    "true_color": """//VERSION=3
function setup() {
    return {
        input: ["B04", "B03", "B02", "dataMask"],
        output: { bands: 3, sampleType: "AUTO" }
    };
}
function evaluatePixel(sample) {
    return [2.5 * sample.B04, 2.5 * sample.B03, 2.5 * sample.B02];
}
""",
    "burn_scar": """//VERSION=3
function setup() {
    return {
        input: ["B12", "B08", "B04", "dataMask"],
        output: { bands: 3, sampleType: "AUTO" }
    };
}
function evaluatePixel(sample) {
    return [1.45 * sample.B12, 1.35 * sample.B08, 1.35 * sample.B04];
}
""",
}

SH_QUALITY_EVALSCRIPT = """//VERSION=3
function setup() {
    return {
        input: ["SCL", "dataMask"],
        output: { bands: 2, sampleType: "UINT8" }
    };
}
function evaluatePixel(sample) {
    return [sample.SCL, sample.dataMask];
}
"""

SH_BAND_STATS_EVALSCRIPT = """//VERSION=3
function setup() {
    return {
        input: ["B02", "B03", "B04", "B08", "B11", "B12", "SCL", "CLD", "CLP", "dataMask"],
        output: { bands: 10, sampleType: "FLOAT32" }
    };
}
function evaluatePixel(sample) {
    return [
        sample.B02,
        sample.B03,
        sample.B04,
        sample.B08,
        sample.B11,
        sample.B12,
        sample.SCL,
        sample.CLD,
        sample.CLP,
        sample.dataMask
    ];
}
"""

SH_EVALSCRIPT = SH_EVALSCRIPTS["true_color"]

_VISUAL_MODE_LABELS = {
    "true_color": "Sentinel Hub Sentinel-2 L2A true color 10m",
    "burn_scar": "Sentinel Hub Sentinel-2 L2A SWIR/NIR/Red burn-scar composite",
}

_VISUAL_MODE_BANDS = {
    "true_color": ["B04", "B03", "B02"],
    "burn_scar": ["B12", "B08", "B04"],
}


def _frame_quality_from_scl(arr: np.ndarray) -> dict:
    """Convert a Sentinel Hub SCL/dataMask response into the repo scene-quality contract."""
    if arr.ndim == 3:
        scl = arr[:, :, 0].astype(np.uint8)
        if arr.shape[-1] > 1:
            data_mask = arr[:, :, 1].astype(np.uint8)
            scl = np.where(data_mask > 0, scl, 0)
    else:
        scl = arr.astype(np.uint8)
    return dict(evaluate_scene_quality(scl))


def _safe_index(numerator: float, denominator: float) -> float | None:
    if abs(denominator) < 1e-9:
        return None
    return round(numerator / denominator, 4)


def _normalize_reflectance(values: np.ndarray) -> np.ndarray:
    finite = values[np.isfinite(values)]
    if finite.size and float(np.nanmedian(finite)) > 2.0:
        return values / 10000.0
    return values


def _band_stats_from_response(arr: np.ndarray, *, include_cloud_pixels: bool = False) -> dict | None:
    if arr.ndim != 3 or arr.shape[-1] < 5:
        return None
    if arr.shape[-1] >= 10:
        blue = _normalize_reflectance(arr[:, :, 0].astype(np.float32))
        green = _normalize_reflectance(arr[:, :, 1].astype(np.float32))
        red = _normalize_reflectance(arr[:, :, 2].astype(np.float32))
        nir = _normalize_reflectance(arr[:, :, 3].astype(np.float32))
        swir1 = _normalize_reflectance(arr[:, :, 4].astype(np.float32))
        swir2 = _normalize_reflectance(arr[:, :, 5].astype(np.float32))
        scl = arr[:, :, 6].astype(np.uint8)
        cld = arr[:, :, 7].astype(np.float32)
        clp = arr[:, :, 8].astype(np.float32)
        data_mask = arr[:, :, 9] > 0
    else:
        blue = None
        green = None
        red = _normalize_reflectance(arr[:, :, 0].astype(np.float32))
        nir = _normalize_reflectance(arr[:, :, 1].astype(np.float32))
        swir1 = None
        swir2 = _normalize_reflectance(arr[:, :, 2].astype(np.float32))
        scl = arr[:, :, 3].astype(np.uint8)
        cld = None
        clp = None
        data_mask = arr[:, :, 4] > 0
    invalid_classes = [0, 1] if include_cloud_pixels else INVALID_SCL_CLASSES
    valid_mask = data_mask & ~np.isin(scl.astype(int), invalid_classes)
    if int(valid_mask.sum()) == 0:
        return None

    def stats(values: np.ndarray) -> dict:
        selected = values[valid_mask]
        return {
            "mean": round(float(np.nanmean(selected)), 4),
            "p10": round(float(np.nanpercentile(selected, 10)), 4),
            "p90": round(float(np.nanpercentile(selected, 90)), 4),
        }

    red_mean = stats(red)["mean"]
    nir_mean = stats(nir)["mean"]
    swir2_mean = stats(swir2)["mean"]
    band_stats = {
        "B04_red": stats(red),
        "B08_nir": stats(nir),
        "B12_swir2": stats(swir2),
    }
    if blue is not None and green is not None and swir1 is not None:
        blue_mean = stats(blue)["mean"]
        green_mean = stats(green)["mean"]
        swir1_mean = stats(swir1)["mean"]
        band_stats = {
            "B02_blue": stats(blue),
            "B03_green": stats(green),
            **band_stats,
            "B11_swir1": stats(swir1),
        }
    else:
        blue_mean = None
        green_mean = None
        swir1_mean = None

    cloud_mask = np.isin(scl.astype(int), [3, 8, 9, 10]) & data_mask
    cld_probability = None
    clp_probability = None
    if cld is not None:
        cld_selected = cld[data_mask]
        if cld_selected.size:
            cld_mean = float(np.nanmean(cld_selected))
            cld_probability = round(cld_mean / 100.0 if cld_mean > 1.0 else cld_mean, 4)
    if clp is not None:
        clp_selected = clp[data_mask]
        if clp_selected.size:
            clp_mean = float(np.nanmean(clp_selected))
            clp_probability = round(clp_mean / 255.0 if clp_mean > 1.0 else clp_mean, 4)

    derived_indices = {
        "ndvi": _safe_index(nir_mean - red_mean, nir_mean + red_mean),
        "nbr_swir2": _safe_index(nir_mean - swir2_mean, nir_mean + swir2_mean),
        "swir2_nir_ratio": _safe_index(swir2_mean, nir_mean),
    }
    if blue_mean is not None and green_mean is not None and swir1_mean is not None:
        derived_indices["ndmi_swir1"] = _safe_index(nir_mean - swir1_mean, nir_mean + swir1_mean)
        derived_indices["visible_whiteness"] = round(compute_visible_whiteness(red_mean, green_mean, blue_mean), 4)
        derived_indices["blue_green_haze_score"] = round(
            compute_blue_green_haze_score(blue_mean, green_mean, red_mean),
            4,
        )

    return {
        "bands": band_stats,
        "derived_indices": derived_indices,
        "cloud_metrics": {
            "scl_cloud_ratio": round(float(cloud_mask.sum()) / max(1, int(data_mask.sum())), 4),
            "cloud_probability_cld": cld_probability,
            "cloud_probability_clp": clp_probability,
            "data_mask_ratio": round(float(data_mask.mean()), 4),
        },
        "valid_pixel_ratio": round(float(valid_mask.mean()), 4),
        "stats_source": (
            "sentinelhub_process_b02_b03_b04_b08_b11_b12_scl_cld_clp_smoke_cloud_review"
            if include_cloud_pixels
            else "sentinelhub_process_b02_b03_b04_b08_b11_b12_scl_cld_clp"
        ),
        "scl_cloud_pixels_included": include_cloud_pixels,
    }

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


def parse_date_windows(values: list[str] | None) -> list[tuple[str, str, str]]:
    """Parse repeated LABEL=YYYY-MM-DD:YYYY-MM-DD date-window arguments."""
    windows: list[tuple[str, str, str]] = []
    for raw in values or []:
        label, sep, interval = raw.partition("=")
        start_date, range_sep, end_date = interval.partition(":")
        label = label.strip()
        start_date = start_date.strip()
        end_date = end_date.strip()
        if not sep or not range_sep or not label or not start_date or not end_date:
            raise ValueError("date windows must use LABEL=YYYY-MM-DD:YYYY-MM-DD")
        if len(start_date) != 10 or len(end_date) != 10:
            raise ValueError("date-window bounds must be full YYYY-MM-DD dates")
        windows.append((label, start_date, end_date))
    return windows


def fetch_sh_window(
    label: str,
    start_date: str,
    end_date: str,
    bbox_coords: list[float],
    config: SHConfig,
    visual_mode: str = "true_color",
    allow_smoke_cloud_frames: bool = False,
) -> tuple[np.ndarray | None, str, dict | None]:
    w, s, e, n = bbox_coords
    bbox = BBox(bbox=[w, s, e, n], crs=CRS.WGS84)

    time_interval = (start_date, end_date)
    source_label = _VISUAL_MODE_LABELS.get(visual_mode, _VISUAL_MODE_LABELS["true_color"])

    quality_request = SentinelHubRequest(
        evalscript=SH_QUALITY_EVALSCRIPT,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=DataCollection.SENTINEL2_L2A,
                time_interval=time_interval,
                mosaicking_order="leastCC",
            )
        ],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
        bbox=bbox,
        size=(256, 192),
        config=config,
    )

    try:
        quality_data = quality_request.get_data()
        quality = _frame_quality_from_scl(quality_data[0]) if quality_data else None
    except Exception as exc:
        logger.warning("  [SH] QC failed %s %s->%s: %s", label, start_date, end_date, exc)
        quality = None

    if quality is None:
        return None, "", {
            "accepted": False,
            "valid_pixel_ratio": 0.0,
            "cloud_pixel_ratio": 0.0,
            "nodata_pixel_ratio": 0.0,
            "total_pixels": 0,
            "reasons": ["quality_unavailable"],
        }

    smoke_cloud_review = _should_keep_smoke_cloud_frame(label, visual_mode, quality, allow_smoke_cloud_frames)

    if not quality["accepted"] and not smoke_cloud_review:
        logger.warning(
            "  [SH] Skipping cloudy/low-quality frame %s %s->%s valid=%.1f%% cloud=%.1f%% reasons=%s",
            label,
            start_date,
            end_date,
            quality["valid_pixel_ratio"] * 100,
            quality["cloud_pixel_ratio"] * 100,
            ",".join(quality["reasons"]),
        )
        return None, "", quality
    if smoke_cloud_review:
        quality["accepted"] = True
        quality["review_only"] = True
        quality["acceptance_override"] = "wildfire_smoke_cloud_review"
        quality["flags"] = sorted(set([*quality.get("flags", []), "smoke_or_cloud_review"]))
        logger.warning(
            "  [SH] Keeping smoky/cloud-flagged wildfire frame %s %s->%s for review valid=%.1f%% cloud=%.1f%%",
            label,
            start_date,
            end_date,
            quality["valid_pixel_ratio"] * 100,
            quality["cloud_pixel_ratio"] * 100,
        )

    band_stats_request = SentinelHubRequest(
        evalscript=SH_BAND_STATS_EVALSCRIPT,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=DataCollection.SENTINEL2_L2A,
                time_interval=time_interval,
                mosaicking_order="leastCC",
            )
        ],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
        bbox=bbox,
        size=(256, 192),
        config=config,
    )

    try:
        band_stats_data = band_stats_request.get_data()
        band_stats = _band_stats_from_response(
            band_stats_data[0],
            include_cloud_pixels=smoke_cloud_review,
        ) if band_stats_data else None
        if band_stats:
            quality["band_stats"] = band_stats
    except Exception as exc:
        logger.warning("  [SH] Band stats failed %s %s->%s: %s", label, start_date, end_date, exc)
        quality["band_stats_error"] = str(exc)
    
    request = SentinelHubRequest(
        evalscript=SH_EVALSCRIPTS.get(visual_mode, SH_EVALSCRIPT),
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
            logger.info(f"  [SH] {label} {start_date}->{end_date}  mean={arr.mean():.0f}")
            
            img = Image.fromarray(arr).convert("RGB")
            
            draw = ImageDraw.Draw(img)
            bar_h = 28
            draw.rectangle([(0, _FRAME_H - bar_h), (_FRAME_W, _FRAME_H)], fill=(0, 0, 0))
            draw.text((8, _FRAME_H - bar_h + 6), label, fill=(255, 255, 255))
            draw.text((120, _FRAME_H - bar_h + 6), source_label, fill=(180, 220, 180))
            quality_label = (
                f"smoke/cloud review {quality['cloud_pixel_ratio'] * 100:.0f}%"
                if smoke_cloud_review
                else f"clear {quality['valid_pixel_ratio'] * 100:.0f}%"
            )
            draw.text((680, _FRAME_H - bar_h + 6), quality_label, fill=(180, 220, 255))
            
            return np.array(img, dtype=np.uint8), f"{source_label} {label}", quality
    except Exception as e:
        logger.warning(f"  [SH] Failed {label} {start_date}->{end_date}: {e}")
        
    return None, "", quality


def _should_keep_smoke_cloud_frame(
    label: str,
    visual_mode: str,
    quality: dict,
    allow_smoke_cloud_frames: bool,
) -> bool:
    """Keep active wildfire frames that SCL may mark as cloud because of white smoke."""
    if not allow_smoke_cloud_frames or visual_mode != "burn_scar":
        return False
    if quality.get("accepted"):
        return False
    label_text = label.lower()
    if not any(token in label_text for token in ("active", "ignition", "smoke", "plume")):
        return False
    reasons = set(quality.get("reasons", []))
    if not reasons.issubset({"insufficient_valid_pixels"}):
        return False
    nodata_ratio = float(quality.get("nodata_pixel_ratio") or 0.0)
    cloud_ratio = float(quality.get("cloud_pixel_ratio") or 0.0)
    return nodata_ratio <= 0.15 and cloud_ratio >= 0.20


def fetch_sh_month(
    year: int,
    month: int,
    bbox_coords: list[float],
    config: SHConfig,
    visual_mode: str = "true_color",
) -> tuple[np.ndarray | None, str, dict | None]:
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
    label = f"{year}-{month:02d}-15" # approx mid month
    return fetch_sh_window(label, start_date, end_date, bbox_coords, config, visual_mode)


def generate_vlm_metadata(lat: float, lon: float, location_name: str, start_ym: str, end_ym: str) -> str:
    prompt = (
        f"[SYSTEM] You are the Satellite evidence-packet reviewer analyzing high-resolution Sentinel-2 orbital sequence metadata.\n\n"
        f"Location: {location_name} (lat={lat:.3f}, lon={lon:.3f})\n"
        f"Time span: {start_ym} to {end_ym}\n"
        f"This region is a known deforestation hotspot in the Brazilian Amazon.\n\n"
        "Describe in 2-3 sentences: (1) explicitly confirm whether the change is true structural decay "
        "(long-term land clearing, agricultural expansion) or merely a seasonal phenology shift/brown-out, "
        "(2) what specific vegetation changes are evident in the multi-year sequence to support this, "
        "and (3) the ecological significance of this occurrence."
    )
    logger.info("  Running LFM evidence-packet inference for metadata...")
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
    skip_vlm_metadata: bool = False,
    use_case_id: str | None = None,
    target_category: str | None = None,
    target_pack_id: str | None = None,
    target_task: str | None = None,
    date_windows: list[tuple[str, str, str]] | None = None,
    visual_mode: str = "true_color",
    allow_smoke_cloud_frames: bool = False,
) -> str | None:
    from datetime import date as _date
    bbox = [lon - cell_dim, lat - cell_dim, lon + cell_dim, lat + cell_dim]
    sig = get_chunk_signature(bbox)
    webm_path = cache_dir / f"sh_{sig}.webm"
    meta_path = cache_dir / f"sh_{sig}_meta.json"
    frame_dir = cache_dir / f"sh_{sig}_frames"

    if webm_path.exists() and not force:
        logger.info("  [SKIP] %s already cached (%s)", sig, webm_path.name)
        return sig

    logger.info("  [SEED] sig=%s  bbox=%s  %s→%s", sig, [round(b, 3) for b in bbox], start_ym, end_ym)

    frames = []
    isos = []
    frame_quality = []
    band_stats_by_frame = []
    rejected_windows = []
    provider_source = _VISUAL_MODE_LABELS.get(visual_mode, _VISUAL_MODE_LABELS["true_color"])
    requested_bands = _VISUAL_MODE_BANDS.get(visual_mode, _VISUAL_MODE_BANDS["true_color"])
    
    frame_windows = date_windows or [
        (f"{year}-{month:02d}-15", f"{year}-{month:02d}-01", f"{year + 1}-01-01" if month == 12 else f"{year}-{month + 1:02d}-01")
        for year, month in _month_range(start_ym, end_ym)
    ]
    effective_start = frame_windows[0][1] if frame_windows else start_ym
    effective_end = frame_windows[-1][2] if frame_windows else end_ym

    for label, window_start, window_end in frame_windows:
        frame, source_lbl, quality = fetch_sh_window(
            label,
            window_start,
            window_end,
            bbox,
            config,
            visual_mode,
            allow_smoke_cloud_frames=allow_smoke_cloud_frames,
        )
        if frame is not None:
            frames.append(frame)
            isos.append(label)
            frame_quality.append({
                "label": label,
                "valid_pixel_ratio": quality.get("valid_pixel_ratio") if quality else None,
                "cloud_pixel_ratio": quality.get("cloud_pixel_ratio") if quality else None,
                "nodata_pixel_ratio": quality.get("nodata_pixel_ratio") if quality else None,
                "reasons": quality.get("reasons", []) if quality else [],
                "review_only": bool(quality.get("review_only")) if quality else False,
                "acceptance_override": quality.get("acceptance_override") if quality else None,
                "flags": quality.get("flags", []) if quality else [],
            })
            if quality and quality.get("band_stats"):
                band_stats_by_frame.append({
                    "label": label,
                    **quality["band_stats"],
                })
        else:
            rejected_windows.append({
                "label": label,
                "start_date": window_start,
                "end_date": window_end,
                "quality": quality,
            })

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

    if force and frame_dir.exists():
        import shutil
        shutil.rmtree(frame_dir)
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_images = []
    repo_root = Path(__file__).resolve().parents[3]
    for index, (label, frame) in enumerate(zip(isos, frames), start=1):
        safe_label = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in label)
        frame_path = frame_dir / f"{index:02d}_{safe_label}.png"
        Image.fromarray(frame).save(frame_path)
        try:
            frame_images.append(str(frame_path.relative_to(repo_root).as_posix()))
        except ValueError:
            frame_images.append(str(frame_path))
    logger.info("  Frames -> %s  (%d PNG)", frame_dir.name, len(frame_images))

    if skip_vlm_metadata:
        vlm_text = (
            f"Sentinel-2 L2A timelapse seeded for {location_name} "
            f"from {effective_start} to {effective_end}. Metadata inference was skipped for this cache refresh."
        )
    else:
        vlm_text = generate_vlm_metadata(lat, lon, location_name, start_ym, end_ym)

    meta = {
        "chunk_signature": sig,
        "bbox": bbox,
        "lat": lat,
        "lon": lon,
        "location_name": location_name,
        "region_note": region_note,
        "start_date": effective_start,
        "end_date": effective_end,
        "frames_count": len(frames),
        "frame_dates": isos,
        "frame_images": frame_images,
        "date_windows": [
            {"label": label, "start_date": window_start, "end_date": window_end}
            for label, window_start, window_end in frame_windows
        ],
        "vlm_explanation": vlm_text,
        "source": provider_source,
        "visual_mode": visual_mode,
        "spectral_bands": {
            "visual_mode": visual_mode,
            "requested_bands": requested_bands,
            "stats_requested_bands": ["B02", "B03", "B04", "B08", "B11", "B12", "SCL", "CLD", "CLP", "dataMask"],
            "band_stats_by_frame": band_stats_by_frame,
            "derived_indices": [
                "ndvi",
                "nbr_swir2",
                "ndmi_swir1",
                "swir2_nir_ratio",
                "visible_whiteness",
                "blue_green_haze_score",
            ],
            "note": "Band statistics are computed from accepted Sentinel-2 L2A pixels after SCL/dataMask quality filtering.",
        },
        "cloud_policy": {
            "min_valid_pixel_ratio": DETECTION.min_quality_threshold,
            "invalid_scl_classes": INVALID_SCL_CLASSES,
            "mosaicking_order": "leastCC",
            "allow_smoke_cloud_frames": allow_smoke_cloud_frames,
            "smoke_cloud_note": (
                "Wildfire burn-scar seeding may keep active/ignition smoke frames for review when SCL flags likely smoke as cloud; "
                "those frames are not standalone positive detections."
                if allow_smoke_cloud_frames
                else ""
            ),
        },
        "frame_quality": frame_quality,
        "rejected_windows": rejected_windows,
        "seeded_at": _date.today().isoformat(),
        "training_ready": True,
        "use_case_id": use_case_id,
        "target_category": target_category,
        "target_pack_id": target_pack_id,
        "target_task": target_task,
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
        extra={
            "location_name": location_name,
            "frame_dates": isos,
            "seeded_at": meta["seeded_at"],
            "use_case_id": use_case_id,
            "target_category": target_category,
            "target_pack_id": target_pack_id,
            "target_task": target_task,
        },
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
    skip_vlm_metadata: bool = False,
    use_case_id: str | None = None,
    target_category: str | None = None,
    target_pack_id: str | None = None,
    target_task: str | None = None,
    date_windows: list[tuple[str, str, str]] | None = None,
    visual_mode: str = "true_color",
    allow_smoke_cloud_frames: bool = False,
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
            sig = seed_single_cell(
                lat,
                lon,
                cell_dim,
                start_ym,
                end_ym,
                label,
                region_note,
                cache_dir,
                config,
                force,
                skip_vlm_metadata,
                use_case_id,
                target_category,
                target_pack_id,
                target_task,
                date_windows,
                visual_mode,
                allow_smoke_cloud_frames,
            )
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
    parser.add_argument("--cell-dim", type=float, default=0.02,
                        help="Half-width of each cell in degrees (default 0.02)")
    parser.add_argument("--force", action="store_true", help="Re-seed even if cached")
    parser.add_argument(
        "--skip-vlm-metadata",
        action="store_true",
        help="Seed imagery/video cache without running local VLM metadata generation for each cell",
    )
    parser.add_argument("--location-name", default=None, help="Display name for a custom lat/lon seed target.")
    parser.add_argument("--region-note", default=None, help="Short provenance or mission note for a custom seed target.")
    parser.add_argument("--use-case-id", default=None, help="Optional temporal use-case id to persist into metadata.")
    parser.add_argument("--target-category", default=None, help="Optional target category to persist into metadata.")
    parser.add_argument("--target-pack-id", default=None, help="Optional target pack id to persist into metadata.")
    parser.add_argument("--target-task", default=None, help="Optional target task to persist into metadata.")
    parser.add_argument(
        "--date-window",
        action="append",
        default=[],
        help="Custom frame window as LABEL=YYYY-MM-DD:YYYY-MM-DD. Repeat to build event-specific timelapses.",
    )
    parser.add_argument(
        "--visual-mode",
        choices=sorted(SH_EVALSCRIPTS.keys()),
        default="true_color",
        help="Sentinel-2 visual composite to request.",
    )
    parser.add_argument(
        "--allow-smoke-cloud-frames",
        action="store_true",
        help="For burn_scar wildfire seeds, keep active/ignition frames that SCL flags as cloud when dataMask is valid; marks them review-only.",
    )
    args = parser.parse_args()
    try:
        date_windows = parse_date_windows(args.date_window)
    except ValueError as exc:
        parser.error(str(exc))

    creds = resolve_sentinel_credentials()
    if not creds.available:
        logger.error(
            "Sentinel Hub credentials unavailable. Set SENTINEL_CLIENT_ID and "
            "SENTINEL_CLIENT_SECRET, or configure a local developer secret file."
        )
        sys.exit(1)

    config = SHConfig()
    config.sh_client_id = creds.client_id
    config.sh_client_secret = creds.client_secret
    if creds.instance_id:
        config.instance_id = creds.instance_id
    logger.info("Sentinel Hub credentials resolved from %s", creds.source)

    targets: list[tuple[float, float, str, str]] = []
    if args.all_targets:
        for lat, lon, display, note in HOTSPOTS.values():
            targets.append((lat, lon, display, note))
    elif args.target:
        lat, lon, display, note = HOTSPOTS[args.target]
        targets.append((lat, lon, display, note))
    elif args.lat is not None and args.lon is not None:
        targets.append((
            args.lat,
            args.lon,
            args.location_name or "Custom Location",
            args.region_note or "User-specified",
        ))
    else:
        lat, lon, display, note = HOTSPOTS["rondoniaWS"]
        targets.append((lat, lon, display, note))

    for lat, lon, display, note in targets:
        seed_grid(
            lat,
            lon,
            args.grid,
            args.start,
            args.end,
            display,
            note,
            config,
            args.cell_dim,
            args.force,
            args.skip_vlm_metadata,
            args.use_case_id,
            args.target_category,
            args.target_pack_id,
            args.target_task,
            date_windows or None,
            args.visual_mode,
            args.allow_smoke_cloud_frames,
        )

    logger.info("All done.")


if __name__ == "__main__":
    main()
