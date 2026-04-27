from unittest.mock import patch

from core import vlm


def test_vlm_grounding_uses_fallback_when_transformers_unavailable():
    with patch("core.vlm._load_pipeline", return_value=None):
        vlm._grounding_pipeline = None
        assert vlm.run_vlm_grounding([-60.5, -3.5, -60.4, -3.4], "Find airplanes") == [
            {"label": "airplane", "bbox": [0.18, 0.22, 0.46, 0.52]},
            {"label": "airplane", "bbox": [0.52, 0.36, 0.78, 0.7]},
        ]


def test_vlm_vqa_uses_fallback_when_transformers_unavailable():
    with patch("core.vlm._load_pipeline", return_value=None):
        vlm._vqa_pipeline = None
        assert vlm.run_vlm_vqa([-60.5, -3.5, -60.4, -3.4], "How many airplanes are visible?") == "3."


def test_vlm_caption_uses_fallback_when_transformers_unavailable():
    with patch("core.vlm._load_pipeline", return_value=None):
        vlm._caption_pipeline = None
        assert vlm.run_vlm_caption([-60.5, -3.5, -60.4, -3.4]) == "Deforested clearing beside intact canopy."


def test_vlm_fetch_image_failure_returns_none_instead_of_blank_tile():
    with patch("core.vlm.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.side_effect = RuntimeError("network down")

        assert vlm._fetch_image([-60.5, -3.5, -60.4, -3.4]) is None
