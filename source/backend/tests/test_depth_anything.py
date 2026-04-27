"""Tests for the optional Depth Anything V3 adapter."""

from __future__ import annotations

import numpy as np
import pytest

from core import depth_anything
from core.depth_anything import _extract_depth_array, clear_depth_anything_runtime_override, estimate_depth_summary


class PredictionLike:
    def __init__(self, depth: np.ndarray):
        self.depth = depth


def test_extract_depth_array_accepts_dict_and_prediction_shapes():
    depth = np.asarray([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)

    from_dict = _extract_depth_array({"depth": depth})
    from_prediction = _extract_depth_array(PredictionLike(depth))
    from_list = _extract_depth_array([{"depths": [depth]}])

    assert from_dict.shape == (2, 2)
    assert from_prediction.shape == (2, 2)
    assert from_list.shape == (2, 2)


def test_estimate_depth_summary_rejects_bad_image_before_model_load(monkeypatch):
    clear_depth_anything_runtime_override()
    monkeypatch.setenv("DEPTH_ANYTHING_V3_ENABLED", "true")
    monkeypatch.setattr(depth_anything, "_package_available", lambda: True)

    def fail_model_load(config):
        raise AssertionError("model should not load before image payload validation")

    monkeypatch.setattr(depth_anything, "_get_model", fail_model_load)

    with pytest.raises(ValueError, match="valid base64 image data"):
        estimate_depth_summary("not-image")

    clear_depth_anything_runtime_override()
