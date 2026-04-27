"""Optional Depth Anything V3 adapter.

The app must stay offline-safe by default, so this module never imports the
Depth Anything package unless the feature is explicitly enabled.
"""

from __future__ import annotations

import base64
import importlib.util
import logging
import os
import threading
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_DEPTH_ANYTHING_V3_MODEL = "depth-anything/da3-large"
_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
_FALSE_VALUES = {"0", "false", "no", "off", "disabled"}
_DEFAULT_MAX_PIXELS = 1024 * 1024

_runtime_enabled_override: bool | None = None
_model: Any | None = None
_model_config_key: tuple[str, str] | None = None
_model_lock = threading.Lock()


class DepthAnythingUnavailable(RuntimeError):
    """Raised when the optional Depth Anything lane cannot run."""


@dataclass(frozen=True)
class DepthAnythingConfig:
    enabled: bool
    model_id: str
    requested_device: str
    resolved_device: str
    max_pixels: int
    source: str


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


def _parse_positive_int(value: str | None, default: int) -> int:
    try:
        parsed = int(str(value or "").strip())
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def resolve_depth_anything_config() -> DepthAnythingConfig:
    env_enabled = _parse_bool(os.getenv("DEPTH_ANYTHING_V3_ENABLED"), default=False)
    if _runtime_enabled_override is None:
        enabled = env_enabled
        source = "env"
    else:
        enabled = _runtime_enabled_override
        source = "runtime"

    requested_device = os.getenv("DEPTH_ANYTHING_V3_DEVICE", "auto").strip() or "auto"
    return DepthAnythingConfig(
        enabled=enabled,
        model_id=os.getenv("DEPTH_ANYTHING_V3_MODEL", DEFAULT_DEPTH_ANYTHING_V3_MODEL).strip()
        or DEFAULT_DEPTH_ANYTHING_V3_MODEL,
        requested_device=requested_device,
        resolved_device=_resolve_device(requested_device),
        max_pixels=_parse_positive_int(os.getenv("DEPTH_ANYTHING_V3_MAX_PIXELS"), _DEFAULT_MAX_PIXELS),
        source=source,
    )


def set_depth_anything_enabled(enabled: bool) -> dict[str, Any]:
    global _runtime_enabled_override, _model, _model_config_key
    _runtime_enabled_override = enabled
    if not enabled:
        with _model_lock:
            _model = None
            _model_config_key = None
    return get_depth_anything_status()


def clear_depth_anything_runtime_override() -> None:
    global _runtime_enabled_override, _model, _model_config_key
    _runtime_enabled_override = None
    with _model_lock:
        _model = None
        _model_config_key = None


def _package_available() -> bool:
    return importlib.util.find_spec("depth_anything_3") is not None


def _resolve_device(requested_device: str) -> str:
    if requested_device != "auto":
        return requested_device
    try:
        import torch  # type: ignore

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def get_depth_anything_status() -> dict[str, Any]:
    config = resolve_depth_anything_config()
    package_available = _package_available()
    reason = ""
    if not config.enabled:
        reason = "disabled"
    elif not package_available:
        reason = "depth_anything_3 package not installed"
    elif _model is None:
        reason = "enabled, not loaded"
    else:
        reason = "loaded"

    return {
        "feature": "depth_anything_v3",
        "enabled": config.enabled,
        "available": config.enabled and package_available,
        "loaded": _model is not None,
        "reason": reason,
        "model_id": config.model_id,
        "device": config.resolved_device,
        "requested_device": config.requested_device,
        "max_pixels": config.max_pixels,
        "source": config.source,
        "package": "depth_anything_3",
        "requires": "Depth Anything 3 optional Python package and model artifacts",
        "install_hint": (
            "Install Depth Anything 3 in the backend environment separately, then set "
            "DEPTH_ANYTHING_V3_ENABLED=true."
        ),
    }


