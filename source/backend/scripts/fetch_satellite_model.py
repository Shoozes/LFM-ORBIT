"""Fetch a published satellite model artifact for LFM Orbit.

Examples:
    python source/backend/scripts/fetch_satellite_model.py ^
        --repo-id Shoozes/lfm2.5-450m-vl-orbit-satellite

    python source/backend/scripts/fetch_satellite_model.py ^
        --source-manifest C:\\path\\to\\model-bundle\\orbit_model_handoff.json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from contextlib import suppress
from pathlib import Path
from typing import Any

from core.model_manifest import (
    DEFAULT_MODEL_FILENAME,
    DEFAULT_MODEL_REPO_ID,
    DEFAULT_MODEL_SUBDIR,
    DEFAULT_README_FILENAME,
    DEFAULT_REVISION,
    DEFAULT_SOURCE_HANDOFF_FILENAME,
    write_runtime_model_manifest,
)
from core.paths import get_models_dir


DEFAULT_HANDOFF_MANIFEST_FILENAME = "orbit_model_handoff.json"
DOWNLOAD_CHUNK_SIZE = 1024 * 1024


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


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Manifest must be a JSON object: {path}")
    return payload


def _build_resolve_url(repo_id: str, revision: str, filename: str) -> str:
    return f"https://huggingface.co/{repo_id}/resolve/{revision}/{filename}"


def _request_headers(token: str | None) -> dict[str, str]:
    headers = {"User-Agent": "lfm-orbit-fetch/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _read_json_url(url: str, token: str | None) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=_request_headers(token))
    with urllib.request.urlopen(request) as response:  # nosec: B310
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Manifest must be a JSON object: {url}")
    return payload


def _download_file(url: str, target_path: Path, token: str | None) -> None:
    request = urllib.request.Request(url, headers=_request_headers(token))
    target_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f"{target_path.name}.",
        suffix=".part",
        dir=str(target_path.parent),
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        with urllib.request.urlopen(request) as response, tmp_path.open("wb") as handle:  # nosec: B310
            while True:
                chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                handle.write(chunk)
        os.replace(tmp_path, target_path)
    except Exception:
        with suppress(OSError):
            tmp_path.unlink(missing_ok=True)
        raise


def _safe_relative_path(value: str | Path, *, label: str) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        raise ValueError(f"{label} must stay relative: {value}")
    return path


def _safe_target_path(base_dir: Path, relative_path: str | Path, *, label: str) -> Path:
    rel_path = _safe_relative_path(relative_path, label=label)
    base_dir = base_dir.resolve()
    candidate = (base_dir / rel_path).resolve()
    try:
        candidate.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError(f"{label} escapes target directory: {relative_path}") from exc
    return candidate


def _try_load_remote_handoff_manifest(
    repo_id: str,
    revision: str,
    filename: str,
    token: str | None,
) -> dict[str, Any] | None:
    try:
        return _read_json_url(_build_resolve_url(repo_id, revision, filename), token)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def _write_source_handoff(target_dir: Path, payload: dict[str, Any]) -> Path:
    target_path = target_dir / DEFAULT_SOURCE_HANDOFF_FILENAME
    target_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target_path


def _copy_bundle_member(source_root: Path, relative_path: str | None, target_dir: Path) -> Path | None:
    text = _text(relative_path)
    if not text:
        return None
    rel_path = _safe_relative_path(text, label="bundle member")
    source_root = source_root.resolve()
    source_path = (source_root / rel_path).resolve()
    try:
        source_path.relative_to(source_root)
    except ValueError as exc:
        raise ValueError(f"bundle member escapes source bundle: {relative_path}") from exc
    if not source_path.exists():
        return None
    target_path = _safe_target_path(target_dir, rel_path, label="bundle member")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)
    return target_path


def _download_repo_member(
    repo_id: str,
    revision: str,
    relative_path: str | None,
    target_dir: Path,
    token: str | None,
    *,
    required: bool,
) -> Path | None:
    text = _text(relative_path)
    if not text:
        return None
    rel_path = _safe_relative_path(text, label="repo member")
    target_path = _safe_target_path(target_dir, rel_path, label="repo member")
    try:
        _download_file(
            _build_resolve_url(repo_id, revision, rel_path.as_posix()),
            target_path,
            token,
        )
    except urllib.error.HTTPError as exc:
        if not required and exc.code == 404:
            return None
        raise
    return target_path


def _copy_local_bundle_metadata(
    *,
    source_manifest_path: Path,
    handoff_payload: dict[str, Any],
    training_result_manifest: str | None,
    target_dir: Path,
) -> dict[str, Path]:
    copied: dict[str, Path] = {"source_handoff": _write_source_handoff(target_dir, handoff_payload)}
    source_root = source_manifest_path.parent.resolve()
    training_path = _copy_bundle_member(source_root, training_result_manifest, target_dir)
    if training_result_manifest and training_path is None:
        raise FileNotFoundError(
            f"training_result_manifest is declared in the handoff but missing from the bundle: {training_result_manifest}"
        )
    if training_path is not None:
        copied["training_result_manifest"] = training_path
    readme_path = _copy_bundle_member(source_root, DEFAULT_README_FILENAME, target_dir)
    if readme_path is not None:
        copied["readme"] = readme_path
    return copied


def _download_remote_bundle_metadata(
    *,
    repo_id: str,
    revision: str,
    handoff_payload: dict[str, Any],
    training_result_manifest: str | None,
    target_dir: Path,
    token: str | None,
) -> dict[str, Path]:
    copied: dict[str, Path] = {"source_handoff": _write_source_handoff(target_dir, handoff_payload)}
    training_path = _download_repo_member(
        repo_id,
        revision,
        training_result_manifest,
        target_dir,
        token,
        required=bool(training_result_manifest),
    )
    if training_path is not None:
        copied["training_result_manifest"] = training_path
    readme_path = _download_repo_member(
        repo_id,
        revision,
        DEFAULT_README_FILENAME,
        target_dir,
        token,
        required=False,
    )
    if readme_path is not None:
        copied["readme"] = readme_path
    return copied


def _source_manifest_values(payload: dict[str, Any]) -> dict[str, str | None]:
    return {
        "repo_id": (
            _text(payload.get("repo_id"))
            or _nested_text(payload, "source", "repo_id")
        ),
        "revision": (
            _text(payload.get("revision"))
            or _nested_text(payload, "source", "revision")
            or DEFAULT_REVISION
        ),
        "model_filename": (
            _text(payload.get("model_filename"))
            or _text(payload.get("filename"))
            or _nested_text(payload, "runtime", "model_filename")
            or DEFAULT_MODEL_FILENAME
        ),
        "mmproj_filename": (
            _text(payload.get("mmproj_filename"))
            or _nested_text(payload, "runtime", "mmproj_filename")
        ),
        "model_subdir": (
            _text(payload.get("model_subdir"))
            or _nested_text(payload, "runtime", "model_subdir")
            or DEFAULT_MODEL_SUBDIR
        ),
        "base_model": (
            _text(payload.get("base_model"))
            or _nested_text(payload, "artifact", "base_model")
        ),
        "quantization": (
            _text(payload.get("quantization"))
            or _nested_text(payload, "artifact", "quantization")
        ),
        "task": (
            _text(payload.get("task"))
            or _nested_text(payload, "artifact", "task")
        ),
        "training_result_manifest": (
            _text(payload.get("training_result_manifest"))
            or _nested_text(payload, "producer", "training_result_manifest")
        ),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch a published satellite model into Orbit runtime-data.")
    parser.add_argument("--source-manifest", type=Path, default=None, help="Optional local handoff manifest.")
    parser.add_argument(
        "--handoff-manifest-filename",
        default=DEFAULT_HANDOFF_MANIFEST_FILENAME,
        help="Repo-relative handoff manifest to try first when --repo-id is provided (default: orbit_model_handoff.json).",
    )
    parser.add_argument(
        "--repo-id",
        default=os.getenv("LFM_MODEL_REPO_ID") or os.getenv("CANOPY_SENTINEL_MODEL_REPO_ID") or DEFAULT_MODEL_REPO_ID,
        help=f"Hugging Face model repo ID (default: {DEFAULT_MODEL_REPO_ID}).",
    )
    parser.add_argument(
        "--revision",
        default=os.getenv("LFM_MODEL_REVISION") or os.getenv("CANOPY_SENTINEL_MODEL_REVISION"),
        help="Repo revision, tag, or branch.",
    )
    parser.add_argument("--model-filename", default=None, help="Primary GGUF filename.")
    parser.add_argument("--mmproj-filename", default=None, help="Optional mmproj filename.")
    parser.add_argument("--model-subdir", default=None, help="Runtime model subdirectory under runtime-data/models.")
    parser.add_argument("--base-model", default=None, help="Optional base model label for the local manifest.")
    parser.add_argument("--quantization", default=None, help="Optional quantization label for the local manifest.")
    parser.add_argument("--task", default=None, help="Optional task label for the local manifest.")
    parser.add_argument(
        "--token-env",
        default="HF_TOKEN",
        help="Environment variable to read for Hugging Face auth (default: HF_TOKEN).",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned work without downloading.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    token = _text(os.getenv(args.token_env))

    manifest_values: dict[str, str | None] = {}
    source_manifest_path = args.source_manifest.resolve() if args.source_manifest else None
    source_handoff_payload: dict[str, Any] | None = None
    if source_manifest_path:
        source_handoff_payload = _load_json(source_manifest_path)
        manifest_values = _source_manifest_values(source_handoff_payload)

    remote_handoff_payload: dict[str, Any] | None = None
    if source_handoff_payload is None and args.repo_id:
        hinted_revision = args.revision or DEFAULT_REVISION
        remote_handoff_payload = _try_load_remote_handoff_manifest(
            str(args.repo_id),
            str(hinted_revision),
            str(args.handoff_manifest_filename),
            token,
        )
        if remote_handoff_payload:
            manifest_values = _source_manifest_values(remote_handoff_payload)

    repo_id = args.repo_id or manifest_values.get("repo_id")
    revision = args.revision or manifest_values.get("revision") or DEFAULT_REVISION
    model_filename = args.model_filename or manifest_values.get("model_filename") or DEFAULT_MODEL_FILENAME
    mmproj_filename = args.mmproj_filename or manifest_values.get("mmproj_filename")
    model_subdir = args.model_subdir or manifest_values.get("model_subdir") or DEFAULT_MODEL_SUBDIR
    base_model = args.base_model or manifest_values.get("base_model")
    quantization = args.quantization or manifest_values.get("quantization")
    task = args.task or manifest_values.get("task")
    training_result_manifest = manifest_values.get("training_result_manifest")

    if not repo_id:
        print("Missing repo id. Provide --repo-id or a --source-manifest with repo_id.", file=sys.stderr)
        return 1

    try:
        target_dir = _safe_target_path(get_models_dir(), str(model_subdir), label="model_subdir")
        model_target = _safe_target_path(target_dir, str(model_filename), label="model_filename")
        mmproj_target = (
            _safe_target_path(target_dir, str(mmproj_filename), label="mmproj_filename")
            if mmproj_filename
            else None
        )
    except ValueError as exc:
        print(f"[Orbit] Invalid handoff path: {exc}", file=sys.stderr)
        return 1

    print(f"[Orbit] Repo: {repo_id}@{revision}")
    print(f"[Orbit] Target dir: {target_dir}")
    print(f"[Orbit] Model file: {model_target.relative_to(target_dir)}")
    if mmproj_target:
        print(f"[Orbit] mmproj file: {mmproj_target.relative_to(target_dir)}")
    if remote_handoff_payload:
        print(f"[Orbit] Resolved canonical handoff manifest: {args.handoff_manifest_filename}")

    if not args.force:
        existing = [path for path in (model_target, mmproj_target) if path and path.exists()]
        if existing:
            print(
                "[Orbit] Refusing to overwrite existing file(s) without --force: "
                + ", ".join(str(path) for path in existing),
                file=sys.stderr,
            )
            return 1

    if args.dry_run:
        return 0

    model_url = _build_resolve_url(str(repo_id), str(revision), Path(str(model_filename)).as_posix())
    try:
        _download_file(model_url, model_target, token)
        print(f"[Orbit] Downloaded {model_target}")
        if mmproj_target and mmproj_filename:
            mmproj_url = _build_resolve_url(str(repo_id), str(revision), Path(str(mmproj_filename)).as_posix())
            _download_file(mmproj_url, mmproj_target, token)
            print(f"[Orbit] Downloaded {mmproj_target}")
    except urllib.error.HTTPError as exc:
        print(f"[Orbit] Download failed: {exc.code} {exc.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"[Orbit] Network error: {exc}", file=sys.stderr)
        return 1

    provenance_files: dict[str, Path] = {}
    try:
        if source_handoff_payload and source_manifest_path:
            provenance_files = _copy_local_bundle_metadata(
                source_manifest_path=source_manifest_path,
                handoff_payload=source_handoff_payload,
                training_result_manifest=training_result_manifest,
                target_dir=target_dir,
            )
        elif remote_handoff_payload:
            provenance_files = _download_remote_bundle_metadata(
                repo_id=str(repo_id),
                revision=str(revision),
                handoff_payload=remote_handoff_payload,
                training_result_manifest=training_result_manifest,
                target_dir=target_dir,
                token=token,
            )
    except (FileNotFoundError, ValueError, urllib.error.HTTPError, urllib.error.URLError) as exc:
        print(f"[Orbit] Failed to preserve bundle metadata: {exc}", file=sys.stderr)
        return 1

    for label, path in provenance_files.items():
        print(f"[Orbit] Preserved {label}: {path}")

    runtime_manifest = write_runtime_model_manifest(
        target_dir,
        repo_id=str(repo_id),
        revision=str(revision),
        model_filename=str(Path(str(model_filename)).as_posix()),
        model_subdir=str(model_subdir),
        base_model=base_model,
        quantization=quantization,
        task=task,
        training_result_manifest=training_result_manifest,
        mmproj_filename=str(Path(str(mmproj_filename)).as_posix()) if mmproj_filename else None,
    )
    print(f"[Orbit] Wrote runtime manifest to {runtime_manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
