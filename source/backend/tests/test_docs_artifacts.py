from __future__ import annotations

import json
import hashlib
import re
from types import SimpleNamespace
from pathlib import Path

import av
from PIL import Image, ImageStat


REPO_ROOT = Path(__file__).resolve().parents[3]
MEDIA_SUFFIXES = {".gif", ".jpeg", ".jpg", ".mp4", ".png", ".webm"}


def _local_markdown_targets(markdown: str) -> list[str]:
    targets: list[str] = []
    for match in re.finditer(r"!?\[[^\]]*\]\(([^)]+)\)", markdown):
        raw = match.group(1).strip()
        if not raw or raw.startswith(("#", "http://", "https://", "mailto:")):
            continue
        target = raw.split("#", 1)[0].strip()
        if target:
            targets.append(target)
    return targets


def test_readme_local_links_and_images_exist():
    readme = REPO_ROOT / "README.md"
    markdown = readme.read_text(encoding="utf-8")

    missing = [
        target
        for target in _local_markdown_targets(markdown)
        if not (REPO_ROOT / target).exists()
    ]

    assert missing == []


def test_markdown_local_links_and_images_exist():
    markdown_roots = [
        REPO_ROOT / "README.md",
        *sorted((REPO_ROOT / "docs").rglob("*.md")),
        *sorted((REPO_ROOT / "source/backend/data").glob("*.md")),
    ]
    missing: list[tuple[str, str]] = []

    for path in markdown_roots:
        if not path.exists():
            continue
        markdown = path.read_text(encoding="utf-8", errors="ignore")
        for target in _local_markdown_targets(markdown):
            if not (path.parent / target).exists():
                missing.append((path.relative_to(REPO_ROOT).as_posix(), target))

    assert missing == []


def test_documented_demo_media_exists_and_is_nonempty():
    expected_media = [
        "docs/media/infographics/what-is-lfm-orbit-info.png",
        "docs/media/infographics/image-to-training-data-flow-info.png",
        "docs/media/infographics/app-usage-to-agent-growth-info.png",
        "docs/media/videos/showcase-demo.webm",
        "docs/media/videos/payload-reduction-demo.webm",
        "docs/media/videos/provenance-demo.webm",
        "docs/media/videos/abstain-safety-demo.webm",
        "docs/media/videos/object-evidence-demo.webm",
        "docs/media/videos/orbital-eclipse-demo.webm",
        "docs/media/videos/tutorial_video.webm",
        "docs/media/timelapse/highlight-greenland-ice-timelapse.gif",
        "docs/media/timelapse/highlight-greenland-ice-timelapse.webm",
        "docs/media/readme/readme-payload-reduction.png",
        "docs/media/readme/readme-orbital-eclipse.png",
        "docs/media/story-plates/story-critical-minerals-expansion.png",
        "docs/media/story-plates/story-object-evidence-port.png",
        "docs/media/readme/readme-provenance.png",
        "docs/media/readme/readme-ground-agent-playbook.png",
        "docs/media/readme/readme-ground-agent-chat-action.png",
        "docs/media/readme/readme-location-camera-context.png",
    ]

    missing_or_empty = []
    for rel_path in expected_media:
        path = REPO_ROOT / rel_path
        if not path.exists() or path.stat().st_size <= 0:
            missing_or_empty.append(rel_path)

    assert missing_or_empty == []


def test_public_readme_images_are_visually_nonblank():
    image_paths = [
        "docs/media/infographics/what-is-lfm-orbit-info.png",
        "docs/media/infographics/image-to-training-data-flow-info.png",
        "docs/media/infographics/app-usage-to-agent-growth-info.png",
        "docs/media/readme/readme-payload-reduction.png",
        "docs/media/readme/readme-orbital-eclipse.png",
        "docs/media/story-plates/story-critical-minerals-expansion.png",
        "docs/media/story-plates/story-object-evidence-port.png",
        "docs/media/readme/readme-provenance.png",
        "docs/media/readme/readme-ground-agent-playbook.png",
        "docs/media/readme/readme-ground-agent-chat-action.png",
        "docs/media/readme/readme-location-camera-context.png",
    ]
    failures: list[str] = []

    for rel_path in image_paths:
        path = REPO_ROOT / rel_path
        with Image.open(path) as image:
            width, height = image.size
            gray = image.convert("L")
            mean = float(ImageStat.Stat(gray).mean[0])
            y_min, y_max = gray.getextrema()
            luminance_range = float(y_max - y_min)
        if width < 480 or height < 270 or mean < 8 or mean > 247 or luminance_range < 20:
            failures.append(f"{rel_path}: {width}x{height}, mean={mean:.1f}, range={luminance_range:.1f}")

    assert failures == []


