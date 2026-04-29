from __future__ import annotations

import json
from pathlib import Path

import imageio.v3 as iio
import numpy as np
from PIL import Image


ASSETS_ROOT = Path(__file__).resolve().parents[1] / "assets"
REPLAY_ROOT = ASSETS_ROOT / "replays"
SEEDED_DATA_ROOT = ASSETS_ROOT / "seeded_data"


def _edge_map(frame: np.ndarray) -> np.ndarray:
    img = Image.fromarray(frame).convert("L").resize((96, 72))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    gx = np.abs(arr[:, 1:] - arr[:, :-1])
    gy = np.abs(arr[1:, :] - arr[:-1, :])
    return gx[:71, :95] + gy[:71, :95]


def _replay_seeded_video_keys() -> set[str]:
    keys: set[str] = set()
    for replay_path in REPLAY_ROOT.glob("*.json"):
        payload = json.loads(replay_path.read_text(encoding="utf-8"))
        for alert in payload.get("alerts", []):
            seeded_video = str(alert.get("seeded_video") or "").strip()
            if seeded_video:
                keys.add(seeded_video)
    return keys


def test_seeded_replay_timelapses_are_real_frame_sequences():
    """Reject invalid timelapses made from one static image or trivial tinting."""
    seeded_video_keys = _replay_seeded_video_keys()
    assert seeded_video_keys

    for seeded_video in sorted(seeded_video_keys):
        webm_path = SEEDED_DATA_ROOT / f"{seeded_video}.webm"
        assert webm_path.is_file(), f"Missing replay video: {webm_path.name}"

        frames = list(iio.imiter(webm_path, plugin="pyav"))
        assert len(frames) >= 3, f"{webm_path.name} does not contain a temporal sequence"

        edge_diff = float(np.mean(np.abs(_edge_map(frames[0]) - _edge_map(frames[-1]))))
        assert edge_diff > 0.02, (
            f"{webm_path.name} looks structurally static across time; "
            "do not treat color-tinted still imagery as timelapse evidence"
        )
