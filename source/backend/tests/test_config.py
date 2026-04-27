from core.config import (
    PROVIDER_SIMSAT_MAPBOX,
    get_runtime_mode_summary,
    is_imagery_backed_scoring_enabled,
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