def test_public_demo_videos_are_temporal_and_nonblank():
    video_paths = [
        "docs/media/videos/showcase-demo.webm",
        "docs/media/videos/payload-reduction-demo.webm",
        "docs/media/videos/provenance-demo.webm",
        "docs/media/videos/abstain-safety-demo.webm",
        "docs/media/videos/object-evidence-demo.webm",
        "docs/media/videos/orbital-eclipse-demo.webm",
        "docs/media/videos/tutorial_video.webm",
        "docs/media/timelapse/highlight-greenland-ice-timelapse.webm",
    ]
    failures: list[str] = []

    for rel_path in video_paths:
        path = REPO_ROOT / rel_path
        duration_seconds, unique_hashes, visible_samples = _video_duration_and_sample_hashes(path)
        minimum_unique = 3 if "abstain-safety" in rel_path else 5
        if duration_seconds < 8 or len(unique_hashes) < minimum_unique or visible_samples < minimum_unique:
            failures.append(
                f"{rel_path}: duration={duration_seconds:.2f}, "
                f"unique_frames={len(unique_hashes)}, visible_samples={visible_samples}"
            )

    assert failures == []


def _video_duration_and_sample_hashes(path: Path) -> tuple[float, set[str], int]:
    """Sample video frames without requiring system ffmpeg/ffprobe binaries."""
    hashes: set[str] = set()
    visible_samples = 0
    with av.open(str(path)) as container:
        video_stream = next((stream for stream in container.streams if stream.type == "video"), None)
        assert video_stream is not None, f"{path} has no video stream"

        duration_seconds = 0.0
        if container.duration:
            duration_seconds = _duration_to_seconds(container.duration)
        elif video_stream.duration and video_stream.time_base:
            duration_seconds = float(video_stream.duration * video_stream.time_base)

        last_sample_second: int | None = None
        decoded_frames = 0
        for frame in container.decode(video=0):
            decoded_frames += 1
            timestamp = float(frame.pts * frame.time_base) if frame.pts is not None and frame.time_base else None
            sample_second = int(timestamp) if timestamp is not None else decoded_frames // 30
            if sample_second == last_sample_second:
                continue
            last_sample_second = sample_second

            image = frame.to_image().convert("L").resize((96, 54))
            mean = float(ImageStat.Stat(image).mean[0])
            y_min, y_max = image.getextrema()
            if 8 <= mean <= 247 and (y_max - y_min) >= 20:
                visible_samples += 1
            hashes.add(hashlib.md5(image.tobytes(), usedforsecurity=False).hexdigest())

        if duration_seconds <= 0 and decoded_frames and video_stream.average_rate:
            duration_seconds = float(decoded_frames / video_stream.average_rate)

    return duration_seconds, hashes, visible_samples


def _duration_to_seconds(raw_duration: int | float) -> float:
    """PyAV exposes some container durations as microseconds and others as time-base units."""
    seconds = float(raw_duration * av.time_base)
    if seconds > 24 * 60 * 60:
        return float(raw_duration) / 1_000_000.0
    return seconds


def test_docs_media_is_organized_under_media_subfolders():
    docs_root = REPO_ROOT / "docs"
    loose_media = sorted(
        path.name
        for path in docs_root.iterdir()
        if path.is_file() and path.suffix.lower() in MEDIA_SUFFIXES
    )
    expected_subfolders = {
        "infographics",
        "readme",
        "story-plates",
        "timelapse",
        "videos",
    }
    actual_subfolders = {
        path.name
        for path in (docs_root / "media").iterdir()
        if path.is_dir()
    }

    assert loose_media == []
    assert expected_subfolders.issubset(actual_subfolders)


