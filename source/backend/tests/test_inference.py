from core.inference import parse_output


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
