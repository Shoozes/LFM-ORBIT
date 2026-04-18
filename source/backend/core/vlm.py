import logging
import httpx
from io import BytesIO
from PIL import Image

logger = logging.getLogger(__name__)

# Lazy-loaded transformer pipelines
_grounding_pipeline = None
_vqa_pipeline = None
_caption_pipeline = None

_ESRI_MAP = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export"

def _fetch_image(bbox: list[float]) -> Image.Image:
    w, s, e, n = bbox
    buf = 0.005 # minor padding for cropped areas
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
        # Return a blank image to avoid crashing the pipeline
        return Image.new("RGB", (512, 512), (0, 0, 0))

def run_vlm_grounding(bbox: list[float], prompt: str) -> list[dict]:
    """Runs OwlViT zero-shot object detection."""
    global _grounding_pipeline
    if _grounding_pipeline is None:
        from transformers import pipeline
        logger.info("[VLM] Initializing Grounding model (google/owlvit-base-patch32)...")
        _grounding_pipeline = pipeline("zero-shot-object-detection", model="google/owlvit-base-patch32")

    image = _fetch_image(bbox)
    results = _grounding_pipeline(image, candidate_labels=[prompt])
    
    out = []
    width, height = image.size
    for r in results:
        # Owlvit tends to output many boxes, filter low confidence
        if r["score"] > 0.05:
            box = r["box"]
            xmin = box["xmin"] / width
            ymin = box["ymin"] / height
            xmax = box["xmax"] / width
            ymax = box["ymax"] / height
            out.append({"label": r["label"], "bbox": [ymin, xmin, ymax, xmax]})

    return out

def run_vlm_vqa(bbox: list[float], question: str) -> str:
    """Runs ViLT Visual Question Answering."""
    global _vqa_pipeline
    if _vqa_pipeline is None:
        from transformers import pipeline
        logger.info("[VLM] Initializing VQA model (dandelin/vilt-b32-finetuned-vqa)...")
        _vqa_pipeline = pipeline("visual-question-answering", model="dandelin/vilt-b32-finetuned-vqa")

    image = _fetch_image(bbox)
    results = _vqa_pipeline(image=image, question=question, top_k=1)
    
    if results and len(results) > 0:
        return results[0]["answer"].capitalize() + "."
    return "Unknown."

def run_vlm_caption(bbox: list[float]) -> str:
    """Runs ViT-GPT2 Image Captioning."""
    global _caption_pipeline
    if _caption_pipeline is None:
        from transformers import pipeline
        logger.info("[VLM] Initializing Caption model (nlpconnect/vit-gpt2-image-captioning)...")
        _caption_pipeline = pipeline("image-to-text", model="nlpconnect/vit-gpt2-image-captioning")

    image = _fetch_image(bbox)
    results = _caption_pipeline(image)
    
    if isinstance(results, list) and len(results) > 0:
        return results[0]["generated_text"].capitalize() + "."
    return "A satellite view of the ground."