def test_docs_user_and_dev_surfaces_are_separated():
    """Keep operator docs and maintenance docs in distinct folders."""
    docs_root = REPO_ROOT / "docs"
    user_docs = sorted(path.name for path in (docs_root / "user").glob("*.md"))
    dev_docs = sorted(path.name for path in (docs_root / "dev").glob("*.md"))
    archive_docs = sorted(path.name for path in (docs_root / "dev" / "archive").glob("*.md"))
    release_docs = sorted(path.name for path in (docs_root / "release").glob("*.md"))
    root_docs = sorted(path.name for path in docs_root.glob("*.md"))

    assert user_docs == ["DEMO_GUIDE.md", "OBJECT_EVIDENCE_MODE.md"]
    assert dev_docs == ["ARCHITECTURE.md", "DATASET_CYCLE_TUTORIAL.md", "MODEL_HANDOFF.md", "TODO.md"]
    assert release_docs == ["v0.4.0-public-proof.md"]
    assert root_docs == ["README.md"]
    assert {
        "AGENT_GROWTH_LOOP.md",
        "FUTURE_SENTINEL_LANES.md",
        "Liquid_AI_x_DPhi_Space_Hackathon_Criteria.md",
        "QA_PITFALLS.md",
        "SENTINEL_CLOSE_LOOKS.md",
    }.issubset(set(archive_docs))


def test_docs_media_files_are_referenced_by_markdown():
    markdown_roots = [
        REPO_ROOT / "README.md",
        *sorted((REPO_ROOT / "docs").rglob("*.md")),
        *sorted((REPO_ROOT / "source/backend/data").glob("*.md")),
    ]
    markdown = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in markdown_roots if path.exists())
    orphans = []

    for path in sorted((REPO_ROOT / "docs/media").rglob("*")):
        if not path.is_file() or path.suffix.lower() not in MEDIA_SUFFIXES:
            continue
        repo_rel = path.relative_to(REPO_ROOT).as_posix()
        docs_rel = path.relative_to(REPO_ROOT / "docs").as_posix()
        if repo_rel not in markdown and docs_rel not in markdown:
            orphans.append(repo_rel)

    assert orphans == []


def test_docs_do_not_reintroduce_retired_mission_evidence_ui():
    docs_paths = [
        REPO_ROOT / "README.md",
        *sorted((REPO_ROOT / "docs").rglob("*.md")),
    ]
    combined = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in docs_paths if path.exists())
    retired_active_claims = [
        "npm run demo:object-evidence",
        "Mission Control shows a target-pack selector",
        "VLM tools can run all enabled mission targets",
        "Visual evidence boxes now render with glowing semantic outlines",
        "the flow is wired through mission state, Mission Control",
        "target-pack selector, object chips",
    ]

    leaked = [claim for claim in retired_active_claims if claim in combined]

    assert leaked == []


def test_readme_timelapse_gif_fits_github_inline_limit():
    gif_path = REPO_ROOT / "docs/media/timelapse/highlight-greenland-ice-timelapse.gif"
    assert gif_path.exists()
    assert gif_path.stat().st_size <= 10 * 1024 * 1024


def test_summary_bank_references_existing_files():
    bank = json.loads((REPO_ROOT / "summary_bank.json").read_text(encoding="utf-8"))
    missing: list[tuple[str, str]] = []

    for group_name, group in bank.get("groups", {}).items():
        files = group.get("files") if isinstance(group, dict) else None
        if not isinstance(files, list):
            continue
        for rel_path in files:
            if isinstance(rel_path, str) and not (REPO_ROOT / rel_path).exists():
                missing.append((group_name, rel_path))

    assert missing == []


def test_readme_keeps_showcase_first_product_shape():
    markdown = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    required_sections = [
        "![What is LFM-ORBIT?](docs/media/infographics/what-is-lfm-orbit-info.png)",
        "## Run The Showcase",
        "## What It Proves",
        "## Proof Gallery",
        "## Validation Snapshot",
        "## Model + Training Loop",
        "## Run Locally",
        "## Limits",
        "## Docs",
    ]

    positions = [markdown.find(section) for section in required_sections]
    assert all(position >= 0 for position in positions)
    assert positions == sorted(positions)

    pre_showcase = markdown[: positions[1]]
    assert "\n## " not in pre_showcase
    assert "## Architecture In 60 Seconds" not in markdown
    assert "Public video playback is handled outside GitHub" not in markdown
    assert "## Verified Object Evidence" not in markdown
    assert "## Usage To Training Loop" not in markdown


def test_readme_documents_minimal_cold_start_prerequisites():
    markdown = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "Python `3.10+`" in markdown
    assert "Node.js `20.19.0`" in markdown
    assert "Node.js `22.12.0+`" in markdown
    assert "bootstrap repo-local `uv`" in markdown


def test_summary_bank_file_references_are_repo_relative():
    bank = json.loads((REPO_ROOT / "summary_bank.json").read_text(encoding="utf-8"))
    absolute_references: list[tuple[str, str]] = []

    for group_name, group in bank.get("groups", {}).items():
        files = group.get("files") if isinstance(group, dict) else None
        if not isinstance(files, list):
            continue
        for rel_path in files:
            if isinstance(rel_path, str) and Path(rel_path).is_absolute():
                absolute_references.append((group_name, rel_path))

    assert absolute_references == []


