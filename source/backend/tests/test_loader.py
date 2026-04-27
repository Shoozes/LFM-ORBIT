import logging
from types import SimpleNamespace

import core.loader as loader
from core.observability import reset_throttled_logs


def test_provider_results_are_cached(tmp_path, monkeypatch):
    cache_path = tmp_path / "api_cache.sqlite"
    monkeypatch.setattr(loader, "CACHE_PATH", str(cache_path))
    loader._init_cache()
    monkeypatch.setattr(
        loader,
        "REGION",
        SimpleNamespace(
            observation_mode="simsat_sentinel",
            before_label="2024-06",
            after_label="2025-06",
        ),
    )

    calls = {"count": 0}

    def fake_simsat(cell_id: str):
        calls["count"] += 1
        return {
            "source": "simsat_sentinel_imagery",
            "cell_id": cell_id,
            "centroid_lat": 0.0,
            "centroid_lng": 0.0,
            "before": {
                "label": "Baseline 2025-06 (-2Y)",
                "quality": 0.95,
                "bands": {"nir": 0.6, "red": 0.1, "swir": 0.2},
                "flags": [],
            },
            "after": {
                "label": "2025-06",
                "quality": 0.92,
                "bands": {"nir": 0.3, "red": 0.2, "swir": 0.4},
                "flags": ["disturbance_pattern"],
            },
        }

    monkeypatch.setattr(loader, "_try_load_simsat_observations", fake_simsat)

    first = loader.load_temporal_observations("cell_a")
    second = loader.load_temporal_observations("cell_a")

    assert first == second
    assert calls["count"] == 1


def test_cache_key_changes_when_window_labels_change(tmp_path, monkeypatch):
    cache_path = tmp_path / "api_cache.sqlite"
    monkeypatch.setattr(loader, "CACHE_PATH", str(cache_path))
    loader._init_cache()

    calls = {"count": 0}

    def fake_simsat(cell_id: str):
        calls["count"] += 1
        return {
            "source": f"call_{calls['count']}",
            "cell_id": cell_id,
            "centroid_lat": 0.0,
            "centroid_lng": 0.0,
            "before": {
                "label": "baseline",
                "quality": 0.95,
                "bands": {"nir": 0.6, "red": 0.1, "swir": 0.2},
                "flags": [],
            },
            "after": {
                "label": "after",
                "quality": 0.92,
                "bands": {"nir": 0.3, "red": 0.2, "swir": 0.4},
                "flags": [],
            },
        }

    monkeypatch.setattr(loader, "_try_load_simsat_observations", fake_simsat)
    monkeypatch.setattr(
        loader,
        "REGION",
        SimpleNamespace(
            observation_mode="simsat_sentinel",
            before_label="2024-06",
            after_label="2025-06",
        ),
    )
    first = loader.load_temporal_observations("cell_a")

    monkeypatch.setattr(
        loader,
        "REGION",
        SimpleNamespace(
            observation_mode="simsat_sentinel",
            before_label="2025-06",
            after_label="2026-06",
        ),
    )
    second = loader.load_temporal_observations("cell_a")

    assert first["source"] == "call_1"
    assert second["source"] == "call_2"
    assert calls["count"] == 2


