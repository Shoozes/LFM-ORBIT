from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


WATCHLIST_ROOT = Path(__file__).resolve().parents[1] / "assets" / "watchlists"


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def test_future_wildfire_watchlist_is_timestamped_and_unverified():
    path = WATCHLIST_ROOT / "wildfire_spc_day2_southern_high_plains_2026-04-28.json"
    payload = json.loads(path.read_text(encoding="utf-8"))

    created_at = _parse_utc(payload["created_at_utc"])
    issued_at = _parse_utc(payload["source_issued_at_utc"])
    valid_from = _parse_utc(payload["valid_from_utc"])
    valid_to = _parse_utc(payload["valid_to_utc"])
    verify_after = _parse_utc(payload["verification_plan"]["verify_after_utc"])

    assert payload["schema"] == "orbit_future_watch_v1"
    assert payload["status"] == "watch_only_unverified"
    assert "not an ignition prediction" in payload["claim_boundary"]
    assert issued_at <= created_at < valid_from < valid_to < verify_after
    assert payload["hazard"] == "critical_fire_weather"
    assert len(payload["bbox"]) == 4
    assert payload["sources"][0]["url"].startswith("https://www.spc.noaa.gov/")
