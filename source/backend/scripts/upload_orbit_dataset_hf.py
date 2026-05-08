"""Upload an Orbit dataset export or retagged training folder to Hugging Face."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path


_DEFAULT_HF_TOKEN_PATH = Path(__file__).resolve().parents[3] / ".tools" / ".secrets" / "hf.txt"
_LOCAL_PATH_PATTERNS = (
    re.compile(r"[A-Za-z]:[\\/](?:Users|Windows|Program Files|ProgramData|workspaces|tmp)[\\/]", re.IGNORECASE),
    re.compile(r"[\\/](?:Users|home)[\\/][^\"'\s]+[\\/](?:OneDrive|Desktop|workspaces|tmp)[\\/]", re.IGNORECASE),
)
_IMAGE_REF_FILES = {
    "training_assets.jsonl": ("image",),
    "metadata.jsonl": ("file_name",),
    "retagged_assets.jsonl": ("file_name",),
    "review_queue.jsonl": ("file_name",),
}


def resolve_hf_token(secrets_path: Path | None = None) -> tuple[str, str]:
    """Resolve a Hugging Face token from env or the local secrets file."""
    env_token = os.environ.get("HF_TOKEN", "").strip() or os.environ.get("HUGGINGFACE_HUB_TOKEN", "").strip()
    if env_token:
        return env_token, "env"

    path = secrets_path or _DEFAULT_HF_TOKEN_PATH
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return stripped, "file"

    return "", "unavailable"


def build_upload_command(
    *,
    repo_id: str,
    dataset_dir: Path,
    revision: str | None = None,
    commit_message: str | None = None,
    create_pr: bool = False,
    large_folder: bool = False,
    delete_patterns: list[str] | None = None,
) -> list[str]:
    """Build an `hf` upload command without embedding the token."""
    clean_repo = repo_id.strip()
    if not clean_repo:
        raise ValueError("repo_id is required")
    dataset_dir = dataset_dir.resolve()
    if large_folder:
        command = ["hf", "upload-large-folder", clean_repo, str(dataset_dir), "--type", "dataset"]
    else:
        command = ["hf", "upload", clean_repo, str(dataset_dir), ".", "--type", "dataset"]
    if revision:
        command.extend(["--revision", revision])
    if commit_message and not large_folder:
        command.extend(["--commit-message", commit_message])
    if create_pr and not large_folder:
        command.append("--create-pr")
    if not large_folder:
        for pattern in delete_patterns or []:
            clean_pattern = pattern.strip()
            if clean_pattern:
                command.extend(["--delete", clean_pattern])
    return command


def build_repo_create_command(*, repo_id: str, private: bool) -> list[str]:
    command = ["hf", "repos", "create", repo_id.strip(), "--type", "dataset", "--exist-ok"]
    if private:
        command.append("--private")
    return command


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not path.exists():
        return rows
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}:{line_number} is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{path.name}:{line_number} must be a JSON object")
        rows.append(payload)
    return rows


def _has_local_path(value: str) -> bool:
    normalized = value.replace("\\\\", "\\").replace("\\/", "/")
    return any(pattern.search(normalized) for pattern in _LOCAL_PATH_PATTERNS)


def _collect_readme_config_paths(readme_path: Path) -> list[str]:
    if not readme_path.exists():
        return []
    paths: list[str] = []
    in_front_matter = False
    seen_front_matter = False
    for line in readme_path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "---":
            if not seen_front_matter:
                seen_front_matter = True
                in_front_matter = True
                continue
            if in_front_matter:
                break
        if in_front_matter:
            match = re.match(r"\s*path:\s*(.+?)\s*$", line)
            if match:
                paths.append(match.group(1).strip().strip("'\""))
    return paths


def validate_dataset_dir(dataset_dir: Path) -> list[str]:
    """Return upload-blocking dataset packaging issues."""
    dataset_dir = dataset_dir.resolve()
    issues: list[str] = []
    rows_by_name: dict[str, list[dict[str, object]]] = {}

    for path in sorted(dataset_dir.glob("*.jsonl")):
        try:
            rows_by_name[path.name] = _read_jsonl(path)
        except ValueError as exc:
            issues.append(str(exc))

    for path in sorted(dataset_dir.glob("*.json")) + sorted(dataset_dir.glob("*.jsonl")):
        text = path.read_text(encoding="utf-8")
        if _has_local_path(text):
            issues.append(f"{path.name} contains a local absolute path")

    referenced_images: set[str] = set()
    for file_name, fields in _IMAGE_REF_FILES.items():
        for row in rows_by_name.get(file_name, []):
            for field in fields:
                value = row.get(field)
                if isinstance(value, str) and value:
                    referenced_images.add(value)
                    if not (dataset_dir / value).is_file():
                        issues.append(f"{file_name} references missing asset: {value}")

    for row in rows_by_name.get("training_temporal_sequences.jsonl", []):
        images = row.get("images")
        if isinstance(images, list):
            for value in images:
                if isinstance(value, str) and value:
                    referenced_images.add(value)
                    if not (dataset_dir / value).is_file():
                        issues.append(f"training_temporal_sequences.jsonl references missing asset: {value}")

    for row in rows_by_name.get("temporal_sequences.jsonl", []):
        frames = row.get("ordered_frames")
        if isinstance(frames, list):
            for frame in frames:
                if isinstance(frame, dict):
                    value = frame.get("file_name")
                    if isinstance(value, str) and value:
                        referenced_images.add(value)
                        if not (dataset_dir / value).is_file():
                            issues.append(f"temporal_sequences.jsonl references missing asset: {value}")

    metadata_images = {
        str(row.get("file_name"))
        for row in rows_by_name.get("metadata.jsonl", [])
        if isinstance(row.get("file_name"), str) and row.get("file_name")
    }
    image_files = {
        path.relative_to(dataset_dir).as_posix()
        for path in (dataset_dir / "images").glob("*")
        if path.is_file()
    }
    if metadata_images:
        missing = sorted(metadata_images - image_files)
        orphaned = sorted(image_files - metadata_images)
        if missing:
            issues.append(f"metadata.jsonl has {len(missing)} missing image file(s)")
        if orphaned:
            issues.append(f"images/ has {len(orphaned)} orphan file(s) not present in metadata.jsonl")

    for config_path in _collect_readme_config_paths(dataset_dir / "README.md"):
        target = dataset_dir / config_path
        if not target.exists():
            issues.append(f"README.md config references missing file: {config_path}")
        elif target.suffix == ".jsonl" and not rows_by_name.get(target.name):
            issues.append(f"README.md config references empty JSONL file: {config_path}")

    return sorted(set(issues))


def run_hf_command(command: list[str], *, env: dict[str, str]) -> int:
    """Run an hf command and keep expected CLI failures readable."""
    try:
        subprocess.run(command, env=env, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"[Orbit] Hugging Face command failed with exit code {exc.returncode}: {' '.join(command)}")
        print(
            "[Orbit] For 403 repo-creation errors, grant dataset write/create permission "
            "or pre-create the dataset repo with write access."
        )
        return exc.returncode or 1
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload an Orbit dataset folder to Hugging Face Hub.")
    parser.add_argument("--dataset-dir", type=Path, required=True, help="Dataset export or retagged training directory.")
    parser.add_argument("--repo-id", required=True, help="Target Hugging Face dataset repo, e.g. username/lfm-orbit-data.")
    parser.add_argument("--revision", default=None, help="Optional branch or revision.")
    parser.add_argument("--commit-message", default="Update LFM Orbit dataset export", help="Commit message for `hf upload`.")
    parser.add_argument("--private", action="store_true", help="Create the dataset repo as private when --create-repo is used.")
    parser.add_argument("--create-repo", action="store_true", help="Create the dataset repo if it does not exist.")
    parser.add_argument("--create-pr", action="store_true", help="Upload as a Hub pull request.")
    parser.add_argument("--large-folder", action="store_true", help="Use resumable `hf upload-large-folder`.")
    parser.add_argument(
        "--delete",
        action="append",
        default=[],
        help="Glob pattern to delete from the Hub repo in the same commit. Repeat for multiple patterns.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the upload plan without running hf.")
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip local JSONL, asset-reference, path-leak, and README config validation before upload.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    dataset_dir = args.dataset_dir.resolve()
    if not dataset_dir.exists():
        raise FileNotFoundError(f"dataset directory not found: {dataset_dir}")

    token, source = resolve_hf_token()
    if not token and not args.dry_run:
        raise RuntimeError("HF token unavailable. Set HF_TOKEN or configure a local developer token file.")

    if not args.skip_validation:
        issues = validate_dataset_dir(dataset_dir)
        if issues:
            print("[Orbit] Dataset validation failed:")
            for issue in issues:
                print(f"[Orbit] - {issue}")
            return 2
        print("[Orbit] Dataset validation passed.")

    upload_command = build_upload_command(
        repo_id=args.repo_id,
        dataset_dir=dataset_dir,
        revision=args.revision,
        commit_message=args.commit_message,
        create_pr=args.create_pr,
        large_folder=args.large_folder,
        delete_patterns=args.delete,
    )
    repo_command = build_repo_create_command(repo_id=args.repo_id, private=args.private)

    print(f"[Orbit] Dataset directory: {dataset_dir}")
    print(f"[Orbit] HF token source: {source}")
    if args.dry_run:
        if args.create_repo:
            print("[Orbit] Would run:", " ".join(repo_command))
        print("[Orbit] Would run:", " ".join(upload_command))
        return 0

    env = dict(os.environ)
    env["HF_TOKEN"] = token
    if args.create_repo:
        create_code = run_hf_command(repo_command, env=env)
        if create_code:
            return create_code
    return run_hf_command(upload_command, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
