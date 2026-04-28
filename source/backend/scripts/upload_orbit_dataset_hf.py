"""Upload an Orbit dataset export or retagged training folder to Hugging Face."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


_DEFAULT_HF_TOKEN_PATH = Path(__file__).resolve().parents[3] / ".tools" / ".secrets" / "hf.txt"


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
    return command


def build_repo_create_command(*, repo_id: str, private: bool) -> list[str]:
    command = ["hf", "repos", "create", repo_id.strip(), "--type", "dataset", "--exist-ok"]
    if private:
        command.append("--private")
    return command


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
    parser.add_argument("--dry-run", action="store_true", help="Print the upload plan without running hf.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    dataset_dir = args.dataset_dir.resolve()
    if not dataset_dir.exists():
        raise FileNotFoundError(f"dataset directory not found: {dataset_dir}")

    token, source = resolve_hf_token()
    if not token and not args.dry_run:
        raise RuntimeError("HF token unavailable. Set HF_TOKEN or fill .tools/.secrets/hf.txt.")

    upload_command = build_upload_command(
        repo_id=args.repo_id,
        dataset_dir=dataset_dir,
        revision=args.revision,
        commit_message=args.commit_message,
        create_pr=args.create_pr,
        large_folder=args.large_folder,
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
