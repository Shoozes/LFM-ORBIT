from core import model_manifest
from scripts import smoke_satellite_model


def test_resolve_satellite_model_artifact_defaults(monkeypatch):
    monkeypatch.delenv("CANOPY_SENTINEL_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("CANOPY_SENTINEL_MODEL_MANIFEST", raising=False)
    monkeypatch.delenv("CANOPY_SENTINEL_MODEL_SUBDIR", raising=False)
    monkeypatch.delenv("CANOPY_SENTINEL_MODEL_FILENAME", raising=False)
    monkeypatch.delenv("CANOPY_SENTINEL_MODEL_MMPROJ_FILENAME", raising=False)
    monkeypatch.delenv("CANOPY_SENTINEL_MODEL_REPO_ID", raising=False)
    monkeypatch.delenv("CANOPY_SENTINEL_MODEL_REVISION", raising=False)

    artifact = model_manifest.resolve_satellite_model_artifact()

    assert artifact.model_dir == model_manifest.get_models_dir() / model_manifest.DEFAULT_MODEL_SUBDIR
    assert artifact.model_path == artifact.model_dir / model_manifest.DEFAULT_MODEL_FILENAME
    assert artifact.repo_id is None
    assert artifact.mmproj_path is None


def test_resolve_satellite_model_artifact_reads_manifest(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "runtime-data"
    model_dir = runtime_dir / "models" / "nm-uni-orbit"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "source_handoff.json").write_text("{\"repo_id\": \"example/orbit-satellite\"}", encoding="utf-8")
    (model_dir / "training_result_manifest.json").write_text("{\"run_id\": \"orbit-run-1\"}", encoding="utf-8")
    (model_dir / "README.md").write_text("# Orbit Bundle\n", encoding="utf-8")
    manifest_path = model_dir / model_manifest.DEFAULT_MANIFEST_FILENAME
    manifest_path.write_text(
        """
{
  "repo_id": "example/orbit-satellite",
  "revision": "release-1",
  "model_subdir": "nm-uni-orbit",
  "model_filename": "nm-uni-orbit-q4.gguf",
  "mmproj_filename": "nm-uni-orbit-mmproj.gguf",
  "base_model": "LiquidAI/LFM2.5-VL-450M",
  "quantization": "Q4_0",
  "task": "deforestation-triage",
  "training_result_manifest": "training_result_manifest.json"
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.delenv("CANOPY_SENTINEL_MODEL_MANIFEST", raising=False)
    monkeypatch.setenv("CANOPY_SENTINEL_MODEL_SUBDIR", "nm-uni-orbit")

    artifact = model_manifest.resolve_satellite_model_artifact()

    assert artifact.repo_id == "example/orbit-satellite"
    assert artifact.revision == "release-1"
    assert artifact.model_dir == model_dir
    assert artifact.model_path == model_dir / "nm-uni-orbit-q4.gguf"
    assert artifact.mmproj_path == model_dir / "nm-uni-orbit-mmproj.gguf"
    assert artifact.base_model == "LiquidAI/LFM2.5-VL-450M"
    assert artifact.quantization == "Q4_0"
    assert artifact.task == "deforestation-triage"
    assert artifact.training_result_manifest == "training_result_manifest.json"
    assert artifact.source_handoff_path == model_dir / "source_handoff.json"
    assert artifact.training_result_manifest_path == model_dir / "training_result_manifest.json"
    assert artifact.readme_path == model_dir / "README.md"

    status = artifact.to_status_dict()
    assert status["source_handoff_present"] is True
    assert status["training_result_manifest_present"] is True
    assert status["readme_present"] is True


def test_satellite_model_smoke_skips_when_optional_model_missing(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "runtime-data"
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.delenv("CANOPY_SENTINEL_MODEL_MANIFEST", raising=False)
    monkeypatch.delenv("CANOPY_SENTINEL_MODEL_SUBDIR", raising=False)

    payload = smoke_satellite_model.run_model_smoke()

    assert payload["format"] == "orbit_satellite_model_smoke_v1"
    assert payload["status"] == "skipped"
    assert payload["reason"] == "model file not found"
