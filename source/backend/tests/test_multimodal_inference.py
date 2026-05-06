import base64
from io import BytesIO

from PIL import Image, ImageDraw

import core.multimodal_inference as multimodal_inference
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
        "ORBIT_IMAGE_VLM_MODEL",
        "ORBIT_IMAGE_VLM_TASK",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(multimodal_inference, "_IMAGE_REVIEW_PIPELINE", None)


def _png_b64(*, blank: bool = False, clearing: bool = False) -> str:
    image = Image.new("RGB", (12, 12), (20, 90, 35) if not clearing else (150, 92, 45))
    if not blank:
        draw = ImageDraw.Draw(image)
        draw.rectangle((6, 0, 11, 11), fill=(150, 92, 45) if not clearing else (20, 90, 35))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


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


def test_generate_with_image_returns_unavailable_when_disabled(monkeypatch, tmp_path):
    _clear_image_runtime_env(monkeypatch)
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(tmp_path / "runtime-data"))

    payload = generate_with_image(
        "Inspect the evidence frame.",
        image_b64=_png_b64(),
        metadata={"cell_id": "8928308280fffff"},
    )

    assert payload["available"] is False
    assert payload["image_conditioned"] is False
    assert payload["response"] == ""
    assert payload["reason"] == "image-conditioned inference feature flag is disabled"
    assert payload["provenance"]["image_conditioned"] is False
    assert payload["provenance"]["image_b64_present"] is True
    assert payload["provenance"]["cell_id"] == "8928308280fffff"


def test_generate_with_image_rejects_invalid_image_payload(monkeypatch, tmp_path):
    _clear_image_runtime_env(monkeypatch)
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(tmp_path / "runtime-data"))

    payload = generate_with_image("Inspect.", image_b64="not-image-data")

    assert payload["available"] is False
    assert payload["image_conditioned"] is False
    assert "valid base64" in payload["reason"]


def test_generate_with_image_abstains_on_blank_image(monkeypatch, tmp_path):
    _clear_image_runtime_env(monkeypatch)
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(tmp_path / "runtime-data"))
    monkeypatch.setenv("ORBIT_IMAGE_CONDITIONED_INFERENCE", "true")
    monkeypatch.setenv("ORBIT_IMAGE_INFERENCE_BACKEND", "transformers_vlm")

    payload = generate_with_image("Describe visible evidence.", image_b64=_png_b64(blank=True))

    assert payload["available"] is True
    assert payload["abstained"] is True
    assert payload["image_conditioned"] is False
    assert payload["reason"] == "blank_or_no_data_image"
    assert "blank or no-data" in payload["response"]


def test_generate_with_image_calls_loaded_transformers_adapter(monkeypatch, tmp_path):
    _clear_image_runtime_env(monkeypatch)
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(tmp_path / "runtime-data"))
    monkeypatch.setenv("ORBIT_IMAGE_CONDITIONED_INFERENCE", "true")
    monkeypatch.setenv("ORBIT_IMAGE_INFERENCE_BACKEND", "transformers_vlm")

    class FakePipeline:
        def __call__(self, *, image, question, top_k):
            assert question == "Describe visible land-cover change."
            assert top_k == 1
            pixel = image.getpixel((0, 0))
            answer = "green canopy remains visible" if pixel[1] > pixel[0] else "exposed clearing is visible"
            return [{"answer": answer}]

    monkeypatch.setattr(multimodal_inference, "_IMAGE_REVIEW_PIPELINE", FakePipeline())

    payload = generate_with_image(
        "Describe visible land-cover change.",
        image_b64=_png_b64(),
        metadata={
            "cell_id": "sq_-10.0_-63.0",
            "frame_id": "after_window_2025-01-15",
            "imagery_origin": "cached_api",
            "bbox": [-63.05, -10.05, -62.95, -9.95],
        },
    )

    assert payload["available"] is True
    assert payload["image_conditioned"] is True
    assert payload["runtime_backend"] == "transformers_vlm"
    assert payload["runtime_inference_mode"] == "image_conditioned_review"
    assert payload["response"] == "green canopy remains visible"
    assert payload["provenance"]["image_conditioned"] is True
    assert payload["provenance"]["visual_model"] == "dandelin/vilt-b32-finetuned-vqa"
    assert payload["provenance"]["image_source"] == "cached_api"
    assert payload["provenance"]["frame_id"] == "after_window_2025-01-15"
    assert payload["provenance"]["bbox"] == [-63.05, -10.05, -62.95, -9.95]


def test_image_review_pixel_sensitivity_smoke(monkeypatch, tmp_path):
    _clear_image_runtime_env(monkeypatch)
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(tmp_path / "runtime-data"))
    monkeypatch.setenv("ORBIT_IMAGE_CONDITIONED_INFERENCE", "true")
    monkeypatch.setenv("ORBIT_IMAGE_INFERENCE_BACKEND", "transformers_vlm")

    class FakePipeline:
        def __call__(self, *, image, question, top_k):
            pixel = image.getpixel((0, 0))
            if pixel[1] > pixel[0]:
                return [{"answer": "vegetation-dominant chip"}]
            return [{"answer": "exposed-soil-dominant chip"}]

    monkeypatch.setattr(multimodal_inference, "_IMAGE_REVIEW_PIPELINE", FakePipeline())

    green_payload = generate_with_image("Describe visible evidence.", image_b64=_png_b64(clearing=False))
    clearing_payload = generate_with_image("Describe visible evidence.", image_b64=_png_b64(clearing=True))

    assert green_payload["image_conditioned"] is True
    assert clearing_payload["image_conditioned"] is True
    assert green_payload["response"] != clearing_payload["response"]


def test_multimodal_status_flips_true_after_adapter_loaded(monkeypatch, tmp_path):
    _clear_image_runtime_env(monkeypatch)
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(tmp_path / "runtime-data"))
    monkeypatch.setenv("ORBIT_IMAGE_CONDITIONED_INFERENCE", "true")
    monkeypatch.setenv("ORBIT_IMAGE_INFERENCE_BACKEND", "transformers_vlm")

    status_before = multimodal_status()
    assert status_before["image_conditioned_runtime_enabled"] is False

    monkeypatch.setattr(multimodal_inference, "_IMAGE_REVIEW_PIPELINE", object())

    status_after = multimodal_status()
    assert status_after["image_conditioned_runtime_enabled"] is True
    assert status_after["runtime_inference_mode"] == "image_conditioned_review"
