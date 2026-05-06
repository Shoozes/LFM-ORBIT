import base64
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

import core.multimodal_inference as multimodal_inference
from api.main import app


client = TestClient(app)


def _png_b64() -> str:
    image = Image.new("RGB", (12, 12), (20, 90, 35))
    draw = ImageDraw.Draw(image)
    draw.rectangle((6, 0, 11, 11), fill=(150, 92, 45))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _configure_fake_image_runtime(monkeypatch):
    monkeypatch.setenv("ORBIT_IMAGE_CONDITIONED_INFERENCE", "true")
    monkeypatch.setenv("ORBIT_IMAGE_INFERENCE_BACKEND", "transformers_vlm")

    class FakePipeline:
        def __call__(self, *, image, question, top_k):
            return [{"answer": f"reviewed {image.size[0]}x{image.size[1]} evidence chip"}]

    monkeypatch.setattr(multimodal_inference, "_IMAGE_REVIEW_PIPELINE", FakePipeline())


def test_image_inference_api_returns_visual_review_with_metadata(monkeypatch):
    _configure_fake_image_runtime(monkeypatch)

    response = client.post(
        "/api/inference/image",
        json={
            "prompt": "Describe visible land-cover change. Do not infer cause beyond visible evidence.",
            "image_b64": _png_b64(),
            "metadata": {
                "cell_id": "sq_-10.0_-63.0",
                "frame_id": "after_window_2025-01-15",
                "runtime_truth_mode": "replay",
                "imagery_origin": "cached_api",
                "bbox": [-63.05, -10.05, -62.95, -9.95],
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    assert data["image_conditioned"] is True
    assert data["runtime_backend"] == "transformers_vlm"
    assert data["runtime_inference_mode"] == "image_conditioned_review"
    assert data["response"] == "reviewed 12x12 evidence chip"
    assert data["provenance"]["image_conditioned"] is True
    assert data["provenance"]["image_source"] == "cached_api"
    assert data["provenance"]["frame_id"] == "after_window_2025-01-15"
    assert data["provenance"]["bbox"] == [-63.05, -10.05, -62.95, -9.95]


def test_image_inference_api_rejects_missing_image_payload():
    response = client.post(
        "/api/inference/image",
        json={"prompt": "Inspect this retained evidence frame."},
    )

    assert response.status_code == 422


def test_image_inference_api_does_not_leak_local_paths(monkeypatch, tmp_path):
    _configure_fake_image_runtime(monkeypatch)
    image_path = tmp_path / "review-chip.png"
    Image.new("RGB", (12, 12), (20, 90, 35)).save(image_path)

    response = client.post(
        "/api/inference/image",
        json={
            "prompt": "Inspect this retained evidence frame.",
            "image_path": str(image_path),
            "metadata": {"cell_id": "sq_test"},
        },
    )

    assert response.status_code == 200
    data = response.json()
    payload_text = response.text
    assert data["provenance"]["image_path"] == "review-chip.png"
    assert str(tmp_path) not in payload_text
