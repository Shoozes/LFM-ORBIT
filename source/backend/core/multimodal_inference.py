from __future__ import annotations

import base64
import binascii
import logging
import os
import threading
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from core.model_manifest import SatelliteModelArtifact, resolve_satellite_model_artifact

try:
    from PIL import Image, ImageStat, UnidentifiedImageError
except ImportError:  # pragma: no cover - optional runtime dependency guard
    Image = None  # type: ignore[assignment]
    ImageStat = None  # type: ignore[assignment]

    class UnidentifiedImageError(Exception):
        """Fallback image decode error used when Pillow is not installed."""


_VALID_BACKENDS = {"none", "llama_cpp_mmproj", "transformers_vlm"}
_DEFAULT_TRANSFORMERS_TASK = "image-text-to-text"
_DEFAULT_TRANSFORMERS_MODEL = "LiquidAI/LFM2.5-VL-450M"
_DEFAULT_IMAGE_REVIEW_MAX_TOKENS = 160
_IMAGE_REVIEW_PROMPT = (
    "Review the satellite evidence image for the configured concern. "
    "Describe only visible evidence. Do not infer legality, casualty, ownership, intent, "
    "or cause beyond visible image evidence. If the image is blank, cloudy, too low-resolution, "
    "or not relevant, say that clearly."
)
_IMAGE_REVIEW_PIPELINE = None
_PIPELINE_UNAVAILABLE = object()
_IMAGE_RUNTIME_VALIDATED = False
_IMAGE_RUNTIME_LOCK = threading.RLock()

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ImagePayload:
    image: Any
    source_label: str
    image_b64_present: bool
    image_path_label: str
    width: int
    height: int


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _runtime_reason(*, enabled: bool, backend: str, require_mmproj: bool, mmproj_present: bool) -> str:
    if not enabled:
        return "image-conditioned inference feature flag is disabled"
    if backend not in _VALID_BACKENDS:
        return f"unsupported image inference backend: {backend}"
    if backend == "none":
        return "image inference backend is none"
    if backend == "llama_cpp_mmproj" and require_mmproj and not mmproj_present:
        return "mmproj not present"
    if backend == "llama_cpp_mmproj":
        return "llama_cpp_mmproj image adapter is unavailable in this Orbit runtime"
    if backend == "transformers_vlm" and _IMAGE_REVIEW_PIPELINE is _PIPELINE_UNAVAILABLE:
        return "transformers_vlm image adapter unavailable"
    if backend == "transformers_vlm" and _IMAGE_REVIEW_PIPELINE is None:
        return "transformers_vlm image adapter has not been loaded yet"
    if backend == "transformers_vlm" and not _IMAGE_RUNTIME_VALIDATED:
        return "transformers_vlm image adapter loaded; image smoke has not passed yet"
    return "transformers_vlm image adapter loaded"


def _runtime_mode(*, enabled: bool, backend: str, adapter_loaded: bool) -> str:
    if enabled and backend == "transformers_vlm" and adapter_loaded:
        return "image_conditioned_review"
    return "text_evidence_packet"


def _configured_visual_model() -> str:
    return os.getenv("ORBIT_IMAGE_VLM_MODEL", _DEFAULT_TRANSFORMERS_MODEL).strip() or _DEFAULT_TRANSFORMERS_MODEL


def _configured_transformers_task() -> str:
    return os.getenv("ORBIT_IMAGE_VLM_TASK", _DEFAULT_TRANSFORMERS_TASK).strip() or _DEFAULT_TRANSFORMERS_TASK


def _configured_review_max_tokens(default: int = _DEFAULT_IMAGE_REVIEW_MAX_TOKENS) -> int:
    raw = os.getenv("ORBIT_IMAGE_REVIEW_MAX_TOKENS", "").strip()
    if not raw:
        return default
    try:
        return max(1, min(2048, int(raw)))
    except ValueError:
        return default


def _configured_review_device() -> str:
    return os.getenv("ORBIT_IMAGE_REVIEW_DEVICE", "auto").strip().lower() or "auto"


def _public_path_label(path: str | None) -> str:
    if not path:
        return ""
    return Path(path).name


def _strip_data_url(value: str) -> str:
    text = value.strip()
    if "," in text and text.lower().startswith("data:"):
        return text.split(",", 1)[1].strip()
    return text


