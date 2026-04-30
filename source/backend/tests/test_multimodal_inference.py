from core.multimodal_inference import generate_with_image, multimodal_status
from core.model_manifest import DEFAULT_MODEL_FILENAME, DEFAULT_MODEL_SUBDIR


def _clear_image_runtime_env(monkeypatch):
    for key in (
        "ORBIT_IMAGE_CONDITIONED_INFERENCE",
        "ORBIT_IMAGE_INFERENCE_BACKEND",
        "ORBIT_REQUIRE_MMPROJ_FOR_IMAGE_INFERENCE",
        "CANOPY_SENTINEL_MODEL_MANIFEST",
        "CANOPY_SENTINEL_MODEL_SUBDIR",
        "CANOPY_SENTINEL_MODEL_FILENAME",
        "CANOPY_SENTINEL_MODEL_MMPROJ_FILENAME",
    ):
        monkeypatch.delenv(key, raising=False)


def test_multimodal_status_defaults_to_text_evidence_runtime(monkeypatch, tmp_path):
    _clear_image_runtime_env(monkeypatch)
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(tmp_path / "runtime-data"))

    status = multimodal_status()

    assert status["feature"] == "image_conditioned_runtime"
    assert status["feature_flag_enabled"] is False
    assert status["runtime_backend"] == "none"
    assert status["runtime_inference_mode"] == "text_evidence_packet"
    assert status["image_conditioned_runtime_enabled"] is False
    assert status["image_conditioned_reasoning"] is False
    assert status["image_conditioned_runtime_reason"] == "image-conditioned inference feature flag is disabled"


def test_multimodal_status_reports_mmproj_gate_without_enabling_unwired_adapter(monkeypatch, tmp_path):
    _clear_image_runtime_env(monkeypatch)
    runtime_dir = tmp_path / "runtime-data"
    model_dir = runtime_dir / "models" / DEFAULT_MODEL_SUBDIR
    model_dir.mkdir(parents=True)
    (model_dir / DEFAULT_MODEL_FILENAME).write_bytes(b"gguf")
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("CANOPY_SENTINEL_MODEL_MMPROJ_FILENAME", "orbit-mmproj.gguf")
    monkeypatch.setenv("ORBIT_IMAGE_CONDITIONED_INFERENCE", "true")
    monkeypatch.setenv("ORBIT_IMAGE_INFERENCE_BACKEND", "llama_cpp_mmproj")

    status = multimodal_status()

    assert status["gguf_present"] is True
    assert status["mmproj_present"] is False
    assert status["runtime_backend"] == "llama_cpp_mmproj"
    assert status["image_conditioned_runtime_enabled"] is False
    assert status["image_conditioned_runtime_reason"] == "mmproj not present"


def test_generate_with_image_returns_unavailable_provenance(monkeypatch, tmp_path):
    _clear_image_runtime_env(monkeypatch)
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(tmp_path / "runtime-data"))

    payload = generate_with_image(
        "Inspect the evidence frame.",
        image_path="runtime-data/gallery/context.png",
        metadata={"cell_id": "8928308280fffff"},
    )

    assert payload["available"] is False
    assert payload["image_conditioned"] is False
    assert payload["response"] == ""
    assert payload["provenance"]["image_conditioned"] is False
    assert payload["provenance"]["image_path"] == "runtime-data/gallery/context.png"
    assert payload["provenance"]["cell_id"] == "8928308280fffff"
