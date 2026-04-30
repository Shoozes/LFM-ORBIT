from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from core.paths import get_models_dir


DEFAULT_MODEL_SUBDIR = "lfm2.5-vlm-450m"
DEFAULT_MODEL_FILENAME = "LFM2.5-VL-450M-Q4_0.gguf"
DEFAULT_MODEL_REPO_ID = "Shoozes/lfm2.5-450m-vl-orbit-satellite"
DEFAULT_MANIFEST_FILENAME = "model_manifest.json"
DEFAULT_SOURCE_HANDOFF_FILENAME = "source_handoff.json"
DEFAULT_README_FILENAME = "README.md"
DEFAULT_REVISION = "main"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SatelliteModelArtifact:
    manifest_path: Path
    model_dir: Path
    model_filename: str
    model_path: Path
    repo_id: str | None = None
    revision: str = DEFAULT_REVISION
    source: str = "local"
    base_model: str | None = None
    quantization: str | None = None
    task: str | None = None
    training_result_manifest: str | None = None
    mmproj_filename: str | None = None
    mmproj_path: Path | None = None
    source_handoff_path: Path | None = None
    training_result_manifest_path: Path | None = None
    readme_path: Path | None = None

    def training_status_dict(self) -> dict[str, Any]:
        payload = load_model_manifest(self.training_result_manifest_path) if self.training_result_manifest_path else {}
        manifest_present = bool(self.training_result_manifest_path and self.training_result_manifest_path.exists())

        train_rows = _manifest_int(
            payload,
            "train_rows",
            "training_rows",
            "dataset_summary.rows",
            "dataset_summary.train_rows",
            "row_counts.train_rows",
            "counts.train_rows",
        )
        multimodal_rows = _manifest_int(
            payload,
            "multimodal_rows",
            "image_text_rows",
            "dataset_summary.multimodal_rows",
            "dataset_summary.image_text_rows",
            "row_counts.multimodal_rows",
            "counts.multimodal_rows",
        )
        image_blocks = _manifest_int(
            payload,
            "image_blocks",
            "image_block_count",
            "dataset_summary.image_blocks",
            "dataset_summary.image_block_count",
            "row_counts.image_blocks",
            "counts.image_blocks",
        )
        eval_rows = _manifest_int(
            payload,
            "eval_rows",
            "evaluation_rows",
            "evaluation_metadata.eval_rows",
            "dataset_summary.eval_rows",
            "row_counts.eval_rows",
            "counts.eval_rows",
        )
        method = _manifest_text(payload, "training_method", "method", "training.method", "run.method", "trainer.method")
        base_model = (
            _manifest_text(
                payload,
                "base_model",
                "source_model",
                "training.source_model_path",
                "model.base_model",
                "run.base_model",
            )
            or self.base_model
        )
        manifest_modality = (_manifest_text(payload, "training_modality", "modality", "data.modality") or "").lower()

        if image_blocks > 0 or multimodal_rows > 0 or manifest_modality in {"image_text", "multimodal", "vlm"}:
            training_modality = "image_text"
        elif manifest_present:
            training_modality = manifest_modality or "text"
        else:
            training_modality = "unknown"

        hf_checkpoint_path = _training_asset_path(
            self.model_dir,
            payload,
            (
                "hf_checkpoint",
                "hf_checkpoint_path",
                "hf_checkpoint_dir",
                "artifacts.hf_checkpoint",
                "outputs.hf_checkpoint",
            ),
            ("hf-checkpoint", "hf_checkpoint"),
        )
        lora_adapter_path = _training_asset_path(
            self.model_dir,
            payload,
            (
                "lora_adapter",
                "lora_adapter_path",
                "lora_adapter_dir",
                "artifacts.lora_adapter",
                "outputs.lora_adapter",
            ),
            ("lora-adapter", "lora_adapter"),
        )

        return {
            "training_method": method or "",
            "training_base_model": base_model or "",
            "training_modality": training_modality,
            "image_training_verified": bool(manifest_present and image_blocks > 0),
            "training_train_rows": train_rows,
            "training_multimodal_rows": multimodal_rows,
            "training_image_blocks": image_blocks,
            "training_eval_rows": eval_rows,
            "hf_checkpoint_path": str(hf_checkpoint_path) if hf_checkpoint_path else "",
            "hf_checkpoint_present": bool(hf_checkpoint_path and hf_checkpoint_path.exists()),
            "lora_adapter_path": str(lora_adapter_path) if lora_adapter_path else "",
            "lora_adapter_present": bool(lora_adapter_path and lora_adapter_path.exists()),
        }

    def to_status_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["manifest_path"] = str(self.manifest_path)
        payload["model_dir"] = str(self.model_dir)
        payload["model_path"] = str(self.model_path)
        payload["mmproj_path"] = str(self.mmproj_path) if self.mmproj_path else ""
        payload["source_handoff_path"] = str(self.source_handoff_path) if self.source_handoff_path else ""
        payload["training_result_manifest_path"] = (
            str(self.training_result_manifest_path) if self.training_result_manifest_path else ""
        )
        payload["readme_path"] = str(self.readme_path) if self.readme_path else ""
        payload["mmproj_present"] = bool(self.mmproj_path and self.mmproj_path.exists())
        payload["source_handoff_present"] = bool(self.source_handoff_path and self.source_handoff_path.exists())
        payload["training_result_manifest_present"] = bool(
            self.training_result_manifest_path and self.training_result_manifest_path.exists()
        )
        payload["readme_present"] = bool(self.readme_path and self.readme_path.exists())
        payload.update(self.training_status_dict())
        payload["runtime_inference_mode"] = "text_evidence_packet"
        payload["image_conditioned_runtime_enabled"] = False
        payload["image_conditioned_runtime_reason"] = "direct image runtime adapter is not wired"
        return payload


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _nested_text(payload: dict[str, Any], *keys: str) -> str | None:
    return _text(_nested_value(payload, *keys))


