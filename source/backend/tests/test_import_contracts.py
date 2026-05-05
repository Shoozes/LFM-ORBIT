"""Import-contract tests for modules that form the supported app surface."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

import core


SCRIPT_MODULES = (
    "scripts.decision_gate",
    "scripts.drift_simulator",
    "scripts.evaluate_model",
    "scripts.evaluate_object_evidence",
    "scripts.export_orbit_dataset",
    "scripts.build_docs_timelapse_highlight",
    "scripts.build_visual_story_proofs",
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

BACKEND_ROOT = Path(__file__).resolve().parents[1]

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


def test_supported_script_module_list_matches_scripts_directory():
    """Keep the import guard in sync when adding backend scripts."""
    expected = {
        f"scripts.{path.stem}"
        for path in (BACKEND_ROOT / "scripts").glob("*.py")
        if not path.name.startswith("_")
    }

    assert set(SCRIPT_MODULES) == expected


def test_backend_scratch_probe_modules_are_pruned():
    """Keep ad hoc provider probes out of the tracked backend surface."""
    scratch_dir = BACKEND_ROOT / "scratch"
    if not scratch_dir.exists():
        return

    assert sorted(path.name for path in scratch_dir.glob("*.py")) == []


def test_launchers_keep_minimal_runtime_guards_documented():
    """Keep cold-start launchers aligned with the documented Python/Node/uv contract."""
    repo_root = BACKEND_ROOT.parents[1]
    bash_launcher = (repo_root / "run.sh").read_text(encoding="utf-8")
    ps_launcher = (repo_root / "run.ps1").read_text(encoding="utf-8")

    assert "Python 3.10+" in bash_launcher
    assert "Python 3.10+" in ps_launcher
    assert "20.19.0" in bash_launcher
    assert "22.12.0" in bash_launcher
    assert "20.19.0" in ps_launcher
    assert "22.12.0" in ps_launcher
    assert "uv not found; bootstrapping repo-local uv" in bash_launcher
    assert "uv not found; bootstrapping repo-local uv" in ps_launcher
    assert "node.exe" in bash_launcher
    assert "NPM_CMD" in bash_launcher
    assert "NPX_CMD" in bash_launcher