def _decode_image_payload(*, image_b64: str | None, image_path: str | None) -> _ImagePayload | None:
    if Image is None:
        return None

    raw: bytes
    source_label: str
    b64_present = bool(image_b64)
    path_label = _public_path_label(image_path)
    if image_b64:
        try:
            raw = base64.b64decode(_strip_data_url(image_b64), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("image_b64 must be valid base64 image data") from exc
        source_label = "request_b64"
    elif image_path:
        path = Path(image_path)
        if not path.is_file():
            raise ValueError("image_path does not point to an available image file")
        raw = path.read_bytes()
        source_label = path.name
    else:
        raise ValueError("image_b64 or image_path is required")

    try:
        image = Image.open(BytesIO(raw)).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("image payload is not a readable image") from exc

    width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError("image payload has invalid dimensions")
    return _ImagePayload(
        image=image,
        source_label=source_label,
        image_b64_present=b64_present,
        image_path_label=path_label,
        width=width,
        height=height,
    )


def _is_blank_or_no_data(image: Any) -> bool:
    if ImageStat is None:
        return False
    stat = ImageStat.Stat(image)
    extrema = image.getextrema()
    channel_ranges = [(hi - lo) for lo, hi in extrema]
    max_stddev = max(float(value) for value in stat.stddev) if stat.stddev else 0.0
    return max(channel_ranges or [0]) <= 2 or max_stddev <= 1.0


def _get_transformers_review_pipeline():
    global _IMAGE_REVIEW_PIPELINE
    with _IMAGE_RUNTIME_LOCK:
        if _IMAGE_REVIEW_PIPELINE is not None:
            return _IMAGE_REVIEW_PIPELINE
        try:
            from transformers import pipeline
        except Exception as exc:  # pragma: no cover - optional install
            logger.warning("[MM] transformers unavailable for image review: %s", exc)
            _IMAGE_REVIEW_PIPELINE = _PIPELINE_UNAVAILABLE
            return _IMAGE_REVIEW_PIPELINE

        task = _configured_transformers_task()
        model = _configured_visual_model()
        try:
            pipeline_kwargs: dict[str, Any] = {"model": model}
            device = _configured_review_device()
            if device == "auto":
                pipeline_kwargs["device_map"] = "auto"
            elif device:
                pipeline_kwargs["device"] = device
            _IMAGE_REVIEW_PIPELINE = pipeline(task, **pipeline_kwargs)
        except Exception as exc:  # pragma: no cover - model/runtime dependent
            logger.warning("[MM] failed to initialize image review model %s/%s: %s", task, model, exc)
            _IMAGE_REVIEW_PIPELINE = _PIPELINE_UNAVAILABLE
        return _IMAGE_REVIEW_PIPELINE


def _extract_transformers_text(result: Any) -> str:
    if isinstance(result, list) and result:
        return _extract_transformers_text(result[0])
    if isinstance(result, dict):
        for key in ("answer", "generated_text", "caption", "text"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, list) and value:
                extracted = _extract_transformers_text(value[-1])
                if extracted:
                    return extracted
        content = result.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            for item in reversed(content):
                extracted = _extract_transformers_text(item)
                if extracted:
                    return extracted
    if isinstance(result, str):
        return result.strip()
    return ""


def _bounded_review_prompt(prompt: str) -> str:
    user_prompt = " ".join(prompt.strip().split())
    if len(user_prompt) > 1000:
        user_prompt = user_prompt[:1000].rstrip()
    if not user_prompt:
        return _IMAGE_REVIEW_PROMPT
    return f"{_IMAGE_REVIEW_PROMPT}\n\nConfigured concern prompt: {user_prompt}"


def _run_transformers_review(*, prompt: str, image: Any, max_tokens: int) -> str:
    pipe = _get_transformers_review_pipeline()
    if pipe is _PIPELINE_UNAVAILABLE:
        raise RuntimeError("transformers_vlm image adapter unavailable")

    task = _configured_transformers_task()
    bounded_prompt = _bounded_review_prompt(prompt)
    transformers_logger = logging.getLogger("transformers")
    previous_transformers_level = transformers_logger.level
    with _IMAGE_RUNTIME_LOCK:
        transformers_logger.setLevel(max(previous_transformers_level, logging.ERROR))
        try:
            if task == "image-text-to-text":
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "image": image},
                            {"type": "text", "text": bounded_prompt},
                        ],
                    }
                ]
                try:
                    result = pipe(
                        text=messages,
                        max_new_tokens=max_tokens,
                        return_full_text=False,
                    )
                except TypeError:
                    result = pipe(text=messages, max_new_tokens=max_tokens)
            elif task == "visual-question-answering":
                try:
                    result = pipe(image=image, question=bounded_prompt, top_k=1)
                except TypeError:
                    result = pipe(image=image, question=bounded_prompt)
            elif task == "image-to-text":
                try:
                    result = pipe(image, max_new_tokens=max_tokens)
                except TypeError:
                    result = pipe(image)
            else:
                try:
                    result = pipe(images=image, text=bounded_prompt, max_new_tokens=max_tokens)
                except TypeError:
                    try:
                        result = pipe(image=image, text=bounded_prompt, max_new_tokens=max_tokens)
                    except TypeError:
                        result = pipe(image=image, text=bounded_prompt)
        finally:
            transformers_logger.setLevel(previous_transformers_level)
    text = _extract_transformers_text(result)
    if not text:
        raise RuntimeError("transformers_vlm image adapter returned an empty response")
    return text


