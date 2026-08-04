import pytest
from unittest.mock import patch
import base64
from pathlib import Path
from core import timelapse
from core.timelapse import generate_timelapse_frames

def test_generate_timelapse_frames_real_fetch(monkeypatch):
    """Test generating frames when a real fetch succeeds."""
    monkeypatch.setenv("DISABLE_EXTERNAL_APIS", "false")
    with patch("core.timelapse._read_cache", return_value=None), \
         patch("core.timelapse._write_cache"), \
         patch("core.timelapse._fetch_gee_frames") as mock_fetch:
        import numpy as np
        mock_frame = np.zeros((960, 1280, 3), dtype=np.uint8)
        mock_fetch.return_value = [(mock_frame, "iso1"), (mock_frame.copy(), "iso2")]

        result = generate_timelapse_frames(bbox=[-62, -9, -61, -8], start_date="2020", end_date="2021")

        assert result["format"] == "webm"
        assert result["frames_count"] == 2
        assert result["provenance"]["kind"] == "live_fetch"
        assert result["provenance"]["provider"] == "gee"
        assert result["video_b64"].startswith("data:video/webm;base64,")

def test_generate_timelapse_falls_back_to_gibs(monkeypatch):
    """Test that missing gee frames trigger gibs fallback securely."""
    monkeypatch.setenv("DISABLE_EXTERNAL_APIS", "false")
    with patch("core.timelapse._read_cache", return_value=None), \
         patch("core.timelapse._write_cache"), \
         patch("core.timelapse._fetch_gee_frames") as mock_gee, \
         patch("core.timelapse._fetch_gibs_frames") as mock_gibs:
        mock_gee.return_value = None # Fail GEE

        import numpy as np
        mock_frame = np.zeros((960, 1280, 3), dtype=np.uint8)
        mock_gibs.return_value = [(mock_frame, "iso1"), (mock_frame.copy(), "iso2")]

        result = generate_timelapse_frames(bbox=[-62, -9, -61, -8], start_date="2020", end_date="2021")

        assert result["format"] == "webm"
        assert result["frames_count"] == 2
        assert result["provider"] == "nasa_gibs"
        assert result["provenance"]["kind"] == "live_fetch"
        assert result["provenance"]["provider"] == "nasa_gibs"
        assert result["video_b64"].startswith("data:video/webm;base64,")

def test_generate_timelapse_fails_without_frames(monkeypatch):
    """Test what happens if both fetches fail with no cached frames."""
    monkeypatch.setenv("DISABLE_EXTERNAL_APIS", "false")
    with patch("core.timelapse._read_cache", return_value=None), \
         patch("core.timelapse._fetch_gee_frames", return_value=None), \
         patch("core.timelapse._fetch_gibs_frames", return_value=None):

        result = generate_timelapse_frames(bbox=[-62, -9, -61, -8], start_date="2020", end_date="2021", steps=4)

        assert result["format"] == "none"
        assert result["frames_count"] == 0
        assert "error" in result


def test_generate_timelapse_respects_requested_steps(monkeypatch):
    """The steps parameter should bound provider fetches for faster local runs."""
    monkeypatch.setenv("DISABLE_EXTERNAL_APIS", "false")
    with patch("core.timelapse._read_cache", return_value=None), \
         patch("core.timelapse._write_cache"), \
         patch("core.timelapse._fetch_gee_frames") as mock_fetch:
        import numpy as np
        mock_frame = np.zeros((960, 1280, 3), dtype=np.uint8)
        mock_fetch.return_value = [(mock_frame, "iso1"), (mock_frame.copy(), "iso2"), (mock_frame.copy(), "iso3")]

        result = generate_timelapse_frames(
            bbox=[-62, -9, -61, -8],
            start_date="2020-01-01",
            end_date="2022-12-31",
            steps=3,
        )

        months = mock_fetch.call_args.args[1]
        assert len(months) == 3
        assert result["format"] == "webm"


def test_generate_timelapse_returns_error_for_invalid_bbox():
    result = generate_timelapse_frames(
        bbox=[-62, -9],
        start_date="2020",
        end_date="2021",
    )

    assert result["format"] == "none"
    assert result["frames_count"] == 0
    assert "Invalid bbox" in result["error"]
    assert result["provenance"]["kind"] == "unavailable"


def test_generate_timelapse_defaults_external_apis_off(monkeypatch):
    monkeypatch.delenv("DISABLE_EXTERNAL_APIS", raising=False)

    result = generate_timelapse_frames(
        bbox=[-62, -9, -61, -8],
        start_date="2020",
        end_date="2021",
    )

    assert result["format"] == "none"
    assert result["frames_count"] == 0
    assert result["provenance"]["label"] == "External APIs disabled"


def test_read_cache_reports_seeded_provenance(monkeypatch, tmp_path):
    sig = "abc12345"
    monkeypatch.setattr(timelapse, "_SEEDED_DIR", tmp_path)
    (tmp_path / f"nasa_{sig}.webm").write_bytes(b"webm")
    (tmp_path / f"nasa_{sig}_meta.json").write_text(
        '{"frames_count": 7, "provider": "nasa_gibs"}',
        encoding="utf-8",
    )

    result = timelapse._read_cache(sig)

    assert result is not None
    assert result["source"] == "seeded_cache"
    assert result["runtime_truth_mode"] == "replay"
    assert result["imagery_origin"] == "cached_api"
    assert result["scoring_basis"] == "visual_only"
    assert result["provider"] == "nasa_gibs"
    assert result["provenance"]["kind"] == "replay_cache"
    assert result["provenance"]["legacy_kind"] == "seeded_cache"
    assert result["provenance"]["cache_key"] == sig


def test_generated_timelapse_cache_key_includes_months_and_provider_preference():
    bbox = [-62, -9, -61, -8]
    months_short = timelapse._month_range("2020-01", "2020-12", steps=3)
    months_long = timelapse._month_range("2020-01", "2020-12", steps=6)

    short_gee = timelapse._request_cache_key(bbox, months_short, "gee")
    long_gee = timelapse._request_cache_key(bbox, months_long, "gee")
    short_nasa = timelapse._request_cache_key(bbox, months_short, "nasa_gibs")

    assert short_gee != long_gee
    assert short_gee != short_nasa


def test_generated_cache_is_runtime_owned_and_requires_metadata(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "runtime"
    seeded_dir = tmp_path / "seeded"
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setattr(timelapse, "_SEEDED_DIR", seeded_dir)

    timelapse._write_cache(
        "runtime123",
        b"webm",
        {
            "cache_key_version": 2,
            "cache_key": "runtime123",
            "months": [[2025, 1], [2025, 2]],
            "frames_count": 2,
            "provider": "nasa_gibs",
        },
    )

    runtime_video = runtime_dir / "timelapse-cache" / "nasa_runtime123.webm"
    assert runtime_video.exists()
    assert not (seeded_dir / "nasa_runtime123.webm").exists()
    assert timelapse._read_cache("runtime123")["provenance"]["cache_storage"] == "runtime"

    (runtime_dir / "timelapse-cache" / "nasa_runtime123_meta.json").write_text("{}", encoding="utf-8")
    assert timelapse._read_cache("runtime123") is None
