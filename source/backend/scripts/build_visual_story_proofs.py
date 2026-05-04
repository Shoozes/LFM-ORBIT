"""Build close-look visual story proof plates from cached or fresh Sentinel Hub imagery.

The default lane uses Sentinel Hub Process API with local development credentials.
Fetched frames are saved under assets/seeded_data/visual_story_frames so the
same imagery can be reused for demos and future training/export cycles.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
FRAME_ROOT = BACKEND_ROOT / "assets" / "seeded_data" / "visual_story_frames"
DOCS_ROOT = REPO_ROOT / "docs"
STORY_OUTPUT_ROOT = DOCS_ROOT / "media" / "story-plates"
LOCAL_STORY_OUTPUT_ROOT = FRAME_ROOT / "story_plates"
SECRETS_PATHS = (
    REPO_ROOT / ".tools" / ".secrets" / "sentinel.txt",
    REPO_ROOT / ".tools" / ".secrets" / "sh.txt",
)

PUBLIC_LABEL_SCOPE_TERMS = (
    "area",
    "zone",
    "group",
    "context",
    "region",
    "candidate",
    "sample",
    "corridor",
    "cluster",
    "row",
)

TOKEN_URL = "https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token"
PROCESS_URL = "https://services.sentinel-hub.com/api/v1/process"
ESRI_EXPORT_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export"

TRUE_COLOR_EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: ["B04", "B03", "B02", "dataMask"],
    output: { bands: 4, sampleType: "AUTO" }
  };
}
function evaluatePixel(sample) {
  return [
    Math.min(1, 2.7 * sample.B04),
    Math.min(1, 2.7 * sample.B03),
    Math.min(1, 2.7 * sample.B02),
    sample.dataMask
  ];
}
"""

