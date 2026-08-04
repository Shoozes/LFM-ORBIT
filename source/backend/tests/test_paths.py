from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

from core import paths


def test_runtime_data_dir_defaults_to_repo_root(monkeypatch):
    monkeypatch.delenv("CANOPY_SENTINEL_RUNTIME_DIR", raising=False)

    assert paths.get_runtime_data_dir() == paths.REPO_ROOT / "runtime-data"
    assert paths.get_api_cache_path() == paths.REPO_ROOT / "runtime-data" / "api_cache.sqlite"
    assert paths.get_boundaries_dir() == paths.REPO_ROOT / "runtime-data" / "boundaries"
    assert paths.get_models_dir() == paths.REPO_ROOT / "runtime-data" / "models"


def test_runtime_data_dir_can_be_overridden(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "custom-runtime"
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.delenv("CANOPY_SENTINEL_API_CACHE_PATH", raising=False)
    monkeypatch.delenv("CANOPY_SENTINEL_BOUNDARIES_DIR", raising=False)
    monkeypatch.delenv("CANOPY_SENTINEL_MODELS_DIR", raising=False)

    assert paths.get_runtime_data_dir() == runtime_dir
    assert paths.get_api_cache_path() == runtime_dir / "api_cache.sqlite"
    assert paths.get_boundaries_dir() == runtime_dir / "boundaries"
    assert paths.get_models_dir() == runtime_dir / "models"


def test_specific_runtime_paths_can_be_overridden(monkeypatch, tmp_path):
    cache_path = tmp_path / "cache.sqlite"
    boundaries_dir = tmp_path / "boundaries"
    models_dir = tmp_path / "models"

    monkeypatch.setenv("CANOPY_SENTINEL_API_CACHE_PATH", str(cache_path))
    monkeypatch.setenv("CANOPY_SENTINEL_BOUNDARIES_DIR", str(boundaries_dir))
    monkeypatch.setenv("CANOPY_SENTINEL_MODELS_DIR", str(models_dir))

    assert paths.get_api_cache_path() == cache_path
    assert paths.get_boundaries_dir() == boundaries_dir
    assert paths.get_models_dir() == models_dir


def test_runtime_artifact_paths_follow_runtime_dir(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.delenv("CANOPY_SENTINEL_OBSERVATION_STORE_DIR", raising=False)
    monkeypatch.delenv("CANOPY_SENTINEL_TIMELAPSE_CACHE_DIR", raising=False)

    assert paths.get_observation_store_dir() == runtime_dir / "observation-store"
    assert paths.get_timelapse_cache_dir() == runtime_dir / "timelapse-cache"


def test_atomic_text_writes_do_not_share_windows_temp_names(monkeypatch, tmp_path):
    destination = tmp_path / "artifact.json"
    original_write_text = Path.write_text
    barrier = threading.Barrier(2)

    def gated_write_text(path: Path, payload: str, *args, **kwargs):
        if path.name.startswith(".artifact.json.tmp-"):
            barrier.wait(timeout=2)
        return original_write_text(path, payload, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", gated_write_text)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(paths.atomic_write_text, destination, payload)
            for payload in ('{"state": 1}', '{"state": 2}')
        ]
        for future in futures:
            future.result()

    assert destination.read_text(encoding="utf-8") in ('{"state": 1}', '{"state": 2}')


def test_atomic_text_write_retries_transient_replace_failures(monkeypatch, tmp_path):
    destination = tmp_path / "artifact.json"
    original_replace = paths.os.replace
    attempts = {"count": 0}

    def flaky_replace(source, target):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise PermissionError("transient sharing violation")
        return original_replace(source, target)

    monkeypatch.setattr(paths.os, "replace", flaky_replace)
    monkeypatch.setattr(paths.time, "sleep", lambda _: None)

    paths.atomic_write_text(destination, '{"state": 3}')

    assert attempts["count"] == 3
    assert destination.read_text(encoding="utf-8") == '{"state": 3}'
