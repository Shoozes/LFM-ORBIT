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
    assert all("timelapse_" in row["source_asset_path"] for row in asset_rows)


def test_retag_dataset_names_extracted_frames_by_video_hash(tmp_path, monkeypatch):
    dataset = tmp_path / "dataset"
    first_sample = dataset / "samples" / "first"
    second_sample = dataset / "samples" / "second"
    first_sample.mkdir(parents=True)
    second_sample.mkdir(parents=True)
    first_video = first_sample / "timelapse.webm"
    second_video = second_sample / "timelapse.webm"
    first_video.write_bytes(b"first-video")
    second_video.write_bytes(b"second-video")
    (dataset / "samples.jsonl").write_text(
        "\n".join(
            [
                json.dumps({
                    "sample_id": "first",
                    "target_task": "temporal_change_review",
                    "target_category": "temporal_change",
                    "target_action": "review",
                    "assets": {"timelapse": "timelapse.webm"},
                }),
                json.dumps({
                    "sample_id": "second",
                    "target_task": "temporal_change_review",
                    "target_category": "temporal_change",
                    "target_action": "review",
                    "assets": {"timelapse": "timelapse.webm"},
                }),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_read_video_frames(path):
        if path == first_video:
            return [
                retag_training_assets.np.asarray(Image.new("RGB", (8, 8), (10, 20, 30))),
                retag_training_assets.np.asarray(Image.new("RGB", (8, 8), (40, 50, 60))),
            ]
        return [
            retag_training_assets.np.asarray(Image.new("RGB", (8, 8), (70, 80, 90))),
            retag_training_assets.np.asarray(Image.new("RGB", (8, 8), (100, 110, 120))),
        ]

    monkeypatch.setattr(retag_training_assets, "_read_video_frames", fake_read_video_frames)

    output = tmp_path / "retagged"
    manifest = retag_training_assets.retag_dataset(
        dataset,
        output,
        provider="heuristic",
        scan_loose_assets=False,
        frame_count=2,
    )
    frame_names = sorted(path.name for path in (output / "frames").glob("*.jpg"))

    assert manifest["unique_temporal_sequences"] == 2
    assert len(frame_names) == 4
    assert any(retag_training_assets._sha256(first_video)[:16] in name for name in frame_names)
    assert any(retag_training_assets._sha256(second_video)[:16] in name for name in frame_names)


def test_ollama_retag_disables_thinking_for_json_response(tmp_path, monkeypatch):
    image_path = tmp_path / "asset.png"
    _write_png(image_path, (10, 40, 90))
    candidate = retag_training_assets.AssetCandidate(
        path=image_path,
        source_kind="image",
        asset_key="context",
        refs=[],
    )
    captured = {}

    def fake_post_json(url, payload, headers, timeout):
        captured.update(payload)
        return {
            "response": json.dumps({
                "target_category": "flood",
                "target_action": "alert",
                "visual_summary": "Visible water expansion candidate.",
                "labels": ["flood"],
                "reason_codes": ["surface_water"],
                "confidence": 0.8,
                "quality": "usable",
                "temporal_evidence": "single frame only",
                "needs_human_review": False,
            })
        }

    monkeypatch.setattr(retag_training_assets, "_post_json", fake_post_json)

    retag_training_assets._ollama_retag(
        candidate,
        [],
        "qwen3.6:27b",
        base_url="http://127.0.0.1:11434",
        timeout=5.0,
    )

    assert captured["model"] == "qwen3.6:27b"
    assert captured["format"] == "json"
    assert captured["stream"] is False
    assert captured["think"] is False


def test_ollama_budget_falls_back_to_heuristic_for_remaining_assets(tmp_path, monkeypatch):
    dataset = tmp_path / "dataset"
    _write_png(dataset / "asset_a.png", (20, 40, 80))
    _write_png(dataset / "asset_b.png", (120, 90, 40))
    calls = {"count": 0}

    def fake_ollama_retag(candidate, refs, model, *, base_url, timeout):
        calls["count"] += 1
        return {
            "target_category": "wildfire",
            "target_action": "alert",
            "visual_summary": "Model-reviewed wildfire candidate.",
            "labels": ["wildfire"],
            "reason_codes": ["burn_scar"],
            "confidence": 0.75,
            "quality": "usable",
            "temporal_evidence": "single frame only",
            "needs_human_review": False,
        }

    monkeypatch.setattr(retag_training_assets, "_ollama_retag", fake_ollama_retag)

    output = tmp_path / "retagged"
    manifest = retag_training_assets.retag_dataset(
        dataset,
        output,
        provider="ollama",
        model="qwen3.6:27b",
        tag_temporal_sequences=False,
        scan_loose_assets=True,
        max_provider_assets=1,
    )
    rows = _read_jsonl(output / "retagged_assets.jsonl")

    assert calls["count"] == 1
    assert manifest["provider_asset_calls"] == 1
    assert manifest["provider_budget_fallbacks"] == 1
    assert {row["provider"] for row in rows} == {"ollama", "heuristic"}


def test_retag_dataset_reuses_existing_tags_without_provider_call(tmp_path, monkeypatch):
    dataset = tmp_path / "dataset"
    sample_old = dataset / "samples" / "sample_old"
    sample_new = dataset / "samples" / "sample_new"
    old_asset = sample_old / "context_thumb.png"
    new_asset = sample_new / "context_thumb.png"
    _write_png(old_asset, (30, 70, 110))
    _write_png(new_asset, (180, 90, 40))
    old_sha = retag_training_assets._sha256(old_asset)
    (dataset / "samples.jsonl").write_text(
        "\n".join(
            [
                json.dumps({
                    "sample_id": "sample_old",
                    "record_type": "seeded_cache",
                    "target_task": "water_extent_review",
                    "target_category": "water_extent",
                    "target_action": "review",
                    "observation_source": "sentinel",
                    "reason_codes": ["seeded_data"],
                    "assets": {"context_thumb": "context_thumb.png"},
                }),
                json.dumps({
                    "sample_id": "sample_new",
                    "record_type": "seeded_cache",
                    "target_task": "wildfire_temporal_detection",
                    "target_category": "wildfire",
                    "target_action": "alert",
                    "observation_source": "sentinel",
                    "reason_codes": ["burn_scar"],
                    "assets": {"context_thumb": "context_thumb.png"},
                }),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "retagged_assets.jsonl").write_text(
        json.dumps({
            "asset_sha256": old_sha,
            "provider": "ollama",
            "model": "qwen3.6:27b",
            "retag": {
                "target_category": "water_extent",
                "target_action": "review",
                "visual_summary": "Previously reviewed water extent frame.",
                "labels": ["water_extent"],
                "reason_codes": ["seeded_data"],
                "confidence": 0.83,
                "quality": "usable",
                "temporal_evidence": "single frame only",
                "needs_human_review": False,
            },
        })
        + "\n",
        encoding="utf-8",
    )
    calls = {"count": 0}

    def fake_ollama_retag(candidate, refs, model, *, base_url, timeout):
        calls["count"] += 1
        return {
            "target_category": "wildfire",
            "target_action": "alert",
            "visual_summary": "New model-reviewed burn scar frame.",
            "labels": ["wildfire"],
            "reason_codes": ["burn_scar"],
            "confidence": 0.74,
            "quality": "usable",
            "temporal_evidence": "single frame only",
            "needs_human_review": False,
        }

    monkeypatch.setattr(retag_training_assets, "_ollama_retag", fake_ollama_retag)

    output = tmp_path / "retagged"
    manifest = retag_training_assets.retag_dataset(
        dataset,
        output,
        provider="ollama",
        model="qwen3.6:27b",
        scan_loose_assets=False,
        tag_temporal_sequences=False,
        max_provider_assets=-1,
        reuse_existing_dir=existing,
    )
    rows = _read_jsonl(output / "retagged_assets.jsonl")
    reused = [row for row in rows if row["reused_existing_tag"]]

    assert calls["count"] == 1
    assert manifest["provider_asset_calls"] == 1
    assert manifest["reused_asset_tags"] == 1
    assert len(reused) == 1
    assert reused[0]["retag"]["visual_summary"] == "Previously reviewed water extent frame."
