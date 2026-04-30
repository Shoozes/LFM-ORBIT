from core.inference import _llama_init_kwargs, _should_patch_llama_chat_templates, parse_output


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