def _nested_value(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _manifest_value(payload: dict[str, Any], path: str) -> Any:
    if not payload:
        return None
    return _nested_value(payload, *[part for part in path.split(".") if part])


def _manifest_text(payload: dict[str, Any], *paths: str) -> str | None:
    for path in paths:
        text = _text(_manifest_value(payload, path))
        if text is not None:
            return text
    return None


def _int(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value))
    text = str(value).strip()
    if not text:
        return 0
    try:
        return max(0, int(float(text)))
    except ValueError:
        return 0


def _manifest_int(payload: dict[str, Any], *paths: str) -> int:
    for path in paths:
        value = _manifest_value(payload, path)
        if value not in (None, ""):
            return _int(value)
    return 0


def _training_asset_path(
    base_dir: Path,
    payload: dict[str, Any],
    manifest_paths: tuple[str, ...],
    default_names: tuple[str, ...],
) -> Path | None:
    explicit = _manifest_text(payload, *manifest_paths)
    explicit_path = _resolve_local_artifact_path(base_dir, explicit)
    if explicit_path is not None:
        return explicit_path
    for name in default_names:
        candidate = base_dir / name
        if candidate.exists():
            return candidate
    return None


def _manifest_env_path() -> Path | None:
    raw = _text(os.getenv("CANOPY_SENTINEL_MODEL_MANIFEST"))
    return Path(raw).expanduser() if raw else None


def _resolve_manifest_path(default_subdir: str) -> Path:
    env_path = _manifest_env_path()
    if env_path is not None:
        return env_path
    return get_models_dir() / default_subdir / DEFAULT_MANIFEST_FILENAME


def _resolve_local_artifact_path(base_dir: Path, value: str | None) -> Path | None:
    text = _text(value)
    if not text:
        return None
    path = Path(text).expanduser()
    if path.is_absolute():
        return path
    candidate = (base_dir / path).resolve()
    try:
        candidate.relative_to(base_dir.resolve())
    except ValueError:
        return None
    return candidate


