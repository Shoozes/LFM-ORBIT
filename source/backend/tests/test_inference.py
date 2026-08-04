import threading

import core.inference as inference
from core.inference import (
    _llama_init_kwargs,
    _should_patch_llama_chat_templates,
    build_satellite_prompt,
    parse_output,
)


def test_llama_init_uses_chatml_format_by_default(monkeypatch):
    monkeypatch.delenv("CANOPY_SENTINEL_LLAMACPP_CHAT_FORMAT", raising=False)

    kwargs = _llama_init_kwargs("model.gguf")

    assert kwargs["model_path"] == "model.gguf"
    assert kwargs["chat_format"] == "chatml"


def test_llama_init_allows_chat_format_override(monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_LLAMACPP_CHAT_FORMAT", "llama-2")

    kwargs = _llama_init_kwargs("model.gguf")

    assert kwargs["chat_format"] == "llama-2"


def test_llama_chat_template_patch_defaults_on(monkeypatch):
    monkeypatch.delenv("CANOPY_SENTINEL_LLAMACPP_PATCH_CHAT_TEMPLATE", raising=False)
    assert _should_patch_llama_chat_templates() is True


def test_llama_chat_template_patch_can_be_disabled(monkeypatch):
    monkeypatch.setenv("CANOPY_SENTINEL_LLAMACPP_PATCH_CHAT_TEMPLATE", "false")
    assert _should_patch_llama_chat_templates() is False


def test_parse_output_ignores_malformed_tool_json(caplog):
    caplog.set_level("DEBUG", logger="core.inference")

    parsed = parse_output('analysis {"tool": bad-json} final answer')

    assert parsed["tool_calls"] == []
    assert parsed["response"] == 'analysis {"tool": bad-json} final answer'
    assert "Ignoring malformed tool-call JSON" in caplog.text


def test_parse_output_extracts_valid_tool_json():
    parsed = parse_output('Check ```json\n{"tool": "zoom", "arguments": {"cell_id": "sq_1_2"}}\n```')

    assert parsed["tool_calls"] == [
        {"name": "zoom", "arguments": {"cell_id": "sq_1_2"}}
    ]


def test_satellite_prompt_uses_mission_use_case_contract():
    score = {
        "change_score": 0.8,
        "confidence": 0.7,
        "reason_codes": ["burn_scar", "nbr_drop"],
        "observation_source": "seeded_replay",
    }
    prompt = build_satellite_prompt(
        "sq_fire",
        score,
        mission={
            "use_case_id": "wildfire",
            "target_pack_id": "fireline",
            "task_text": "Review the burn scar and smoke boundary.",
        },
    )

    assert "use_case_id: wildfire" in prompt
    assert "target_category: wildfire" in prompt
    assert "burn_scar" in prompt
    assert "deforestation" not in prompt.lower()


def test_satellite_prompt_handles_missing_numeric_scores():
    prompt = build_satellite_prompt("sq_unknown", {"change_score": None, "confidence": "bad"})

    assert "change_score: 0.0000" in prompt
    assert "confidence:   0.0000" in prompt


def test_generate_serializes_llama_completion_calls(monkeypatch):
    entered = threading.Event()
    completed = threading.Event()

    class FakeModel:
        def create_chat_completion(self, **_kwargs):
            entered.set()
            return {"choices": [{"message": {"content": "locked completion"}}]}

    monkeypatch.setattr(inference, "_get_model", lambda: FakeModel())

    with inference._generation_lock:
        worker = threading.Thread(
            target=lambda: (
                inference.generate("hello", max_tokens=4),
                completed.set(),
            )
        )
        worker.start()
        assert not entered.wait(0.15)
        assert not completed.is_set()

    worker.join(timeout=2)
    assert entered.is_set()
    assert completed.is_set()


def test_stream_tokens_serializes_llama_streaming_calls(monkeypatch):
    entered = threading.Event()
    completed = threading.Event()

    class FakeModel:
        def create_chat_completion(self, **_kwargs):
            entered.set()
            yield {"choices": [{"delta": {"content": "locked"}}]}

    monkeypatch.setattr(inference, "_get_model", lambda: FakeModel())

    with inference._generation_lock:
        worker = threading.Thread(
            target=lambda: (
                list(inference.stream_tokens("hello", max_tokens=4)),
                completed.set(),
            )
        )
        worker.start()
        assert not entered.wait(0.15)
        assert not completed.is_set()

    worker.join(timeout=2)
    assert entered.is_set()
    assert completed.is_set()
