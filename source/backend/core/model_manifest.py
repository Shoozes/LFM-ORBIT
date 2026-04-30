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
        return payload


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _nested_text(payload: dict[str, Any], *keys: str) -> str | None:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _text(current)


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
