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


def _wildfire_replay_seeded_video_keys() -> set[str]:
    keys: set[str] = set()
    for replay_path in REPLAY_ROOT.glob("*.json"):
        payload = json.loads(replay_path.read_text(encoding="utf-8"))
        replay_id = str(payload.get("replay_id") or "")
        use_case_id = str(payload.get("use_case_id") or "")
        if use_case_id != "wildfire" and "wildfire" not in replay_id:
            continue
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


def test_wildfire_replays_include_replayable_assets_and_frame_metadata():
    """Source-backed wildfire replays must be reproducible from committed cache files."""
    seeded_video_keys = _wildfire_replay_seeded_video_keys()
    assert seeded_video_keys

    for seeded_video in sorted(seeded_video_keys):
        meta_path = SEEDED_DATA_ROOT / f"{seeded_video}_meta.json"
        assert meta_path.is_file(), f"Missing replay metadata: {meta_path.name}"

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        frame_images = [str(item) for item in meta.get("frame_images", [])]
        frame_dates = [str(item) for item in meta.get("frame_dates", [])]
        frames_count = int(meta.get("frames_count") or 0)

        assert frames_count >= 3, f"{meta_path.name} has fewer than 3 metadata frames"
        assert len(frame_images) == frames_count, f"{meta_path.name} frame_images mismatch"
        assert len(frame_dates) == frames_count, f"{meta_path.name} frame_dates mismatch"

        for frame_image in frame_images:
            frame_path = Path(__file__).resolve().parents[3] / frame_image
            assert frame_path.is_file(), f"Missing replay frame image: {frame_image}"