def test_summary_bank_file_groups_are_deduplicated():
    bank = json.loads((REPO_ROOT / "summary_bank.json").read_text(encoding="utf-8"))
    duplicates: list[tuple[str, str]] = []

    for group_name, group in bank.get("groups", {}).items():
        files = group.get("files") if isinstance(group, dict) else None
        if not isinstance(files, list):
            continue
        seen: set[str] = set()
        for rel_path in files:
            if not isinstance(rel_path, str):
                continue
            if rel_path in seen:
                duplicates.append((group_name, rel_path))
            seen.add(rel_path)

    assert duplicates == []


def test_visual_story_manifest_assets_exist_and_disclose_fixture_boxes():
    manifest_path = REPO_ROOT / "source/backend/assets/seeded_data/visual_story_frames/visual_story_manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stories = manifest.get("stories")
    assert isinstance(stories, list)

    public_outputs = {
        "docs/media/story-plates/story-critical-minerals-expansion.png",
        "docs/media/story-plates/story-object-evidence-port.png",
    }
    public_label_scope_terms = (
        "area",
        "zone",
        "group",
        "context",
        "region",
        "candidate",
        "sample",
        "corridor",
        "cluster",
        "row",
    )
    actual_outputs: set[str] = set()
    actual_public_outputs: set[str] = set()
    missing_assets: list[str] = []

    for story in stories:
        assert story.get("box_source") == "visual_story_fixture"
        assert story.get("imagery_origin") in {"sentinelhub_direct", "esri_context", "cached_api"}
        assert story.get("training_ready") is True
        assert "not a claim of live model-backed object detection" in story.get("note", "")

        for key in ("frame_path", "output_path"):
            rel_path = story.get(key)
            assert isinstance(rel_path, str)
            if not (REPO_ROOT / rel_path).exists():
                missing_assets.append(rel_path)
        output_path = story.get("output_path")
        if isinstance(output_path, str):
            actual_outputs.add(output_path)
            if story.get("public_docs") is True:
                actual_public_outputs.add(output_path)
                assert story.get("visual_audit_status") == "approved"
                audit_notes = story.get("visual_audit_notes")
                assert isinstance(audit_notes, list)
                assert audit_notes
                boxes = story.get("boxes")
                assert isinstance(boxes, list)
                for box in boxes:
                    label = box.get("label") if isinstance(box, dict) else None
                    assert isinstance(label, str)
                    assert any(term in label.lower() for term in public_label_scope_terms)
            elif output_path.startswith("docs/media/"):
                missing_assets.append(f"non_public_story_in_docs:{output_path}")

    assert missing_assets == []
    assert public_outputs == actual_public_outputs
    assert public_outputs.issubset(actual_outputs)


def test_targeted_visual_story_refresh_preserves_existing_manifest(monkeypatch, tmp_path):
    from scripts import build_visual_story_proofs as builder

    frame_root = tmp_path / "frames"
    frame_root.mkdir()
    manifest = frame_root / "visual_story_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "generated_at": "2026-05-01",
                "stories": [
                    {"story_id": "port", "output_path": "old-port.png"},
                    {"story_id": "road", "output_path": "old-road.png"},
                ],
            }
        ),
        encoding="utf-8",
    )

    stories = [SimpleNamespace(story_id="port"), SimpleNamespace(story_id="road")]

    def fake_build_story(story, *_args, **_kwargs):
        return {"story_id": story.story_id, "output_path": f"new-{story.story_id}.png", "source": "cached"}

    monkeypatch.setattr(builder, "FRAME_ROOT", frame_root)
    monkeypatch.setattr(builder, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(builder, "STORIES", stories)
    monkeypatch.setattr(builder, "_resolve_credentials", lambda: {"client_id": "", "client_secret": "", "source": ""})
    monkeypatch.setattr(builder, "build_story", fake_build_story)
    monkeypatch.setattr(builder.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr("sys.argv", ["build_visual_story_proofs.py", "--story", "port"])

    builder.main()

    refreshed = json.loads(manifest.read_text(encoding="utf-8"))
    by_id = {story["story_id"]: story for story in refreshed["stories"]}

    assert list(by_id) == ["port", "road"]
    assert by_id["port"]["output_path"] == "new-port.png"
    assert by_id["road"]["output_path"] == "old-road.png"