def multimodal_status(artifact: SatelliteModelArtifact | None = None) -> dict[str, Any]:
    resolved = artifact or resolve_satellite_model_artifact()
    artifact_status = resolved.to_status_dict()
    enabled = _env_bool("ORBIT_IMAGE_CONDITIONED_INFERENCE", False)
    backend = os.getenv("ORBIT_IMAGE_INFERENCE_BACKEND", "none").strip().lower() or "none"
    require_mmproj = _env_bool("ORBIT_REQUIRE_MMPROJ_FOR_IMAGE_INFERENCE", True)
    mmproj_present = bool(resolved.mmproj_path and resolved.mmproj_path.exists())
    reason = _runtime_reason(
        enabled=enabled,
        backend=backend,
        require_mmproj=require_mmproj,
        mmproj_present=mmproj_present,
    )

    adapter_loaded = bool(
        enabled
        and backend == "transformers_vlm"
        and _IMAGE_REVIEW_PIPELINE is not None
        and _IMAGE_REVIEW_PIPELINE is not _PIPELINE_UNAVAILABLE
    )
    image_runtime_enabled = adapter_loaded and _IMAGE_RUNTIME_VALIDATED
    runtime_mode = _runtime_mode(enabled=enabled, backend=backend, adapter_loaded=adapter_loaded)
    return {
        "feature": "image_conditioned_runtime",
        "feature_flag_enabled": enabled,
        "runtime_backend": backend,
        "runtime_backend_supported": backend in _VALID_BACKENDS,
        "visual_model": _configured_visual_model() if backend == "transformers_vlm" else "",
        "transformers_task": _configured_transformers_task() if backend == "transformers_vlm" else "",
        "adapter_loaded": adapter_loaded,
        "adapter_validated": bool(_IMAGE_RUNTIME_VALIDATED),
        "require_mmproj": require_mmproj,
        "gguf_present": resolved.model_path.exists(),
        "model_path": str(resolved.model_path),
        "mmproj_path": str(resolved.mmproj_path) if resolved.mmproj_path else "",
        "mmproj_present": mmproj_present,
        "hf_checkpoint_path": artifact_status.get("hf_checkpoint_path", ""),
        "hf_checkpoint_present": artifact_status.get("hf_checkpoint_present", False),
        "lora_adapter_path": artifact_status.get("lora_adapter_path", ""),
        "lora_adapter_present": artifact_status.get("lora_adapter_present", False),
        "training_modality": artifact_status.get("training_modality", "unknown"),
        "image_training_verified": artifact_status.get("image_training_verified", False),
        "training_train_rows": artifact_status.get("training_train_rows", 0),
        "training_multimodal_rows": artifact_status.get("training_multimodal_rows", 0),
        "training_image_blocks": artifact_status.get("training_image_blocks", 0),
        "training_eval_rows": artifact_status.get("training_eval_rows", 0),
        "text_evidence_reasoning": resolved.model_path.exists(),
        "image_conditioned_reasoning": image_runtime_enabled,
        "image_conditioned_runtime_enabled": image_runtime_enabled,
        "runtime_inference_mode": runtime_mode,
        "image_conditioned_runtime_reason": reason,
    }


def _unavailable_payload(
    *,
    prompt: str,
    image_path: str | None,
    image_b64: str | None,
    max_tokens: int,
    metadata: dict[str, Any] | None,
    reason: str,
    status: dict[str, Any] | None = None,
    image_payload: _ImagePayload | None = None,
) -> dict[str, Any]:
    runtime_status = status or multimodal_status()
    return {
        "available": False,
        "runtime_backend": runtime_status["runtime_backend"],
        "runtime_inference_mode": runtime_status["runtime_inference_mode"],
        "visual_model": runtime_status.get("visual_model", ""),
        "reason": reason,
        "response": "",
        "image_conditioned": False,
        "abstained": False,
        "max_tokens": max_tokens,
        "provenance": {
            "image_conditioned": False,
            "visual_model": runtime_status.get("visual_model", ""),
            "model_path": _public_path_label(runtime_status.get("model_path", "")),
            "mmproj_path": _public_path_label(runtime_status.get("mmproj_path", "")),
            "hf_checkpoint_path": _public_path_label(runtime_status.get("hf_checkpoint_path", "")),
            "image_path": image_payload.image_path_label if image_payload else _public_path_label(image_path),
            "image_b64_present": bool(image_b64),
            "image_source": image_payload.source_label if image_payload else "",
            "image_width": image_payload.width if image_payload else 0,
            "image_height": image_payload.height if image_payload else 0,
            "prompt_present": bool(prompt.strip()),
            "fallback_used": False,
            "runtime_inference_mode": runtime_status["runtime_inference_mode"],
            **(metadata or {}),
        },
    }


