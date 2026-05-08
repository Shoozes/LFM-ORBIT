from unittest.mock import patch

from core import vlm


def test_vlm_grounding_uses_fallback_when_transformers_unavailable():
    with patch("core.vlm._load_pipeline", return_value=None):
        vlm._grounding_pipeline = None
        assert vlm.run_vlm_grounding([-60.5, -3.5, -60.4, -3.4], "Find clearings") == [
            {"label": "clearing", "bbox": [0.24, 0.18, 0.74, 0.76]},
        ]


def test_vlm_fallback_does_not_fabricate_aircraft_boxes():
    with patch("core.vlm._load_pipeline", return_value=None):
        vlm._grounding_pipeline = None
        assert vlm.run_vlm_grounding([-60.5, -3.5, -60.4, -3.4], "Find airplanes") == []


def test_vlm_fallback_supports_only_candidate_safe_operator_search_labels():
    with patch("core.vlm._load_pipeline", return_value=None):
        vlm._grounding_pipeline = None
        assert vlm.run_vlm_grounding([-60.5, -3.5, -60.4, -3.4], "Find homes") == []
        assert vlm.run_vlm_grounding([-60.5, -3.5, -60.4, -3.4], "Find boats") == []
        assert vlm.run_vlm_grounding([-60.5, -3.5, -60.4, -3.4], "Find possible flaring")[0]["label"] == "possible flaring"
        assert vlm.run_vlm_grounding([-60.5, -3.5, -60.4, -3.4], "Find dark smoke")[0]["label"] == "dark smoke"
        assert (
            vlm.run_vlm_grounding([-69.115, -24.29, -69.035, -24.21], "Find critical minerals expansion regions")[0]["label"]
            == "mining expansion region"
        )


def test_vlm_vqa_uses_fallback_when_transformers_unavailable():
    with patch("core.vlm._load_pipeline", return_value=None):
        vlm._vqa_pipeline = None
        assert (
            vlm.run_vlm_vqa([-60.5, -3.5, -60.4, -3.4], "What land cover is visible?")
            == "Mixed vegetation, exposed clearing, and road context."
        )


def test_vlm_vqa_fallback_uses_bbox_context():
    with patch("core.vlm._load_pipeline", return_value=None):
        vlm._vqa_pipeline = None
        assert (
            vlm.run_vlm_vqa([-81.62, 28.33, -81.48, 28.44], "What land cover is visible?")
            == "Urban road corridor, water bodies, and managed vegetation."
        )
        assert (
            vlm.run_vlm_vqa([-69.115, -24.29, -69.035, -24.21], "What land cover is visible?")
            == "Arid extraction-site terrain with pit, tailings, pond, road, and facility context."
        )
        assert (
            vlm.run_vlm_vqa([-69.115, -24.29, -69.035, -24.21], "What evidence changed?")
            == "Extraction-site regions are visible; treat pit, tailings, pond, road, and facility context as review evidence."
        )
        assert (
            vlm.run_vlm_vqa([-82.2012, 29.6116, -82.1312, 29.6816], "What changed inside the selected evidence box?")
            == "Florida corridor evidence should stay candidate-only for smoke, burn-scar, fireline, road, water, and vegetation context."
        )


def test_vlm_vqa_fallback_marks_sensitive_targets_as_candidates():
    with patch("core.vlm._load_pipeline", return_value=None):
        vlm._vqa_pipeline = None
        assert "candidate evidence" in vlm.run_vlm_vqa(
            [-60.5, -3.5, -60.4, -3.4],
            "Is there dark smoke or possible flaring?",
        )


def test_vlm_caption_uses_fallback_when_transformers_unavailable():
    with patch("core.vlm._load_pipeline", return_value=None):
        vlm._caption_pipeline = None
        assert vlm.run_vlm_caption([-60.5, -3.5, -60.4, -3.4]) == "Deforested clearing beside intact canopy."
        assert (
            vlm.run_vlm_caption([-82.2012, 29.6116, -82.1312, 29.6816])
            == "Florida road corridor beside lakes and developed land."
        )
        assert (
            vlm.run_vlm_caption([-69.115, -24.29, -69.035, -24.21])
            == "Atacama extraction-site region with pit, tailings, pond, road, and facility context."
        )


def test_vlm_explain_caption_marks_heuristic_fallback():
    with patch("core.vlm._load_pipeline", return_value=None):
        vlm._caption_pipeline = None
        payload = vlm.explain_vlm_caption([-60.5, -3.5, -60.4, -3.4])

    assert payload["caption"] == "Deforested clearing beside intact canopy."
    assert payload["provenance"]["heuristic_fallback"] is True
    assert payload["provenance"]["runtime_truth_mode"] == "fallback"
    assert payload["provenance"]["imagery_origin"] == "fallback_none"
    assert payload["provenance"]["scoring_basis"] == "fallback_none"


def test_vlm_fetch_image_failure_returns_none_instead_of_blank_tile():
    with patch("core.vlm.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.side_effect = RuntimeError("network down")

        assert vlm._fetch_image([-60.5, -3.5, -60.4, -3.4]) is None
