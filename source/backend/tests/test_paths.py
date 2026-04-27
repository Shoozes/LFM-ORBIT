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
