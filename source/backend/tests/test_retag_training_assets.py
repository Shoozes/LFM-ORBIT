import json

from PIL import Image

from scripts import retag_training_assets


def _write_png(path, color):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), color).save(path)


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_retag_dataset_dedupes_assets_and_preserves_references(tmp_path):
    dataset = tmp_path / "dataset"
    sample_a = dataset / "samples" / "sample_a"
    sample_b = dataset / "samples" / "sample_b"
    _write_png(sample_a / "context_thumb.png", (10, 20, 30))
    _write_png(sample_b / "context_thumb.png", (10, 20, 30))
    (dataset / "samples.jsonl").write_text(
        "\n".join(
            [
                json.dumps({
                    "sample_id": "sample_a",
                    "record_type": "positive",
                    "target_task": "deforestation_detection",
                    "target_category": "deforestation",
                    "target_action": "alert",
                    "observation_source": "seeded_cache",
                    "reason_codes": ["ndvi_drop"],
                    "assets": {"context_thumb": "context_thumb.png"},
                }),
                json.dumps({
                    "sample_id": "sample_b",
                    "record_type": "positive",
                    "target_task": "deforestation_detection",
                    "target_category": "deforestation",
                    "target_action": "alert",
                    "observation_source": "seeded_cache",
                    "reason_codes": ["ndvi_drop"],
                    "assets": {"context_thumb": "context_thumb.png"},
                }),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    output = tmp_path / "retagged"
    manifest = retag_training_assets.retag_dataset(
        dataset,
        output,
        provider="heuristic",
        scan_loose_assets=False,
    )
    rows = _read_jsonl(output / "retagged_assets.jsonl")
    metadata = _read_jsonl(output / "metadata.jsonl")

    assert manifest["unique_training_assets"] == 1
    assert manifest["duplicate_assets_removed"] == 1
    assert rows[0]["duplicate_reference_count"] == 1
    assert {ref["sample_id"] for ref in rows[0]["references"]} == {"sample_a", "sample_b"}
    assert metadata[0]["file_name"].startswith("images/")
    assert (output / metadata[0]["file_name"]).exists()


def test_retag_dataset_extracts_timelapse_frames_and_sequence_rows(tmp_path, monkeypatch):
    dataset = tmp_path / "dataset"
    sample_dir = dataset / "samples" / "sample_video"
    sample_dir.mkdir(parents=True)
    (sample_dir / "timelapse.webm").write_bytes(b"not-a-real-video")
    (dataset / "samples.jsonl").write_text(
        json.dumps({
            "sample_id": "sample_video",
            "record_type": "positive",
            "target_task": "deforestation_detection",
            "target_category": "deforestation",
            "target_action": "alert",
            "observation_source": "seeded_replay",
            "reason_codes": ["multi_index_consensus"],
            "assets": {"timelapse": "timelapse.webm"},
        })
        + "\n",
        encoding="utf-8",
    )

    def fake_extract(candidate, frames_dir, *, frame_count, min_video_frames):
        frames_dir.mkdir(parents=True, exist_ok=True)
        first = frames_dir / "timelapse__frame_0000.jpg"
        second = frames_dir / "timelapse__frame_0002.jpg"
        _write_png(first, (0, 40, 0))
        _write_png(second, (120, 80, 30))
        frame_candidates = [
            retag_training_assets.AssetCandidate(
                path=first,
                source_kind="video_frame",
                asset_key="timelapse:frame_0",
                refs=[
                    retag_training_assets.AssetRef(
                        sample_id="sample_video",
                        asset_key="timelapse:frame_0",
                        target_task="deforestation_detection",
                        target_category="deforestation",
                        target_action="alert",
                        observation_source="seeded_replay",
                        reason_codes=["multi_index_consensus"],
                        video_source=str(candidate.path),
                        frame_index=0,
                    )
                ],
            ),
            retag_training_assets.AssetCandidate(
                path=second,
                source_kind="video_frame",
                asset_key="timelapse:frame_2",
                refs=[
                    retag_training_assets.AssetRef(
                        sample_id="sample_video",
                        asset_key="timelapse:frame_2",
                        target_task="deforestation_detection",
                        target_category="deforestation",
                        target_action="alert",
                        observation_source="seeded_replay",
                        reason_codes=["multi_index_consensus"],
                        video_source=str(candidate.path),
                        frame_index=2,
                    )
                ],
            ),
        ]
        sequence = retag_training_assets.TemporalSequenceCandidate(
            video_path=candidate.path,
            refs=candidate.refs,
            frame_candidates=frame_candidates,
            decoded_frames_count=3,
            sampled_indices=[0, 2],
        )
        return frame_candidates, sequence, []

    monkeypatch.setattr(retag_training_assets, "_extract_video_frames", fake_extract)

    output = tmp_path / "retagged"
    manifest = retag_training_assets.retag_dataset(
        dataset,
        output,
        provider="heuristic",
        scan_loose_assets=False,
        frame_count=2,
    )
    asset_rows = _read_jsonl(output / "retagged_assets.jsonl")
    sequence_rows = _read_jsonl(output / "temporal_sequences.jsonl")
    sequence_training_rows = _read_jsonl(output / "training_temporal_sequences.jsonl")

    assert manifest["unique_training_assets"] == 2
    assert manifest["unique_temporal_sequences"] == 1
    assert {row["source_kind"] for row in asset_rows} == {"video_frame"}
    assert sequence_rows[0]["decoded_frames_count"] == 3
    assert sequence_rows[0]["sampled_indices"] == [0, 2]
    assert sequence_rows[0]["unique_frame_assets"] == 2
    assert sequence_rows[0]["retag"]["temporal_validity"] == "multi_frame_context"
    assert len(sequence_training_rows[0]["images"]) == 2
