import satellite_debug
from html.parser import HTMLParser


class _TagCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags: list[str] = []
        self.attrs: list[tuple[str, str | None]] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend(attrs)


def test_satellite_debug_server_render_escapes_message_fields():
    html = satellite_debug._render_feed(
        [
            {
                "id": '1" onclick="alert(1)',
                "sender": '<script>alert("sender")</script>',
                "recipient": "ground",
                "msg_type": '<img src=x onerror=alert("type")>',
                "cell_id": 'sq_1" onmouseover="alert(1)',
                "payload": {
                    "thinking": '<script>alert("thinking")</script>',
                    "tool_calls": [
                        {
                            "name": '<script>alert("tool")</script>',
                            "arguments": {"raw": '<img src=x onerror=alert("args")>'},
                        }
                    ],
                    "response": '<script>alert("response")</script>',
                },
                "time": '2026-04-27T00:00:00"><script>alert("time")</script>',
            }
        ]
    )

    parser = _TagCollector()
    parser.feed(html)

    assert "script" not in parser.tags
    assert "img" not in parser.tags
    event_attrs = [(name, value or "") for name, value in parser.attrs if name.startswith("on")]
    assert all(name == "onclick" and value.startswith("switchTab(") for name, value in event_attrs)
    assert all("alert" not in value for _name, value in event_attrs)
    assert "&lt;script&gt;alert" in html


def test_satellite_debug_cors_defaults_to_localhost(monkeypatch):
    monkeypatch.delenv("ORBIT_DEBUG_CORS_ALLOW_ORIGINS", raising=False)

    origins = satellite_debug._debug_cors_allow_origins()

    assert "*" not in origins
    assert "http://127.0.0.1:8080" in origins