def test_loader_uses_simsat_for_mapbox_provider(tmp_path, monkeypatch):
    cache_path = tmp_path / "api_cache.sqlite"
    monkeypatch.setattr(loader, "CACHE_PATH", str(cache_path))
    loader._init_cache()
    monkeypatch.setattr(
        loader,
        "REGION",
        SimpleNamespace(
            observation_mode="simsat_mapbox",
            before_label="2024-06",
            after_label="2025-06",
        ),
    )

    calls = {"simsat": 0, "sentinel": 0}

    def fake_simsat(cell_id: str):
        calls["simsat"] += 1
        return {
            "source": "simsat_mapbox_imagery",
            "cell_id": cell_id,
            "centroid_lat": 0.0,
            "centroid_lng": 0.0,
            "before": {
                "label": "baseline",
                "quality": 0.95,
                "bands": {"nir": 0.6, "red": 0.1, "swir": 0.2},
                "flags": [],
            },
            "after": {
                "label": "after",
                "quality": 0.92,
                "bands": {"nir": 0.3, "red": 0.2, "swir": 0.4},
                "flags": ["disturbance_pattern"],
            },
        }

    monkeypatch.setattr(loader, "_try_load_simsat_observations", fake_simsat)
    monkeypatch.setattr(loader, "_try_load_sentinelhub_observations", lambda cell_id: calls.__setitem__("sentinel", calls["sentinel"] + 1))

    obs = loader.load_temporal_observations("cell_mapbox")

    assert obs["source"] == "simsat_mapbox_imagery"
    assert calls == {"simsat": 1, "sentinel": 0}


def test_loader_falls_back_from_simsat_sentinel_to_mapbox(tmp_path, monkeypatch):
    cache_path = tmp_path / "api_cache.sqlite"
    monkeypatch.setattr(loader, "CACHE_PATH", str(cache_path))
    loader._init_cache()
    monkeypatch.setenv("MAPBOX_ACCESS_TOKEN", "token")
    monkeypatch.delenv("DISABLE_EXTERNAL_APIS", raising=False)
    monkeypatch.setattr(
        loader,
        "REGION",
        SimpleNamespace(
            observation_mode="simsat_sentinel",
            before_label="2024-06",
            after_label="2025-06",
        ),
    )
    monkeypatch.setattr(loader, "_try_load_simsat_observations", lambda cell_id: None)
    monkeypatch.setattr(
        loader,
        "_try_load_simsat_mapbox_observations",
        lambda cell_id: {
            "source": "simsat_mapbox_imagery",
            "cell_id": cell_id,
            "centroid_lat": 0.0,
            "centroid_lng": 0.0,
            "before": {
                "label": "baseline",
                "quality": 0.95,
                "bands": {"nir": 0.6, "red": 0.1, "swir": 0.2},
                "flags": [],
            },
            "after": {
                "label": "after",
                "quality": 0.92,
                "bands": {"nir": 0.3, "red": 0.2, "swir": 0.4},
                "flags": [],
            },
        },
    )

    obs = loader.load_temporal_observations("cell_fallback")

    assert obs["source"] == "simsat_mapbox_imagery"


def test_loader_throttles_repeated_fallback_warnings(tmp_path, monkeypatch, caplog):
    cache_path = tmp_path / "api_cache.sqlite"
    monkeypatch.setattr(loader, "CACHE_PATH", str(cache_path))
    loader._init_cache()
    reset_throttled_logs()
    monkeypatch.setenv("DISABLE_EXTERNAL_APIS", "true")
    monkeypatch.setattr(
        loader,
        "REGION",
        SimpleNamespace(
            observation_mode="simsat_sentinel",
            before_label="2024-06",
            after_label="2025-06",
        ),
    )
    monkeypatch.setattr(loader, "_try_load_simsat_observations", lambda cell_id: None)
    monkeypatch.setattr(
        loader,
        "_load_semi_real_observations",
        lambda cell_id: {
            "source": loader.SOURCE_SEMI_REAL,
            "cell_id": cell_id,
            "centroid_lat": 0.0,
            "centroid_lng": 0.0,
            "before": {
                "label": "baseline",
                "quality": 0.95,
                "bands": {"nir": 0.6, "red": 0.1, "swir": 0.2},
                "flags": [],
            },
            "after": {
                "label": "after",
                "quality": 0.92,
                "bands": {"nir": 0.3, "red": 0.2, "swir": 0.4},
                "flags": [],
            },
        },
    )

    with caplog.at_level(logging.WARNING):
        loader.load_temporal_observations("cell_a")
        loader.load_temporal_observations("cell_b")

    messages = [record.message for record in caplog.records]

    assert sum("SimSat client failed" in message for message in messages) == 1
    assert sum("External APIs disabled" in message for message in messages) == 1
