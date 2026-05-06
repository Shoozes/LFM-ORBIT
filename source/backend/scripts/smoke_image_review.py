"""Smoke-test the optional Liquid image-conditioned review runtime.

This script is intentionally opt-in. CI-safe unit tests monkeypatch the adapter;
this command verifies the real configured runtime against a retained seeded frame
and a blank control image.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from core.multimodal_inference import generate_with_image, multimodal_status


ROOT = Path(__file__).resolve().parents[1]
SEEDED_DATA_DIR = ROOT / "assets" / "seeded_data"
DEFAULT_VISUAL_MODEL = "LiquidAI/LFM2.5-VL-450M"
_STATUS_PATH_KEYS = {
    "path",
    "model_dir",
    "model_path",
    "manifest_path",
    "mmproj_path",
    "source_handoff_path",
    "training_result_manifest_path",
    "hf_checkpoint_path",
    "lora_adapter_path",
    "readme_path",
}


def _public_status_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        clean: dict[str, Any] = {}
        for key, value in payload.items():
            text_key = str(key)
            if text_key in _STATUS_PATH_KEYS and isinstance(value, str):
                value = value.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
            clean[text_key] = _public_status_payload(value)
        return clean
    if isinstance(payload, list):
        return [_public_status_payload(item) for item in payload]
    return payload


def _json(payload: dict[str, Any], *, exit_code: int = 0) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return exit_code


def _image_to_data_url(image: Image.Image) -> str:
    out = BytesIO()
    image.convert("RGB").save(out, format="PNG")
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii")


def _load_seeded_frame_data_url() -> str:
    try:
        import imageio.v3 as iio
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(f"imageio is required to extract a seeded review frame: {exc}") from exc

    candidates = sorted(SEEDED_DATA_DIR.glob("*.webm"))
    if not candidates:
        raise RuntimeError(f"no seeded WebM fixtures found under {SEEDED_DATA_DIR}")

    last_error: Exception | None = None
    for path in candidates:
        try:
            frame = next(iter(iio.imiter(path, plugin="pyav")))
            image = Image.fromarray(frame).convert("RGB")
            return _image_to_data_url(image)
        except Exception as exc:  # pragma: no cover - fixture/plugin dependent
            last_error = exc
            continue

    raise RuntimeError(f"unable to decode a seeded WebM frame: {last_error}")


def _blank_control_data_url() -> str:
    return _image_to_data_url(Image.new("RGB", (96, 96), (0, 0, 0)))


def _configured_for_runtime() -> tuple[bool, str]:
    enabled = os.getenv("ORBIT_IMAGE_CONDITIONED_INFERENCE", "").strip().lower() in {"1", "true", "yes", "on"}
    backend = os.getenv("ORBIT_IMAGE_INFERENCE_BACKEND", "none").strip().lower()
    if not enabled:
        return False, "ORBIT_IMAGE_CONDITIONED_INFERENCE is not true"
    if backend != "transformers_vlm":
        return False, "ORBIT_IMAGE_INFERENCE_BACKEND is not transformers_vlm"
    return True, "configured"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the optional image-conditioned review smoke test.")
    parser.add_argument(
        "--require-present",
        action="store_true",
        help="Exit nonzero unless the real Liquid image review runtime succeeds.",
    )
    parser.add_argument(
        "--prompt",
        default="Describe visible land-cover change. Do not infer cause beyond visible evidence.",
    )
    args = parser.parse_args()

    configured, reason = _configured_for_runtime()
    if not configured:
        return _json(
            {
                "available": False,
                "image_conditioned": False,
                "fallback_used": False,
                "reason": reason,
                "status": _public_status_payload(multimodal_status()),
            },
            exit_code=1 if args.require_present else 0,
        )

    try:
        seeded_image = _load_seeded_frame_data_url()
    except Exception as exc:
        return _json(
            {
                "available": False,
                "image_conditioned": False,
                "fallback_used": False,
                "reason": str(exc),
            },
            exit_code=1 if args.require_present else 0,
        )

    real_review = generate_with_image(
        args.prompt,
        image_b64=seeded_image,
        max_tokens=int(os.getenv("ORBIT_IMAGE_REVIEW_MAX_TOKENS", "160") or 160),
        metadata={
            "frame_id": "seeded_review_frame",
            "runtime_truth_mode": "replay",
            "imagery_origin": "cached_api",
            "scoring_basis": "context_timelapse",
        },
    )
    blank_review = generate_with_image(
        args.prompt,
        image_b64=_blank_control_data_url(),
        max_tokens=32,
        metadata={
            "frame_id": "blank_control",
            "runtime_truth_mode": "replay",
            "imagery_origin": "blank_control",
            "scoring_basis": "fallback_none",
        },
    )

    expected_model = os.getenv("ORBIT_IMAGE_VLM_MODEL", DEFAULT_VISUAL_MODEL).strip() or DEFAULT_VISUAL_MODEL
    passed = (
        bool(real_review.get("image_conditioned"))
        and real_review.get("visual_model") == expected_model
        and (bool(blank_review.get("abstained")) or not bool(blank_review.get("image_conditioned")))
    )
    payload = {
        "passed": passed,
        "fallback_used": False,
        "visual_model": real_review.get("visual_model", ""),
        "real_frame": {
            "available": real_review.get("available"),
            "image_conditioned": real_review.get("image_conditioned"),
            "reason": real_review.get("reason"),
            "response_preview": str(real_review.get("response") or "")[:220],
        },
        "blank_control": {
            "available": blank_review.get("available"),
            "image_conditioned": blank_review.get("image_conditioned"),
            "abstained": blank_review.get("abstained"),
            "reason": blank_review.get("reason"),
        },
        "status": _public_status_payload(multimodal_status()),
    }
    return _json(payload, exit_code=0 if passed else 1)


if __name__ == "__main__":
    raise SystemExit(main())
