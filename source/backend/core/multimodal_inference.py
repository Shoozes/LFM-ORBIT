from __future__ import annotations

import os
from typing import Any

from core.model_manifest import SatelliteModelArtifact, resolve_satellite_model_artifact


_VALID_BACKENDS = {"none", "llama_cpp_mmproj", "transformers_vlm"}


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
        return "llama_cpp_mmproj image adapter is not wired into Orbit runtime yet"
    return "transformers_vlm image adapter is not wired into Orbit runtime yet"


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

    # Status-only until an adapter actually passes image pixels into a model.
    image_runtime_enabled = False
    return {
        "feature": "image_conditioned_runtime",
        "feature_flag_enabled": enabled,
        "runtime_backend": backend,
        "runtime_backend_supported": backend in _VALID_BACKENDS,
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
        "runtime_inference_mode": "text_evidence_packet",
        "image_conditioned_runtime_reason": reason,
    }


def generate_with_image(
    prompt: str,
    *,
    image_path: str | None = None,
    image_b64: str | None = None,
    max_tokens: int = 256,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = multimodal_status()
    return {
        "available": False,
        "runtime_backend": status["runtime_backend"],
        "reason": status["image_conditioned_runtime_reason"],
        "response": "",
        "image_conditioned": False,
        "max_tokens": max_tokens,
        "provenance": {
            "image_conditioned": False,
            "model_path": status["model_path"],
            "mmproj_path": status["mmproj_path"],
            "hf_checkpoint_path": status["hf_checkpoint_path"],
            "image_path": image_path or "",
            "image_b64_present": bool(image_b64),
            "prompt_present": bool(prompt.strip()),
            "fallback_used": False,
            "runtime_inference_mode": status["runtime_inference_mode"],
            **(metadata or {}),
        },
    }
