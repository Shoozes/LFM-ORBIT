from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def _env_path(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    if raw:
        return Path(raw).expanduser()
    return default


def get_runtime_data_dir() -> Path:
    return _env_path("CANOPY_SENTINEL_RUNTIME_DIR", REPO_ROOT / "runtime-data")


def get_api_cache_path() -> Path:
    return _env_path("CANOPY_SENTINEL_API_CACHE_PATH", get_runtime_data_dir() / "api_cache.sqlite")


def get_boundaries_dir() -> Path:
    return _env_path("CANOPY_SENTINEL_BOUNDARIES_DIR", get_runtime_data_dir() / "boundaries")


def get_models_dir() -> Path:
    return _env_path("CANOPY_SENTINEL_MODELS_DIR", get_runtime_data_dir() / "models")
