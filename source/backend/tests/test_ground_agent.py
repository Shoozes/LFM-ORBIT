from datetime import datetime, timezone

from core import ground_agent


def test_ground_validator_timelapse_uses_active_mission_dates(monkeypatch):
    calls = {}

    def fake_generate_timelapse_frames(*, bbox, start_date, end_date, steps):
        calls["start_date"] = start_date
        calls["end_date"] = end_date
        calls["steps"] = steps
        return {
            "video_b64": "data:video/webm;base64,AAAA",
            "frames_count": 2,
            "format": "webm",
            "provenance": {"kind": "live_fetch"},
        }

    monkeypatch.setattr("core.timelapse.generate_timelapse_frames", fake_generate_timelapse_frames)
    monkeypatch.setattr(ground_agent, "analyze_timelapse", lambda bbox: "ok")

    video_b64, analysis, source = ground_agent._generate_cell_timelapse(
        "8928308280fffff",
        {
            "use_case_id": "wildfire",
            "start_date": "2026-04-05",
            "end_date": "2026-05-05",
        },
    )

    assert calls == {"start_date": "2026-04-05", "end_date": "2026-05-05", "steps": 12}
    assert video_b64 == "data:video/webm;base64,AAAA"
    assert analysis == "ok"
    assert source == "live_fetch"


def test_ground_validator_wildfire_without_dates_falls_back_to_recent_window(monkeypatch):
    calls = {}

    def fake_generate_timelapse_frames(*, bbox, start_date, end_date, steps):
        calls["start_date"] = start_date
        calls["end_date"] = end_date
        return {
            "video_b64": "",
            "frames_count": 0,
            "format": "none",
            "provenance": {"kind": "unavailable"},
        }

    monkeypatch.setattr("core.timelapse.generate_timelapse_frames", fake_generate_timelapse_frames)
    monkeypatch.setattr(ground_agent, "analyze_timelapse", lambda bbox: "ok")

    ground_agent._generate_cell_timelapse("8928308280fffff", {"use_case_id": "wildfire"})

    start = datetime.fromisoformat(calls["start_date"]).date()
    end = datetime.fromisoformat(calls["end_date"]).date()
    assert (end - start).days == 30
    assert end == datetime.now(timezone.utc).date()