def _get_model(config: DepthAnythingConfig) -> Any:
    global _model, _model_config_key
    _require_depth_anything_available(config)

    key = (config.model_id, config.resolved_device)
    if _model is not None and _model_config_key == key:
        return _model

    with _model_lock:
        if _model is not None and _model_config_key == key:
            return _model
        try:
            from depth_anything_3.api import DepthAnything3  # type: ignore

            model = DepthAnything3.from_pretrained(config.model_id)
            if hasattr(model, "to"):
                model = model.to(device=config.resolved_device)
            _model = model
            _model_config_key = key
            logger.info("[DEPTH] Depth Anything V3 loaded: %s (%s)", config.model_id, config.resolved_device)
            return _model
        except Exception as exc:  # pragma: no cover - depends on optional runtime
            _model = None
            _model_config_key = None
            raise DepthAnythingUnavailable(f"Depth Anything V3 load failed: {exc}") from exc


def _require_depth_anything_available(config: DepthAnythingConfig) -> None:
    if not config.enabled:
        raise DepthAnythingUnavailable("Depth Anything V3 is disabled.")
    if not _package_available():
        raise DepthAnythingUnavailable("depth_anything_3 package not installed.")


def _decode_image_data_url(image_b64: str, max_pixels: int):
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - transitive dependency guard
        raise DepthAnythingUnavailable("Pillow is required for depth image decoding.") from exc

    payload = image_b64.strip()
    if not payload:
        raise ValueError("image_b64 is required.")
    if "," in payload and payload.lower().startswith("data:"):
        payload = payload.split(",", 1)[1]
    try:
        raw = base64.b64decode(payload, validate=True)
    except Exception as exc:
        raise ValueError("image_b64 must be valid base64 image data.") from exc

    image = Image.open(BytesIO(raw)).convert("RGB")
    pixels = image.width * image.height
    if pixels > max_pixels:
        scale = (max_pixels / pixels) ** 0.5
        next_size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
        image = image.resize(next_size)
    return image


def _extract_depth_array(result: Any) -> np.ndarray:
    if isinstance(result, np.ndarray):
        return np.asarray(result, dtype=np.float32)

    candidates: list[Any] = []
    if isinstance(result, dict):
        candidates.extend(result.get(key) for key in ("depth", "depths", "depth_map", "depth_maps"))
    elif isinstance(result, (list, tuple)):
        candidates.extend(result)
    else:
        candidates.extend(getattr(result, key, None) for key in ("depth", "depths", "depth_map", "depth_maps"))

    for candidate in candidates:
        if candidate is None:
            continue
        if isinstance(candidate, dict):
            nested = _extract_depth_array(candidate)
            if nested.size:
                return nested
        elif isinstance(candidate, (list, tuple)) and candidate:
            nested = _extract_depth_array(candidate[0])
            if nested.size:
                return nested
        else:
            array = np.asarray(candidate, dtype=np.float32)
            if array.size:
                return array
    return np.asarray([], dtype=np.float32)


def estimate_depth_summary(image_b64: str) -> dict[str, Any]:
    config = resolve_depth_anything_config()
    _require_depth_anything_available(config)
    image = _decode_image_data_url(image_b64, config.max_pixels)
    model = _get_model(config)

    try:
        result = model.inference(image=[image], export_format="mini_npz")
    except Exception as exc:  # pragma: no cover - depends on optional runtime
        raise DepthAnythingUnavailable(f"Depth Anything V3 inference failed: {exc}") from exc

    depth = _extract_depth_array(result)
    if depth.size == 0:
        raise DepthAnythingUnavailable("Depth Anything V3 returned no depth map.")

    finite = depth[np.isfinite(depth)]
    if finite.size == 0:
        raise DepthAnythingUnavailable("Depth Anything V3 returned no finite depth values.")

    return {
        "model_id": config.model_id,
        "device": config.resolved_device,
        "requested_device": config.requested_device,
        "image_size": [image.width, image.height],
        "depth_shape": list(depth.shape),
        "stats": {
            "min": float(np.min(finite)),
            "max": float(np.max(finite)),
            "mean": float(np.mean(finite)),
            "std": float(np.std(finite)),
        },
    }
