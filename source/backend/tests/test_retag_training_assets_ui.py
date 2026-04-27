import json
import sys

import pytest

from scripts import retag_training_assets_ui


def test_build_retag_command_includes_selected_options(tmp_path):
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "out"

    command = retag_training_assets_ui.build_retag_command(
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        provider="ollama",
        model="qwen2.5vl:32b",
        video_frame_count=6,
        min_video_frames=3,
        scan_loose_assets=False,
        temporal_sequences=False,
    )

    assert command[0] == sys.executable
    assert "--dataset-dir" in command
    assert str(dataset_dir) in command
    assert "--output-dir" in command
    assert str(output_dir) in command
    assert command[command.index("--provider") + 1] == "ollama"
    assert command[command.index("--model") + 1] == "qwen2.5vl:32b"
    assert command[command.index("--video-frame-count") + 1] == "6"
    assert command[command.index("--min-video-frames") + 1] == "3"
    assert "--no-loose-scan" in command
    assert "--no-temporal-sequences" in command


def test_build_retag_command_rejects_unknown_provider(tmp_path):
    with pytest.raises(ValueError, match="unsupported provider"):
        retag_training_assets_ui.build_retag_command(
            dataset_dir=tmp_path,
            output_dir=None,
            provider="unknown",
            model="",
            video_frame_count=4,
            min_video_frames=2,
            scan_loose_assets=True,
            temporal_sequences=True,
        )


def test_read_manifest_summary_reports_counts(tmp_path):
    output_dir = tmp_path / "retagged"
    output_dir.mkdir()
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "unique_training_assets": 12,
                "unique_temporal_sequences": 3,
                "duplicate_assets_removed": 4,
                "skipped_assets": 1,
                "tagger_failures": 0,
            }
        ),
        encoding="utf-8",
    )

    summary = retag_training_assets_ui.read_manifest_summary(output_dir)

    assert "Unique assets: 12" in summary
    assert "Temporal sequences: 3" in summary
    assert "Duplicates removed: 4" in summary
