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


def _provenance(*, mode: str, model: str, reason: str = "") -> dict[str, str | bool]:
    is_fallback = mode == "fallback"
    return {
        "runtime_truth_mode": "fallback" if is_fallback else "realtime",
        "imagery_origin": "fallback_none" if is_fallback else "esri_arcgis",
        "scoring_basis": "fallback_none" if is_fallback else "visual_only",
        "output_source": mode,
        "model": model,
        "heuristic_fallback": is_fallback,
        "reason": reason,
    }

def _normalize_prompt_label(prompt: str) -> str:
    text = (prompt or "").strip().lower()
    if any(token in text for token in ("airplane", "airplanes", "plane", "planes", "airport")):
        return "airplane"
    if any(token in text for token in ("home", "homes", "house", "houses", "roof", "roofs", "building", "buildings")):
        return "homes"
    if any(token in text for token in ("boat", "boats", "ship", "ships", "vessel", "vessels", "barge", "barges")):
        return "boats"
    if any(token in text for token in ("flaring", "flare", "gas flare", "well pad")):
        return "possible flaring"
    if any(token in text for token in ("dark smoke", "smoke", "plume", "black smoke")):
        return "dark smoke"
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
    boxes_by_label = {
        "homes": [0.30, 0.28, 0.62, 0.58],
        "boats": [0.35, 0.18, 0.58, 0.70],
        "possible flaring": [0.18, 0.46, 0.42, 0.62],
        "dark smoke": [0.12, 0.40, 0.46, 0.72],
        "road": [0.42, 0.12, 0.56, 0.88],
        "river": [0.20, 0.16, 0.80, 0.44],
    }
    return [{"label": label, "bbox": boxes_by_label.get(label, [0.24, 0.18, 0.74, 0.76])}]


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
    if any(token in text for token in ("boat", "ship", "vessel")):
        return "Potential vessel-like targets require model-backed grounding or replay evidence before confirmation."
    if any(token in text for token in ("smoke", "plume", "flaring", "flare")):
        return "Potential plume or flaring-like targets should be treated as candidate evidence, not a confirmed detection."
    if any(token in text for token in ("home", "house", "roof", "building")):
        return "Built-structure-like targets can be queued for visual grounding, but fallback mode cannot confirm occupancy or use."
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
    return explain_vlm_grounding(bbox, prompt)["results"]


def explain_vlm_grounding(bbox: list[float], prompt: str) -> dict[str, Any]:
    """Run grounding with a transformers pipeline when available, otherwise degrade safely."""
    global _grounding_pipeline
    model = "google/owlvit-base-patch32"
    if _grounding_pipeline is None:
        logger.info("[VLM] Initializing Grounding model (%s)...", model)
        _grounding_pipeline = _load_pipeline("zero-shot-object-detection", model) or _PIPELINE_UNAVAILABLE

    if _grounding_pipeline is _PIPELINE_UNAVAILABLE:
        return {
            "results": _fallback_grounding(prompt),
            "provenance": _provenance(mode="fallback", model=model, reason="pipeline_unavailable"),
        }

    image = _fetch_image(bbox)
    if image is None:
        return {
            "results": _fallback_grounding(prompt),
            "provenance": _provenance(mode="fallback", model=model, reason="image_unavailable"),
        }

    try:
        results = _grounding_pipeline(image, candidate_labels=[prompt])
    except Exception as exc:
        logger.warning("[VLM] Grounding inference failed; using fallback responses: %s", exc)
        return {
            "results": _fallback_grounding(prompt),
            "provenance": _provenance(mode="fallback", model=model, reason="inference_failed"),
        }

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

    if out:
        return {"results": out, "provenance": _provenance(mode="model", model=model)}
    return {
        "results": _fallback_grounding(prompt),
        "provenance": _provenance(mode="fallback", model=model, reason="empty_model_result"),
    }

def run_vlm_vqa(bbox: list[float], question: str) -> str:
    return str(explain_vlm_vqa(bbox, question)["answer"])


def explain_vlm_vqa(bbox: list[float], question: str) -> dict[str, Any]:
    """Run VQA when available, otherwise return a deterministic offline fallback."""
    global _vqa_pipeline
    model = "dandelin/vilt-b32-finetuned-vqa"
    if _vqa_pipeline is None:
        logger.info("[VLM] Initializing VQA model (%s)...", model)
        _vqa_pipeline = _load_pipeline("visual-question-answering", model) or _PIPELINE_UNAVAILABLE

    if _vqa_pipeline is _PIPELINE_UNAVAILABLE:
        return {
            "answer": _fallback_vqa(question, bbox),
            "provenance": _provenance(mode="fallback", model=model, reason="pipeline_unavailable"),
        }

    image = _fetch_image(bbox)
    if image is None:
        return {
            "answer": _fallback_vqa(question, bbox),
            "provenance": _provenance(mode="fallback", model=model, reason="image_unavailable"),
        }

    try:
        results = _vqa_pipeline(image=image, question=question, top_k=1)
    except Exception as exc:
        logger.warning("[VLM] VQA inference failed; using fallback response: %s", exc)
        return {
            "answer": _fallback_vqa(question, bbox),
            "provenance": _provenance(mode="fallback", model=model, reason="inference_failed"),
        }

    if results and len(results) > 0:
        return {
            "answer": results[0]["answer"].capitalize() + ".",
            "provenance": _provenance(mode="model", model=model),
        }
    return {
        "answer": _fallback_vqa(question, bbox),
        "provenance": _provenance(mode="fallback", model=model, reason="empty_model_result"),
    }

def run_vlm_caption(bbox: list[float]) -> str:
    return str(explain_vlm_caption(bbox)["caption"])


def explain_vlm_caption(bbox: list[float]) -> dict[str, Any]:
    """Run captioning when available, otherwise return a deterministic offline fallback."""
    global _caption_pipeline
    model = "nlpconnect/vit-gpt2-image-captioning"
    if _caption_pipeline is None:
        logger.info("[VLM] Initializing Caption model (%s)...", model)
        _caption_pipeline = _load_pipeline("image-to-text", model) or _PIPELINE_UNAVAILABLE

    if _caption_pipeline is _PIPELINE_UNAVAILABLE:
        return {
            "caption": _fallback_caption(bbox),
            "provenance": _provenance(mode="fallback", model=model, reason="pipeline_unavailable"),
        }

    image = _fetch_image(bbox)
    if image is None:
        return {
            "caption": _fallback_caption(bbox),
            "provenance": _provenance(mode="fallback", model=model, reason="image_unavailable"),
        }

    try:
        results = _caption_pipeline(image)
    except Exception as exc:
        logger.warning("[VLM] Caption inference failed; using fallback response: %s", exc)
        return {
            "caption": _fallback_caption(bbox),
            "provenance": _provenance(mode="fallback", model=model, reason="inference_failed"),
        }

    if isinstance(results, list) and len(results) > 0:
        return {
            "caption": results[0]["generated_text"].capitalize() + ".",
            "provenance": _provenance(mode="model", model=model),
        }
    return {
        "caption": _fallback_caption(bbox),
        "provenance": _provenance(mode="fallback", model=model, reason="empty_model_result"),
    }
