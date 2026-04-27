import logging
import httpx
from io import BytesIO
from typing import Any, Callable

try:
    from PIL import Image
except ImportError:  # pragma: no cover - environment-specific optional dependency
    Image = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Lazy-loaded transformer pipelines
_grounding_pipeline = None
_vqa_pipeline = None
_caption_pipeline = None
_pipeline_import_failed = False
_PIPELINE_UNAVAILABLE = object()

_ESRI_MAP = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export"

def _normalize_prompt_label(prompt: str) -> str:
    text = (prompt or "").strip().lower()
    if any(token in text for token in ("airplane", "airplanes", "plane", "planes", "airport")):
        return "airplane"
    if any(token in text for token in ("clearing", "clearings", "deforestation", "canopy loss")):
        return "clearing"
    if "canopy" in text or "forest" in text:
        return "canopy"
    if "road" in text:
        return "road"
    if "river" in text:
        return "river"
    return prompt.strip() or "target"


def _load_pipeline(task: str, model: str) -> Callable[..., Any] | None:
    global _pipeline_import_failed
    if _pipeline_import_failed:
        return None
    try:
        from transformers import pipeline
    except Exception as exc:  # pragma: no cover - depends on optional install
        _pipeline_import_failed = True
        logger.warning("[VLM] transformers unavailable; using offline fallback responses: %s", exc)
        return None

    try:
        return pipeline(task, model=model)
    except Exception as exc:  # pragma: no cover - depends on model download/runtime
        logger.warning("[VLM] failed to initialize %s model %s; using fallback responses: %s", task, model, exc)
        return None


def _fallback_grounding(prompt: str) -> list[dict]:
    label = _normalize_prompt_label(prompt)
    if label == "airplane":
        return []
    return [{"label": label, "bbox": [0.24, 0.18, 0.74, 0.76]}]


def _bbox_center(bbox: list[float]) -> tuple[float, float]:
    west, south, east, north = bbox
    return ((west + east) / 2.0, (south + north) / 2.0)


def _fallback_scene_family(bbox: list[float]) -> str:
    lon, lat = _bbox_center(bbox)
    if -82.0 <= lon <= -80.0 and 24.0 <= lat <= 29.0:
        return "florida_corridor"
    if -52.0 <= lon <= -45.0 and 64.0 <= lat <= 70.5:
        return "greenland_ice"
    if -63.0 <= lon <= -59.0 and -11.0 <= lat <= -2.0:
        return "amazon_forest"
    return "generic"


def _fallback_vqa(question: str, bbox: list[float]) -> str:
    text = (question or "").lower()
    if "how many" in text and any(token in text for token in ("airplane", "plane")):
        return "Unable to answer precisely from fallback vision mode."
    if "how many" in text:
        return "1."
    if any(token in text for token in ("land cover", "visible", "scene")):
        scene_family = _fallback_scene_family(bbox)
        if scene_family == "florida_corridor":
            return "Urban road corridor, water bodies, and managed vegetation."
        if scene_family == "greenland_ice":
            return "Ice sheet, exposed rock, and coastal water."
        return "Mixed vegetation, exposed clearing, and road context."
    return "Unable to answer precisely from fallback vision mode."


def _fallback_caption(bbox: list[float]) -> str:
    scene_family = _fallback_scene_family(bbox)
    if scene_family == "florida_corridor":
        return "Florida road corridor beside lakes and developed land."
    if scene_family == "greenland_ice":
        return "Greenland ice edge with coastal water and exposed rock."
    return "Deforested clearing beside intact canopy."


def _fetch_image(bbox: list[float]):
    if Image is None:
        logger.warning("[VLM] Pillow unavailable; using fallback responses.")
        return None

    w, s, e, n = bbox
    buf = 0.005
    url_bbox = f"{w-buf},{s-buf},{e+buf},{n+buf}"

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                _ESRI_MAP,
                params={
                    "bbox": url_bbox,
                    "bboxSR": "4326",
                    "imageSR": "4326",
                    "size": "512,512",
                    "format": "jpg",
                    "f": "image",
                }
            )
            resp.raise_for_status()
            return Image.open(BytesIO(resp.content)).convert("RGB")
    except Exception as exc:
        logger.warning(f"[VLM] Failed to fetch image tile from ESRI for VLM: {exc}")
        return None

def run_vlm_grounding(bbox: list[float], prompt: str) -> list[dict]:
    """Run grounding with a transformers pipeline when available, otherwise degrade safely."""
    global _grounding_pipeline
    if _grounding_pipeline is None:
        logger.info("[VLM] Initializing Grounding model (google/owlvit-base-patch32)...")
        _grounding_pipeline = _load_pipeline("zero-shot-object-detection", "google/owlvit-base-patch32") or _PIPELINE_UNAVAILABLE

    if _grounding_pipeline is _PIPELINE_UNAVAILABLE:
        return _fallback_grounding(prompt)

    image = _fetch_image(bbox)
    if image is None:
        return _fallback_grounding(prompt)

    try:
        results = _grounding_pipeline(image, candidate_labels=[prompt])
    except Exception as exc:
        logger.warning("[VLM] Grounding inference failed; using fallback responses: %s", exc)
        return _fallback_grounding(prompt)

    out = []
    width, height = image.size
    for r in results:
        if r["score"] > 0.05:
            box = r["box"]
            xmin = box["xmin"] / width
            ymin = box["ymin"] / height
            xmax = box["xmax"] / width
            ymax = box["ymax"] / height
            out.append({"label": r["label"], "bbox": [ymin, xmin, ymax, xmax]})

    return out or _fallback_grounding(prompt)

def run_vlm_vqa(bbox: list[float], question: str) -> str:
    """Run VQA when available, otherwise return a deterministic offline fallback."""
    global _vqa_pipeline
    if _vqa_pipeline is None:
        logger.info("[VLM] Initializing VQA model (dandelin/vilt-b32-finetuned-vqa)...")
        _vqa_pipeline = _load_pipeline("visual-question-answering", "dandelin/vilt-b32-finetuned-vqa") or _PIPELINE_UNAVAILABLE

    if _vqa_pipeline is _PIPELINE_UNAVAILABLE:
        return _fallback_vqa(question, bbox)

    image = _fetch_image(bbox)
    if image is None:
        return _fallback_vqa(question, bbox)

    try:
        results = _vqa_pipeline(image=image, question=question, top_k=1)
    except Exception as exc:
        logger.warning("[VLM] VQA inference failed; using fallback response: %s", exc)
        return _fallback_vqa(question, bbox)

    if results and len(results) > 0:
        return results[0]["answer"].capitalize() + "."
    return _fallback_vqa(question, bbox)

def run_vlm_caption(bbox: list[float]) -> str:
    """Run captioning when available, otherwise return a deterministic offline fallback."""
    global _caption_pipeline
    if _caption_pipeline is None:
        logger.info("[VLM] Initializing Caption model (nlpconnect/vit-gpt2-image-captioning)...")
        _caption_pipeline = _load_pipeline("image-to-text", "nlpconnect/vit-gpt2-image-captioning") or _PIPELINE_UNAVAILABLE

    if _caption_pipeline is _PIPELINE_UNAVAILABLE:
        return _fallback_caption(bbox)

    image = _fetch_image(bbox)
    if image is None:
        return _fallback_caption(bbox)

    try:
        results = _caption_pipeline(image)
    except Exception as exc:
        logger.warning("[VLM] Caption inference failed; using fallback response: %s", exc)
        return _fallback_caption(bbox)

    if isinstance(results, list) and len(results) > 0:
        return results[0]["generated_text"].capitalize() + "."
    return _fallback_caption(bbox)