def load_model_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_satellite_model_artifact() -> SatelliteModelArtifact:
    default_subdir = _text(os.getenv("CANOPY_SENTINEL_MODEL_SUBDIR")) or DEFAULT_MODEL_SUBDIR
    manifest_path = _resolve_manifest_path(default_subdir)
    payload = load_model_manifest(manifest_path)

    model_subdir = (
        _text(os.getenv("CANOPY_SENTINEL_MODEL_SUBDIR"))
        or _text(payload.get("model_subdir"))
        or _nested_text(payload, "runtime", "model_subdir")
        or default_subdir
    )

    model_dir_raw = (
        _text(payload.get("model_dir"))
        or _nested_text(payload, "runtime", "model_dir")
    )
    if model_dir_raw:
        model_dir = Path(model_dir_raw).expanduser()
        if not model_dir.is_absolute():
            model_dir = (manifest_path.parent / model_dir).resolve()
    else:
        model_dir = get_models_dir() / model_subdir

    model_filename = (
        _text(os.getenv("CANOPY_SENTINEL_MODEL_FILENAME"))
        or _text(payload.get("model_filename"))
        or _text(payload.get("filename"))
        or _nested_text(payload, "runtime", "model_filename")
        or DEFAULT_MODEL_FILENAME
    )

    mmproj_filename = (
        _text(os.getenv("CANOPY_SENTINEL_MODEL_MMPROJ_FILENAME"))
        or _text(payload.get("mmproj_filename"))
        or _nested_text(payload, "runtime", "mmproj_filename")
    )

    repo_id = (
        _text(os.getenv("CANOPY_SENTINEL_MODEL_REPO_ID"))
        or _text(payload.get("repo_id"))
        or _nested_text(payload, "source", "repo_id")
        or _nested_text(payload, "huggingface", "repo_id")
    )

    revision = (
        _text(os.getenv("CANOPY_SENTINEL_MODEL_REVISION"))
        or _text(payload.get("revision"))
        or _nested_text(payload, "source", "revision")
        or DEFAULT_REVISION
    )

    source = (
        _nested_text(payload, "source", "kind")
        or _text(payload.get("source"))
        or ("huggingface" if repo_id else "local")
    )

    base_model = (
        _text(payload.get("base_model"))
        or _nested_text(payload, "artifact", "base_model")
    )
    quantization = (
        _text(payload.get("quantization"))
        or _nested_text(payload, "artifact", "quantization")
    )
    task = (
        _text(payload.get("task"))
        or _nested_text(payload, "artifact", "task")
    )
    training_result_manifest = (
        _text(payload.get("training_result_manifest"))
        or _nested_text(payload, "producer", "training_result_manifest")
    )

    mmproj_path = model_dir / mmproj_filename if mmproj_filename else None
    source_handoff_path = model_dir / DEFAULT_SOURCE_HANDOFF_FILENAME
    training_result_manifest_path = _resolve_local_artifact_path(model_dir, training_result_manifest)
    readme_path = model_dir / DEFAULT_README_FILENAME
    return SatelliteModelArtifact(
        manifest_path=manifest_path,
        model_dir=model_dir,
        model_filename=model_filename,
        model_path=model_dir / model_filename,
        repo_id=repo_id,
        revision=revision,
        source=source,
        base_model=base_model,
        quantization=quantization,
        task=task,
        training_result_manifest=training_result_manifest,
        mmproj_filename=mmproj_filename,
        mmproj_path=mmproj_path,
        source_handoff_path=source_handoff_path,
        training_result_manifest_path=training_result_manifest_path,
        readme_path=readme_path,
    )


def write_runtime_model_manifest(
    target_dir: Path,
    *,
    repo_id: str | None,
    revision: str = DEFAULT_REVISION,
    model_filename: str,
    model_subdir: str = DEFAULT_MODEL_SUBDIR,
    source: str = "huggingface",
    base_model: str | None = None,
    quantization: str | None = None,
    task: str | None = None,
    training_result_manifest: str | None = None,
    mmproj_filename: str | None = None,
    producer: dict[str, Any] | None = None,
) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = target_dir / DEFAULT_MANIFEST_FILENAME
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "kind": source,
            "repo_id": repo_id or "",
            "revision": revision,
        },
        "runtime": {
            "model_subdir": model_subdir,
            "model_filename": model_filename,
            "mmproj_filename": mmproj_filename or "",
        },
        "artifact": {
            "base_model": base_model or "",
            "quantization": quantization or "",
            "task": task or "",
        },
        "repo_id": repo_id or "",
        "revision": revision,
        "model_subdir": model_subdir,
        "model_filename": model_filename,
        "mmproj_filename": mmproj_filename or "",
        "base_model": base_model or "",
        "quantization": quantization or "",
        "task": task or "",
        "training_result_manifest": training_result_manifest or "",
    }
    if producer:
        payload["producer"] = producer
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return manifest_path
