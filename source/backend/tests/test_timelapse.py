import pytest
from unittest.mock import patch
import base64
from pathlib import Path
from core.timelapse import generate_timelapse_frames

def test_generate_timelapse_frames_real_fetch():
    """Test generating frames when a real fetch succeeds."""
    with patch("core.timelapse._read_cache", return_value=None), \
         patch("core.timelapse._write_cache"), \
         patch("core.timelapse._fetch_gee_frames") as mock_fetch:
        import numpy as np
        mock_frame = np.zeros((960, 1280, 3), dtype=np.uint8)
        mock_fetch.return_value = [(mock_frame, "iso1"), (mock_frame.copy(), "iso2")]
        
        result = generate_timelapse_frames(bbox=[-62, -9, -61, -8], start_date="2020", end_date="2021")
        
        assert result["format"] == "webm"
        assert result["frames_count"] == 2
        assert result["video_b64"].startswith("data:video/webm;base64,")

def test_generate_timelapse_falls_back_to_gibs():
    """Test that missing gee frames trigger gibs fallback securely."""
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
        assert result["video_b64"].startswith("data:video/webm;base64,")
                
def test_generate_timelapse_fails_without_frames():
    """Test what happens if both fetches fail with no cached frames."""
    with patch("core.timelapse._read_cache", return_value=None), \
         patch("core.timelapse._fetch_gee_frames", return_value=None), \
         patch("core.timelapse._fetch_gibs_frames", return_value=None):
        
        result = generate_timelapse_frames(bbox=[-62, -9, -61, -8], start_date="2020", end_date="2021", steps=4)
        
        assert result["format"] == "none"
        assert result["frames_count"] == 0
        assert "error" in result
