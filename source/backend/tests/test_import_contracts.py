"""Import-contract tests for modules that form the supported app surface."""

from __future__ import annotations

import importlib
import pkgutil

import core


SCRIPT_MODULES = (
    "scripts.decision_gate",
    "scripts.drift_simulator",
    "scripts.evaluate_model",
    "scripts.export_orbit_dataset",
    "scripts.fetch_satellite_model",
    "scripts.gee_auth",
    "scripts.import_boundaries",
    "scripts.retag_training_assets",
    "scripts.retag_training_assets_ui",
    "scripts.seed_nasa_cache",
    "scripts.seed_sentinel_cache",
    "scripts.smoke_satellite_model",
    "scripts.upload_orbit_dataset_hf",
)

MANUAL_ENTRYPOINTS = (
    "satellite_debug",
    "start_edge",
    "test_evalscript",
    "test_wms",
)


def test_supported_backend_modules_import_cleanly():
    """Catch broken imports/exports before runtime or CI app startup."""
    module_names = [module.name for module in pkgutil.iter_modules(core.__path__, "core.")]
    module_names.extend(["api.main", *SCRIPT_MODULES, *MANUAL_ENTRYPOINTS])

    failures: list[str] = []
    for module_name in module_names:
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - failure path is the assertion payload
            failures.append(f"{module_name}: {type(exc).__name__}: {exc}")

    assert failures == []