BURN_SCAR_EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: ["B12", "B08", "B04", "dataMask"],
    output: { bands: 4, sampleType: "AUTO" }
  };
}
function evaluatePixel(sample) {
  return [
    Math.min(1, 1.55 * sample.B12),
    Math.min(1, 1.35 * sample.B08),
    Math.min(1, 1.35 * sample.B04),
    sample.dataMask
  ];
}
"""


@dataclass(frozen=True)
class StoryBox:
    label: str
    bbox: tuple[float, float, float, float]
    color: str
    confidence: float


@dataclass(frozen=True)
class Story:
    story_id: str
    title: str
    mission: str
    where: str
    why: str
    output_name: str
    bbox: tuple[float, float, float, float]
    date_from: str
    date_to: str
    evalscript: str
    visual_mode: str
    imagery_provider: str
    targets: tuple[str, ...]
    boxes: tuple[StoryBox, ...]
    source_hint: str
    public_docs: bool = False
    visual_audit_status: str = "candidate"
    visual_audit_notes: tuple[str, ...] = ()
    fallback_video: str | None = None
    crop: tuple[float, float, float, float] | None = None


STORIES: tuple[Story, ...] = (
    Story(
        story_id="critical_minerals",
        title="Critical Minerals Expansion Watch",
        mission="Extraction-site region evidence",
        where="Salar de Atacama / Escondida / Atacama corridor",
        why="retain pond, tailings, pit, road, and facility regions without production or pollution claims",
        output_name="story-critical-minerals-expansion.png",
        bbox=(-69.115, -24.29, -69.035, -24.21),
        date_from="2024-01-15",
        date_to="2025-12-15",
        evalscript=TRUE_COLOR_EVALSCRIPT,
        visual_mode="true_color",
        imagery_provider="sentinelhub",
        targets=("evaporation pond regions", "tailings regions", "open-pit expansion", "industrial roads", "facility clusters"),
        source_hint="Sentinel-2 L2A 10m close look",
        public_docs=True,
        visual_audit_status="approved",
        visual_audit_notes=(
            "Public plate uses region/corridor/cluster labels only; no illegal-mining, pollution, or output-volume claim is made.",
            "The image is visually strong for extraction-site region evidence: benches, pond-like areas, roads, and facility clusters are legible.",
        ),
        fallback_video="sh_fbe644a9",
        boxes=(
            StoryBox("open-pit expansion region", (0.29, 0.18, 0.70, 0.82), "#f97316", 0.86),
            StoryBox("tailings region", (0.32, 0.02, 0.69, 0.25), "#facc15", 0.82),
            StoryBox("evaporation pond region", (0.03, 0.61, 0.20, 0.95), "#22d3ee", 0.79),
            StoryBox("industrial road corridor", (0.08, 0.18, 0.24, 0.65), "#a3e635", 0.75),
            StoryBox("facility cluster region", (0.65, 0.54, 0.78, 0.70), "#2dd4bf", 0.72),
        ),
    ),
    Story(
        story_id="houses",
        title="Roof Sample Areas",
        mission="Sample visible roof regions",
        where="Orlando, Florida context imagery",
        why="mark sample roof candidates without claiming an exhaustive count",
        output_name="story-object-evidence-houses.png",
        bbox=(-81.458, 28.408, -81.448, 28.418),
        date_from="2026-01-01",
        date_to="2026-02-15",
        evalscript=TRUE_COLOR_EVALSCRIPT,
        visual_mode="true_color",
        imagery_provider="esri_context",
        targets=("sample roof candidates", "roof-row samples", "large roof area"),
        source_hint="Esri World Imagery context",
        fallback_video="sh_f03170dc",
        crop=(0.57, 0.12, 1.0, 0.55),
        boxes=(
            StoryBox("roof candidate", (0.045, 0.245, 0.105, 0.300), "#2dd4bf", 0.86),
            StoryBox("roof candidate", (0.139, 0.339, 0.200, 0.400), "#2dd4bf", 0.84),
            StoryBox("roof candidate", (0.706, 0.368, 0.764, 0.462), "#2dd4bf", 0.82),
            StoryBox("roof-row sample", (0.663, 0.753, 0.755, 0.876), "#2dd4bf", 0.78),
        ),
    ),
    Story(
        story_id="shelters",
        title="Shelter Row Areas",
        mission="Humanitarian infrastructure regions",
        where="Cox's Bazar camp context area",
        why="mark shelter-row clusters and aid-roof areas without person-level claims",
        output_name="story-object-evidence-shelters.png",
        bbox=(92.1530, 21.2070, 92.1590, 21.2130),
        date_from="2025-01-01",
        date_to="2025-03-01",
        evalscript=TRUE_COLOR_EVALSCRIPT,
        visual_mode="true_color",
        imagery_provider="esri_context",
        targets=("shelter-row clusters", "aid-roof areas", "access-lane context"),
        source_hint="Esri World Imagery context",
        fallback_video=None,
        boxes=(
            StoryBox("shelter-row cluster", (0.13, 0.08, 0.23, 0.14), "#2dd4bf", 0.84),
            StoryBox("shelter-row cluster", (0.31, 0.08, 0.43, 0.15), "#2dd4bf", 0.83),
            StoryBox("shelter-row cluster", (0.57, 0.10, 0.72, 0.17), "#2dd4bf", 0.82),
            StoryBox("shelter-row cluster", (0.18, 0.31, 0.34, 0.39), "#2dd4bf", 0.84),
            StoryBox("shelter-row cluster", (0.43, 0.35, 0.57, 0.43), "#2dd4bf", 0.81),
            StoryBox("shelter-row cluster", (0.66, 0.36, 0.83, 0.44), "#2dd4bf", 0.80),
            StoryBox("shelter-row cluster", (0.29, 0.57, 0.47, 0.65), "#2dd4bf", 0.80),
            StoryBox("shelter-row cluster", (0.55, 0.61, 0.73, 0.69), "#2dd4bf", 0.79),
            StoryBox("aid-roof area", (0.44, 0.22, 0.55, 0.30), "#38bdf8", 0.72),
        ),
    ),
    Story(
        story_id="port",
        title="Port Activity Areas",
        mission="Supply-chain region evidence",
        where="Suez channel port area",
        why="retain visible container clusters, berth context, and docked-vessel groups without claiming an exhaustive count",
        output_name="story-object-evidence-port.png",
        bbox=(32.515, 29.900, 32.575, 29.955),
        date_from="2025-11-01",
        date_to="2025-12-20",
        evalscript=TRUE_COLOR_EVALSCRIPT,
        visual_mode="true_color",
        imagery_provider="esri_context",
        targets=("shipping container clusters", "docked-vessel groups", "berth context areas"),
        source_hint="Esri World Imagery context",
        public_docs=True,
        visual_audit_status="approved",
        visual_audit_notes=(
            "Public plate uses area/group labels only; no singular vessel claim is promoted from this crop.",
            "The previous channel-vessel box was rejected because visual review showed open water at the box location.",
        ),
        fallback_video="sh_2d990c6b",
        crop=(0.60, 0.05, 0.96, 0.43),
        boxes=(
            StoryBox("shipping container cluster", (0.46, 0.28, 0.55, 0.39), "#2dd4bf", 0.82),
            StoryBox("container yard cluster", (0.50, 0.42, 0.60, 0.54), "#2dd4bf", 0.80),
            StoryBox("docked-vessel group", (0.30, 0.64, 0.45, 0.75), "#38bdf8", 0.77),
            StoryBox("berth basin context", (0.15, 0.62, 0.27, 0.74), "#facc15", 0.72),
        ),
    ),
    Story(
        story_id="fireline",
        title="Fireline Candidate Areas",
        mission="Smoke and burn-scar candidate regions",
        where="Highway 82 fire corridor, Georgia",
        why="flag candidate smoke, burn-scar, and road-impact regions for review",
        output_name="story-object-evidence-fireline.png",
        bbox=(-81.905, 31.170, -81.785, 31.290),
        date_from="2026-04-01",
        date_to="2026-04-28",
        evalscript=BURN_SCAR_EVALSCRIPT,
        visual_mode="burn_scar",
        imagery_provider="sentinelhub",
        targets=("burn-scar candidate areas", "smoke-shadow areas", "road-impact area"),
        source_hint="Sentinel-2 L2A SWIR/NIR/Red",
        fallback_video="sh_4015e8b8",
        boxes=(
            StoryBox("burn-scar candidate area", (0.20, 0.22, 0.50, 0.45), "#fb7185", 0.82),
            StoryBox("burn-scar candidate area", (0.52, 0.40, 0.76, 0.58), "#fb7185", 0.79),
            StoryBox("smoke-shadow area", (0.31, 0.14, 0.61, 0.28), "#f472b6", 0.74),
            StoryBox("road-impact area", (0.55, 0.66, 0.74, 0.76), "#22d3ee", 0.69),
        ),
    ),
    Story(
        story_id="road",
        title="Road Lifeline",
        mission="Mobility disruption",
        where="I-4 / SR-536 interchange, Florida",
        why="track road access and queue candidates for civilian lifeline review",
        output_name="story-object-evidence-road.png",
        bbox=(-81.535, 28.360, -81.505, 28.390),
        date_from="2025-01-01",
        date_to="2025-03-01",
        evalscript=TRUE_COLOR_EVALSCRIPT,
        visual_mode="true_color",
        imagery_provider="esri_context",
        targets=("road corridors", "traffic queue area", "structure area"),
        source_hint="Esri World Imagery context",
        fallback_video=None,
        boxes=(
            StoryBox("road corridor", (0.28, 0.18, 0.39, 0.84), "#22d3ee", 0.82),
            StoryBox("road corridor", (0.48, 0.12, 0.59, 0.74), "#22d3ee", 0.80),
            StoryBox("traffic queue area", (0.35, 0.48, 0.52, 0.58), "#facc15", 0.72),
            StoryBox("structure area", (0.65, 0.30, 0.78, 0.44), "#2dd4bf", 0.68),
        ),
    ),
    Story(
        story_id="debris",
        title="Coastal Debris / Slick Candidate Watch",
        mission="Environmental candidate evidence",
        where="Singapore Strait coastal waterway",
        why="flag coastal slick, foam-line, and debris candidates, not garbage-patch mass or material ID",
        output_name="story-object-evidence-debris.png",
        bbox=(103.60, 1.12, 103.95, 1.38),
        date_from="2025-01-01",
        date_to="2025-11-01",
        evalscript=TRUE_COLOR_EVALSCRIPT,
        visual_mode="true_color",
        imagery_provider="sentinelhub",
        targets=("slick candidate areas", "foam-line regions", "coastal debris review areas"),
        source_hint="Sentinel-2 L2A 10m close look",
        fallback_video="sh_99548137",
        boxes=(
            StoryBox("slick candidate area", (0.18, 0.22, 0.48, 0.34), "#a3e635", 0.71),
            StoryBox("foam-line region", (0.50, 0.40, 0.82, 0.50), "#a3e635", 0.69),
            StoryBox("coastal debris review area", (0.28, 0.62, 0.42, 0.73), "#facc15", 0.64),
        ),
    ),
)


def _parse_secret_lines(path: Path) -> dict[str, str]:
    values = {"client_id": "", "client_secret": "", "instance_id": ""}
    if not path.exists():
        return values
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    aliases = {
        "CLIENTID": "client_id",
        "CLIENT_ID": "client_id",
        "SH_CLIENT_ID": "client_id",
        "SENTINEL_CLIENT_ID": "client_id",
        "CLIENT": "client_secret",
        "CLIENT_SECRET": "client_secret",
        "SH_CLIENT_SECRET": "client_secret",
        "SENTINEL_CLIENT_SECRET": "client_secret",
        "API": "instance_id",
        "INSTANCE_ID": "instance_id",
        "SH_INSTANCE_ID": "instance_id",
    }
    plain: list[str] = []
    for line in lines:
        if "=" in line:
            raw_key, raw_value = line.split("=", 1)
        else:
            parts = line.replace(":", " ", 1).split(maxsplit=1)
            if len(parts) == 2 and parts[0].upper().replace("-", "_") in aliases:
                raw_key, raw_value = parts
            else:
                plain.append(line)
                continue
        key = aliases.get(raw_key.strip().upper().replace("-", "_"))
        if key and raw_value.strip() and not values[key]:
            values[key] = raw_value.strip().strip("\"'")
    if not values["client_id"] and not values["client_secret"]:
        if len(plain) >= 3:
            values["instance_id"] = plain[0]
            values["client_secret"] = plain[1]
            values["client_id"] = plain[2]
        elif len(plain) >= 2:
            values["client_secret"] = plain[0]
            values["client_id"] = plain[1]
    return values


def _resolve_credentials() -> dict[str, str]:
    client_id = os.environ.get("SH_CLIENT_ID") or os.environ.get("SENTINEL_CLIENT_ID") or ""
    client_secret = os.environ.get("SH_CLIENT_SECRET") or os.environ.get("SENTINEL_CLIENT_SECRET") or ""
    instance_id = os.environ.get("SH_INSTANCE_ID") or os.environ.get("SENTINEL_INSTANCE_ID") or ""
    if client_id and client_secret:
        return {"client_id": client_id, "client_secret": client_secret, "instance_id": instance_id, "source": "env"}
    for path in SECRETS_PATHS:
        values = _parse_secret_lines(path)
        if values["client_id"] and values["client_secret"]:
            values["source"] = str(path.relative_to(REPO_ROOT))
            return values
    return {"client_id": "", "client_secret": "", "instance_id": "", "source": "unavailable"}


def _get_token(credentials: dict[str, str]) -> str:
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": credentials["client_id"],
            "client_secret": credentials["client_secret"],
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Sentinel Hub token response did not include access_token")
    return token


def _fetch_sentinel_frame(story: Story, token: str, width: int, height: int) -> Image.Image:
    response = requests.post(
        PROCESS_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "image/png",
        },
        json={
            "input": {
                "bounds": {"bbox": list(story.bbox), "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
                "data": [
                    {
                        "type": "sentinel-2-l2a",
                        "dataFilter": {
                            "timeRange": {"from": f"{story.date_from}T00:00:00Z", "to": f"{story.date_to}T23:59:59Z"},
                            "mosaickingOrder": "leastCC",
                        },
                    }
                ],
            },
            "output": {"width": width, "height": height, "responses": [{"identifier": "default", "format": {"type": "image/png"}}]},
            "evalscript": story.evalscript,
        },
        timeout=60,
    )
    response.raise_for_status()
    from io import BytesIO

    return Image.open(BytesIO(response.content)).convert("RGB")


def _fetch_esri_frame(story: Story, width: int, height: int) -> Image.Image:
    response = requests.get(
        ESRI_EXPORT_URL,
        params={
            "bbox": ",".join(f"{value:.8f}" for value in story.bbox),
            "bboxSR": "4326",
            "imageSR": "4326",
            "size": f"{width},{height}",
            "format": "jpg",
            "f": "image",
        },
        timeout=45,
    )
    response.raise_for_status()
    from io import BytesIO

    return Image.open(BytesIO(response.content)).convert("RGB")


def _extract_fallback_frame(story: Story, output_path: Path) -> Image.Image | None:
    if not story.fallback_video:
        return None
    video_path = BACKEND_ROOT / "assets" / "seeded_data" / f"{story.fallback_video}.webm"
    if not video_path.exists():
        return None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        "select=eq(n\\,0)",
        "-vframes",
        "1",
        str(output_path),
    ]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return Image.open(output_path).convert("RGB")


def _fit_cover(image: Image.Image, width: int, height: int) -> Image.Image:
    src_w, src_h = image.size
    scale = max(width / src_w, height / src_h)
    resized = image.resize((int(src_w * scale), int(src_h * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _draw_text_box(draw: ImageDraw.ImageDraw, xy: tuple[int, int], lines: list[tuple[str, ImageFont.ImageFont, str]], padding: int = 12) -> None:
    x, y = xy
    width, height = _text_box_size(draw, lines, padding=padding)
    draw.rounded_rectangle((x, y, x + width, y + height), radius=12, fill=(4, 12, 22, 220), outline=(148, 163, 184, 120), width=1)
    cursor_y = y + padding
    for text, font, color in lines:
        draw.text((x + padding, cursor_y), text, font=font, fill=color)
        cursor_y += draw.textbbox((0, 0), text, font=font)[3] + 7


def _text_box_size(draw: ImageDraw.ImageDraw, lines: list[tuple[str, ImageFont.ImageFont, str]], padding: int = 12) -> tuple[int, int]:
    widths = [draw.textbbox((0, 0), text, font=font)[2] for text, font, _ in lines]
    heights = [draw.textbbox((0, 0), text, font=font)[3] for text, font, _ in lines]
    width = max(widths) + padding * 2
    height = sum(heights) + padding * 2 + 7 * (len(lines) - 1)
    return width, height


def _draw_story_plate(story: Story, frame: Image.Image, output_path: Path) -> None:
    width = 1280
    frame_height = 900
    label_font = _font(16, bold=True)
    small_font = _font(13)
    header_lines = [
        (story.title.upper(), _font(24, bold=True), "#f8fafc"),
        ("what: " + story.mission, _font(15), "#bae6fd"),
        ("where: " + story.where, small_font, "#e2e8f0"),
        (f"when: {story.date_from} to {story.date_to}", small_font, "#e2e8f0"),
        ("why: " + story.why, small_font, "#e2e8f0"),
        ("targets: " + ", ".join(story.targets), small_font, "#cbd5e1"),
    ]
    measure = ImageDraw.Draw(Image.new("RGBA", (width, 256), (0, 0, 0, 0)), "RGBA")
    header_height = max(132, _text_box_size(measure, header_lines, padding=10)[1] + 28)
    height = frame_height + header_height
    if story.crop is not None:
        src_w, src_h = frame.size
        left, top, right, bottom = story.crop
        frame = frame.crop(
            (
                int(left * src_w),
                int(top * src_h),
                int(right * src_w),
                int(bottom * src_h),
            )
        )
    image = _fit_cover(frame, width, frame_height)
    image = ImageEnhance.Contrast(image).enhance(1.10)
    image = ImageEnhance.Sharpness(image).enhance(1.12)
    base = Image.new("RGB", (width, height), (2, 6, 23))
    base.paste(image, (0, header_height))
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")

    mission_color = (244, 63, 94, 42) if story.visual_mode == "burn_scar" else (6, 182, 212, 24)
    draw.rectangle(
        (40, header_height + 74, width - 40, header_height + frame_height - 74),
        fill=mission_color,
        outline=(255, 255, 255, 95),
        width=2,
    )

    label_specs: list[tuple[int, int, str, int, int]] = []
    for box in story.boxes:
        x1 = int(box.bbox[0] * width)
        y1 = header_height + int(box.bbox[1] * frame_height)
        x2 = int(box.bbox[2] * width)
        y2 = header_height + int(box.bbox[3] * frame_height)
        color = tuple(int(box.color[i : i + 2], 16) for i in (1, 3, 5))
        for grow, alpha, stroke in ((13, 55, 5), (7, 120, 5), (0, 255, 4)):
            draw.rounded_rectangle(
                (x1 - grow, y1 - grow, x2 + grow, y2 + grow),
                radius=4,
                outline=(*color, alpha),
                width=stroke,
            )
        corner = max(14, min(28, int(min(x2 - x1, y2 - y1) * 0.35)))
        for start, end in (
            ((x1, y1), (x1 + corner, y1)),
            ((x1, y1), (x1, y1 + corner)),
            ((x2, y1), (x2 - corner, y1)),
            ((x2, y1), (x2, y1 + corner)),
            ((x1, y2), (x1 + corner, y2)),
            ((x1, y2), (x1, y2 - corner)),
            ((x2, y2), (x2 - corner, y2)),
            ((x2, y2), (x2, y2 - corner)),
        ):
            draw.line((*start, *end), fill=(*color, 255), width=6)
        draw.rectangle((x1, y1, x2, y2), fill=(*color, 18))
        label = f"{box.label} {box.confidence:.2f}"
        text_box = draw.textbbox((0, 0), label, font=label_font)
        label_w = text_box[2] - text_box[0]
        label_h = text_box[3] - text_box[1]
        ly = max(header_height + 8, y1 - label_h - 10)
        label_specs.append((x1, ly, label, label_w, label_h))

    for x1, ly, label, label_w, label_h in label_specs:
        lx = max(4, min(x1, width - label_w - 16))
        draw.rounded_rectangle((lx, ly, lx + label_w + 12, ly + label_h + 8), radius=5, fill=(2, 6, 23, 218))
        draw.text((lx + 6, ly + 3), label, font=label_font, fill=(236, 254, 255, 255))

    _draw_text_box(draw, (24, 14), header_lines, padding=10)
    proof_lines = [
        ("compact object evidence", _font(15, bold=True), "#f8fafc"),
        (f"{len(story.boxes)} evidence regions | {story.source_hint}", small_font, "#cbd5e1"),
        (f"imagery_origin={'esri_context' if story.imagery_provider == 'esri_context' else 'sentinelhub_direct'}", small_font, "#a7f3d0"),
        ("box_source=visual_story_fixture", small_font, "#fde68a"),
    ]
    if story.story_id == "houses":
        proof_lines.append(("sample boxes, not exhaustive count", small_font, "#bae6fd"))
    _draw_text_box(draw, (24, header_height + frame_height - 126), proof_lines)

    result = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, quality=94)


def _validate_public_story(story: Story) -> None:
    if not story.public_docs:
        return
    if story.visual_audit_status != "approved":
        raise RuntimeError(
            f"Story {story.story_id} is marked public_docs but visual_audit_status="
            f"{story.visual_audit_status!r}; public plates must be visually approved first."
        )
    unsafe_labels = [
        box.label
        for box in story.boxes
        if not any(term in box.label.lower() for term in PUBLIC_LABEL_SCOPE_TERMS)
    ]
    if unsafe_labels:
        raise RuntimeError(
            f"Story {story.story_id} has public labels that read like unsupported single-object claims: "
            + ", ".join(sorted(unsafe_labels))
        )


def build_story(story: Story, token: str | None, *, force_fetch: bool, frame_width: int, frame_height: int) -> dict[str, Any]:
    _validate_public_story(story)
    FRAME_ROOT.mkdir(parents=True, exist_ok=True)
    provider_slug = "esri" if story.imagery_provider == "esri_context" else "sentinel"
    frame_path = FRAME_ROOT / f"{story.story_id}_{provider_slug}.png"
    meta_path = FRAME_ROOT / f"{story.story_id}_{provider_slug}_meta.json"
    output_root = STORY_OUTPUT_ROOT if story.public_docs else LOCAL_STORY_OUTPUT_ROOT
    output_path = output_root / story.output_name
    fetched = False
    fetch_error = ""

    if force_fetch or not frame_path.exists():
        if story.imagery_provider == "esri_context":
            try:
                frame = _fetch_esri_frame(story, frame_width, frame_height)
                frame.save(frame_path)
                fetched = True
            except Exception as exc:
                fetch_error = str(exc)
                if frame_path.exists():
                    frame = Image.open(frame_path).convert("RGB")
                else:
                    raise RuntimeError(f"Unable to fetch Esri context imagery for {story.story_id}: {fetch_error}") from exc
        elif token:
            try:
                frame = _fetch_sentinel_frame(story, token, frame_width, frame_height)
                frame.save(frame_path)
                fetched = True
            except Exception as exc:
                fetch_error = str(exc)
                frame = _extract_fallback_frame(story, frame_path)
                if frame is None and frame_path.exists():
                    frame = Image.open(frame_path).convert("RGB")
                if frame is None:
                    raise RuntimeError(f"Unable to fetch or recover imagery for {story.story_id}: {fetch_error}") from exc
        else:
            frame = _extract_fallback_frame(story, frame_path)
            if frame is None and frame_path.exists():
                frame = Image.open(frame_path).convert("RGB")
            if frame is None:
                raise RuntimeError(f"Sentinel Hub credentials unavailable and no cached frame exists for {story.story_id}")
    else:
        frame = Image.open(frame_path).convert("RGB")

    _draw_story_plate(story, frame, output_path)

    meta = {
        "story_id": story.story_id,
        "title": story.title,
        "what": story.mission,
        "where": story.where,
        "when": {"date_from": story.date_from, "date_to": story.date_to},
        "why": story.why,
        "bbox": list(story.bbox),
        "date_from": story.date_from,
        "date_to": story.date_to,
        "visual_mode": story.visual_mode,
        "source": (
            "Esri World Imagery context"
            if fetched and story.imagery_provider == "esri_context"
            else "Sentinel Hub Process API"
            if fetched
            else "cached visual story frame"
        ),
        "imagery_provider": story.imagery_provider,
        "imagery_origin": (
            "esri_context"
            if story.imagery_provider == "esri_context"
            else "sentinelhub_direct"
            if fetched
            else "cached_api"
        ),
        "runtime_truth_mode": "realtime" if fetched else "replay",
        "scoring_basis": "visual_only",
        "box_source": "visual_story_fixture",
        "box_count": len(story.boxes),
        "boxes": [
            {
                "label": box.label,
                "bbox": list(box.bbox),
                "confidence": box.confidence,
                "color": box.color,
            }
            for box in story.boxes
        ],
        "targets": list(story.targets),
        "crop": list(story.crop) if story.crop else None,
        "frame_path": frame_path.relative_to(REPO_ROOT).as_posix(),
        "output_path": output_path.relative_to(REPO_ROOT).as_posix(),
        "public_docs": story.public_docs,
        "visual_audit_status": story.visual_audit_status,
        "visual_audit_notes": list(story.visual_audit_notes),
        "fetched_at": date.today().isoformat() if fetched else None,
        "fetch_error": fetch_error,
        "training_ready": True,
        "note": "Boxes are deterministic visual-story evidence fixtures over cached/fetched imagery, not a claim of live model-backed object detection.",
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def _story_frame_path(story: Story) -> Path:
    provider_slug = "esri" if getattr(story, "imagery_provider", "") == "esri_context" else "sentinel"
    return FRAME_ROOT / f"{story.story_id}_{provider_slug}.png"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build README visual story proof plates.")
    parser.add_argument("--story", action="append", choices=[story.story_id for story in STORIES], help="Build only selected story id. Repeatable.")
    parser.add_argument("--force-fetch", action="store_true", help="Fetch fresh Sentinel Hub frames even when cached story frames exist.")
    parser.add_argument("--offline", action="store_true", help="Do not contact external imagery/token APIs; use cached or fallback story frames only.")
    parser.add_argument("--frame-width", type=int, default=1400)
    parser.add_argument("--frame-height", type=int, default=1000)
    args = parser.parse_args()
    if args.offline and args.force_fetch:
        parser.error("--offline cannot be combined with --force-fetch")

    manifest = FRAME_ROOT / "visual_story_manifest.json"
    selected = set(args.story or [story.story_id for story in STORIES])
    needs_sentinel_token = (
        not args.offline
        and any(
            story.story_id in selected
            and getattr(story, "imagery_provider", "") != "esri_context"
            and (args.force_fetch or not _story_frame_path(story).exists())
            for story in STORIES
        )
    )
    token = None
    if needs_sentinel_token:
        credentials = _resolve_credentials()
        if credentials["client_id"] and credentials["client_secret"]:
            token = _get_token(credentials)
            print(f"Sentinel Hub credentials resolved from {credentials['source']}.")
        else:
            print("Sentinel Hub credentials unavailable; using cached/fallback story frames.")
    elif args.offline:
        print("Offline story refresh requested; using cached/fallback story frames.")
    else:
        print("Cached story frames found; skipping Sentinel Hub token request.")

    existing_by_id: dict[str, dict[str, Any]] = {}
    if args.story and manifest.exists():
        try:
            existing = json.loads(manifest.read_text(encoding="utf-8"))
            existing_by_id = {
                story_meta["story_id"]: story_meta
                for story_meta in existing.get("stories", [])
                if isinstance(story_meta, dict) and isinstance(story_meta.get("story_id"), str)
            }
        except (OSError, json.JSONDecodeError):
            existing_by_id = {}

    built_by_id: dict[str, dict[str, Any]] = {}
    for story in STORIES:
        if story.story_id not in selected:
            continue
        meta = build_story(
            story,
            token,
            force_fetch=args.force_fetch,
            frame_width=args.frame_width,
            frame_height=args.frame_height,
        )
        built_by_id[story.story_id] = meta
        print(f"Wrote {meta['output_path']} from {meta['source']}.")
        time.sleep(0.2)

    if args.story and existing_by_id:
        existing_by_id.update(built_by_id)
        built = [existing_by_id[story.story_id] for story in STORIES if story.story_id in existing_by_id]
    else:
        built = [built_by_id[story.story_id] for story in STORIES if story.story_id in built_by_id]
    manifest.write_text(json.dumps({"generated_at": date.today().isoformat(), "stories": built}, indent=2), encoding="utf-8")
    print(f"Wrote {manifest.relative_to(REPO_ROOT)}.")


if __name__ == "__main__":
    main()
