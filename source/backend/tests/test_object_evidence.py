from core.object_evidence import color_key_for_class, run_object_evidence_batch


def test_object_evidence_batch_skips_disabled_targets_and_normalizes_boxes():
    calls: list[str] = []

    def fake_grounding(_bbox, prompt):
        calls.append(prompt)
        return {
            "results": [
                {
                    "label": "raw model label",
                    "bbox": [0.2, 0.1, 1.2, -0.2],
                    "confidence": 0.78,
                }
            ],
            "provenance": {
                "runtime_truth_mode": "replay",
                "imagery_origin": "cached_api",
                "scoring_basis": "visual_only",
                "model": "replay_fixture",
                "heuristic_fallback": False,
            },
        }

    payload = run_object_evidence_batch(
        [-81.9, 31.1, -81.7, 31.3],
        [
            {"label": "dark smoke", "prompt": "Find dark smoke", "class_key": "hazard", "enabled": True},
            {"label": "road obstruction", "prompt": "Find road obstruction", "class_key": "lifeline", "enabled": False},
        ],
        target_pack_id="fireline",
        frame_ref="current",
        grounding_fn=fake_grounding,
    )

    assert calls == ["Find dark smoke"]
    box = payload["results"][0]
    assert box["label"] == "dark smoke"
    assert box["bbox_format"] == "unit_xyxy"
    assert box["bbox"] == [0.0, 0.2, 0.1, 1.0]
    assert box["color_key"] == "hazard"
    assert box["source_model"] == "replay_fixture"
    assert box["frame_ref"] == "current"
    assert payload["summary"]["target_pack_id"] == "fireline"
    assert payload["summary"]["counts_by_label"] == {"dark smoke": 1}


def test_object_evidence_batch_handles_empty_targets():
    payload = run_object_evidence_batch(
        [-81.9, 31.1, -81.7, 31.3],
        [],
        target_pack_id=None,
        grounding_fn=lambda _bbox, _prompt: {"results": [{"bbox": [0, 0, 1, 1]}]},
    )

    assert payload["results"] == []
    assert payload["summary"]["total_boxes"] == 0
    assert payload["target_count"] == 0


def test_object_evidence_batch_discards_zero_area_boxes_after_clamp():
    def fake_grounding(_bbox, _prompt):
        return {
            "results": [
                {"bbox": [2.0, 2.0, 3.0, 3.0], "bbox_format": "unit_xyxy", "confidence": 0.9},
                {"bbox": [0.1, 0.1, 0.3, 0.3], "bbox_format": "unit_xyxy", "confidence": 0.8},
            ],
            "provenance": {"runtime_truth_mode": "replay"},
        }

    payload = run_object_evidence_batch(
        [-81.9, 31.1, -81.7, 31.3],
        [{"label": "dark smoke", "class_key": "hazard"}],
        grounding_fn=fake_grounding,
    )

    assert len(payload["results"]) == 1
    assert payload["results"][0]["bbox"] == [0.1, 0.1, 0.3, 0.3]


def test_object_evidence_batch_rejects_fallback_exact_object_boxes():
    def fake_grounding(_bbox, _prompt):
        return {
            "results": [{"bbox": [0.2, 0.2, 0.4, 0.4], "bbox_format": "unit_xyxy", "confidence": 0.9}],
            "provenance": {"heuristic_fallback": True, "runtime_truth_mode": "fallback"},
        }

    payload = run_object_evidence_batch(
        [32.515, 29.9, 32.575, 29.955],
        [{"label": "docked-vessel group", "prompt": "Find docked-vessel groups", "class_key": "vessel"}],
        target_pack_id="port",
        grounding_fn=fake_grounding,
    )

    assert payload["results"] == []
    assert payload["summary"]["total_boxes"] == 0
    assert payload["summary"]["provenance"]["heuristic_fallback"] is True


def test_object_evidence_batch_rejects_low_confidence_vessel_boxes():
    def fake_grounding(_bbox, _prompt):
        return {
            "results": [
                {"bbox": [0.2, 0.2, 0.4, 0.4], "bbox_format": "unit_xyxy", "confidence": 0.68},
                {"bbox": [0.5, 0.5, 0.7, 0.7], "bbox_format": "unit_xyxy", "confidence": 0.77},
            ],
            "provenance": {"heuristic_fallback": False, "runtime_truth_mode": "replay"},
        }

    payload = run_object_evidence_batch(
        [32.515, 29.9, 32.575, 29.955],
        [{"label": "docked-vessel group", "prompt": "Find docked-vessel groups", "class_key": "vessel"}],
        target_pack_id="port",
        grounding_fn=fake_grounding,
    )

    assert len(payload["results"]) == 1
    assert payload["results"][0]["bbox"] == [0.5, 0.5, 0.7, 0.7]
    assert payload["results"][0]["count_quality"] == "activity_region"


def test_color_key_for_class_preserves_current_target_pack_families():
    expected_keys = {
        "cryosphere",
        "industrial_surface",
        "land_cover_change",
        "surface_change",
        "vegetation",
        "water",
        "water_industrial",
        "waterline",
    }

    for key in expected_keys:
        assert color_key_for_class(key) == key

    assert color_key_for_class("excavation") == "surface_change"
    assert color_key_for_class("unknown_new_family") == "fallback"


def test_object_evidence_batch_marks_mixed_provenance():
    def fake_grounding(_bbox, prompt):
        if "smoke" in prompt:
            return {
                "results": [{"bbox": [0.1, 0.1, 0.2, 0.2], "bbox_format": "unit_xyxy"}],
                "provenance": {
                    "runtime_truth_mode": "replay",
                    "imagery_origin": "cached_api",
                    "scoring_basis": "visual_only",
                    "model": "fixture-a",
                    "heuristic_fallback": False,
                },
            }
        return {
            "results": [{"bbox": [0.3, 0.3, 0.4, 0.4], "bbox_format": "unit_xyxy"}],
            "provenance": {
                "runtime_truth_mode": "fallback",
                "imagery_origin": "simsat",
                "scoring_basis": "fallback_none",
                "model": "fixture-b",
                "heuristic_fallback": True,
            },
        }

    payload = run_object_evidence_batch(
        [-81.9, 31.1, -81.7, 31.3],
        [
            {"label": "dark smoke", "prompt": "Find dark smoke", "class_key": "hazard"},
            {"label": "road obstruction", "prompt": "Find road obstruction", "class_key": "lifeline"},
        ],
        grounding_fn=fake_grounding,
    )

    provenance = payload["summary"]["provenance"]
    assert provenance["heuristic_fallback"] is True
    assert provenance["runtime_truth_mode"] == "mixed"
    assert provenance["imagery_origin"] == "mixed"
    assert provenance["scoring_basis"] == "mixed"
    assert provenance["source_model"] == "mixed"