def generate_with_image(
    prompt: str,
    *,
    image_path: str | None = None,
    image_b64: str | None = None,
    max_tokens: int = 256,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    global _IMAGE_RUNTIME_VALIDATED
    max_tokens = max(1, min(int(max_tokens or _configured_review_max_tokens()), _configured_review_max_tokens()))
    status = multimodal_status()
    try:
        image_payload = _decode_image_payload(image_b64=image_b64, image_path=image_path)
    except ValueError as exc:
        return _unavailable_payload(
            prompt=prompt,
            image_path=image_path,
            image_b64=image_b64,
            max_tokens=max_tokens,
            metadata=metadata,
            reason=str(exc),
            status=status,
        )

    if image_payload is None:
        return _unavailable_payload(
            prompt=prompt,
            image_path=image_path,
            image_b64=image_b64,
            max_tokens=max_tokens,
            metadata=metadata,
            reason="Pillow is unavailable; image payload cannot be decoded",
            status=status,
        )

    if _is_blank_or_no_data(image_payload.image):
        return {
            "available": True,
            "runtime_backend": status["runtime_backend"],
            "runtime_inference_mode": status["runtime_inference_mode"],
            "visual_model": status.get("visual_model", ""),
            "reason": "blank_or_no_data_image",
            "response": "No visible evidence was reviewed because the selected image chip is blank or no-data.",
            "image_conditioned": False,
            "abstained": True,
            "max_tokens": max_tokens,
            "provenance": {
                "image_conditioned": False,
                "visual_model": status.get("visual_model", ""),
                "image_source": image_payload.source_label,
                "image_path": image_payload.image_path_label,
                "image_b64_present": image_payload.image_b64_present,
                "image_width": image_payload.width,
                "image_height": image_payload.height,
                "prompt_present": bool(prompt.strip()),
                "fallback_used": False,
                "runtime_inference_mode": status["runtime_inference_mode"],
                **(metadata or {}),
            },
        }

    enabled = bool(status["feature_flag_enabled"])
    backend = str(status["runtime_backend"])
    if not enabled or backend != "transformers_vlm":
        return _unavailable_payload(
            prompt=prompt,
            image_path=image_path,
            image_b64=image_b64,
            max_tokens=max_tokens,
            metadata=metadata,
            reason=status["image_conditioned_runtime_reason"],
            status=status,
            image_payload=image_payload,
        )

    try:
        response = _run_transformers_review(
            prompt=prompt.strip(),
            image=image_payload.image,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        runtime_status = multimodal_status()
        return _unavailable_payload(
            prompt=prompt,
            image_path=image_path,
            image_b64=image_b64,
            max_tokens=max_tokens,
            metadata=metadata,
            reason=str(exc),
            status=runtime_status,
            image_payload=image_payload,
        )

    _IMAGE_RUNTIME_VALIDATED = True
    loaded_status = multimodal_status()
    visual_model = loaded_status.get("visual_model", _configured_visual_model())
    return {
        "available": True,
        "runtime_backend": "transformers_vlm",
        "runtime_inference_mode": "image_conditioned_review",
        "visual_model": visual_model,
        "reason": "ok",
        "response": response,
        "image_conditioned": True,
        "abstained": False,
        "max_tokens": max_tokens,
        "provenance": {
            "image_conditioned": True,
            "visual_model": visual_model,
            "runtime_backend": "transformers_vlm",
            "runtime_inference_mode": "image_conditioned_review",
            "image_source": metadata.get("imagery_origin", image_payload.source_label) if metadata else image_payload.source_label,
            "frame_id": metadata.get("frame_id", "") if metadata else "",
            "bbox": metadata.get("bbox", []) if metadata else [],
            "image_path": image_payload.image_path_label,
            "image_b64_present": image_payload.image_b64_present,
            "image_width": image_payload.width,
            "image_height": image_payload.height,
            "prompt_present": bool(prompt.strip()),
            "fallback_used": False,
            **(metadata or {}),
        },
    }
