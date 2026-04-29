from core.config import (
    PROVIDER_SIMSAT_MAPBOX,
    get_runtime_mode_summary,
    imagery_origin_for_source,
    is_imagery_backed_scoring_enabled,
    runtime_truth_mode_for_source,
    scoring_basis_for_source,
    resolve_active_provider,
)
from core.depth_anything import (
    DEFAULT_DEPTH_ANYTHING_V3_MODEL,
    clear_depth_anything_runtime_override,
    get_depth_anything_status,
    resolve_depth_anything_config,
    set_depth_anything_enabled,
)


def test_runtime_mode_summary_matches_imagery_backed_helper():
    summary = get_runtime_mode_summary()

    assert summary["imagery_backed_scoring_enabled"] is is_imagery_backed_scoring_enabled()
    assert summary["runtime_truth_mode"] in {"realtime", "replay", "fallback", "unknown"}
    assert isinstance(summary["imagery_origin"], str)
    assert isinstance(summary["scoring_basis"], str)


def test_truth_origin_and_scoring_basis_are_separate():
    assert runtime_truth_mode_for_source("nasa_gibs") == "realtime"
    assert imagery_origin_for_source("nasa_gibs") == "nasa_gibs"
    assert scoring_basis_for_source("nasa_gibs") == "visual_only"

    assert runtime_truth_mode_for_source("seeded_sentinelhub_replay") == "replay"
    assert imagery_origin_for_source("seeded_sentinelhub_replay") == "cached_api"
    assert scoring_basis_for_source("seeded_sentinelhub_replay") == "visual_only"

    assert runtime_truth_mode_for_source("sentinelhub_direct_imagery") == "realtime"
    assert imagery_origin_for_source("sentinelhub_direct_imagery") == "sentinelhub"
    assert scoring_basis_for_source("sentinelhub_direct_imagery") == "multispectral_bands"


def test_simsat_data_source_mapbox_selects_mapbox_provider(monkeypatch):
    monkeypatch.delenv("OBSERVATION_PROVIDER", raising=False)
    monkeypatch.setenv("SIMSAT_ENABLED", "true")
    monkeypatch.setenv("SIMSAT_DATA_SOURCE", "mapbox")

    assert resolve_active_provider() == PROVIDER_SIMSAT_MAPBOX


def test_depth_anything_v3_defaults_disabled(monkeypatch):
    clear_depth_anything_runtime_override()
    monkeypatch.delenv("DEPTH_ANYTHING_V3_ENABLED", raising=False)
    monkeypatch.delenv("DEPTH_ANYTHING_V3_MODEL", raising=False)

    config = resolve_depth_anything_config()
    status = get_depth_anything_status()

    assert config.enabled is False
    assert config.model_id == DEFAULT_DEPTH_ANYTHING_V3_MODEL
    assert config.requested_device == "auto"
    assert config.resolved_device in {"cpu", "cuda"}
    assert status["enabled"] is False
    assert status["available"] is False
    assert status["reason"] == "disabled"


def test_depth_anything_v3_env_and_runtime_toggle(monkeypatch):
    clear_depth_anything_runtime_override()
    monkeypatch.setenv("DEPTH_ANYTHING_V3_ENABLED", "true")
    monkeypatch.setenv("DEPTH_ANYTHING_V3_MODEL", "depth-anything/test-model")
    monkeypatch.setenv("DEPTH_ANYTHING_V3_DEVICE", "cpu")

    config = resolve_depth_anything_config()

    assert config.enabled is True
    assert config.model_id == "depth-anything/test-model"
    assert config.requested_device == "cpu"
    assert config.resolved_device == "cpu"
    assert config.source == "env"

    disabled = set_depth_anything_enabled(False)
    assert disabled["enabled"] is False
    assert disabled["source"] == "runtime"

    clear_depth_anything_runtime_override()
