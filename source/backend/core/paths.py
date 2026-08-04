from __future__ import annotations

import os
import threading
import time
import uuid
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


def get_observation_store_dir() -> Path:
    return _env_path("CANOPY_SENTINEL_OBSERVATION_STORE_DIR", get_runtime_data_dir() / "observation-store")


def get_timelapse_cache_dir() -> Path:
    return _env_path("CANOPY_SENTINEL_TIMELAPSE_CACHE_DIR", get_runtime_data_dir() / "timelapse-cache")


def get_monitor_reports_dir() -> Path:
    return _env_path("CANOPY_SENTINEL_MONITOR_REPORTS_DIR", get_runtime_data_dir() / "monitor-reports")


def _temporary_path(path: Path) -> Path:
    """Give concurrent writers distinct temporary names, including on Windows."""
    suffix = f"{os.getpid()}-{threading.get_ident()}-{uuid.uuid4().hex}"
    return path.with_name(f".{path.name}.tmp-{suffix}")


def _replace_with_retry(temporary: Path, destination: Path) -> None:
    """Replace a destination, tolerating short Windows sharing violations."""
    retry_delays = (0.001, 0.005, 0.02, 0.05, 0.1)
    for attempt, delay in enumerate(retry_delays):
        try:
            os.replace(temporary, destination)
            return
        except PermissionError:
            if attempt == len(retry_delays) - 1:
                raise
            time.sleep(delay)


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Write a replaceable runtime artifact without exposing a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(path)
    try:
        temporary.write_bytes(payload)
        _replace_with_retry(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def atomic_write_text(path: Path, payload: str, *, encoding: str = "utf-8") -> None:
    """Write a replaceable text artifact without exposing a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(path)
    try:
        temporary.write_text(payload, encoding=encoding)
        _replace_with_retry(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
