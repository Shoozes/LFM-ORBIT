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
        *sorted(
            path
            for path in (REPO_ROOT / "docs").rglob("*.md")
            if "archive" not in path.relative_to(REPO_ROOT / "docs").parts
        ),
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
        "docs/media/videos/hosted-demo.webm",
        "docs/media/videos/payload-reduction-demo.webm",
        "docs/media/videos/provenance-demo.webm",
        "docs/media/videos/abstain-safety-demo.webm",
        "docs/media/videos/object-evidence-demo.webm",
        "docs/media/videos/orbital-eclipse-demo.webm",
        "docs/media/videos/training-journey.webm",
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
        "docs/media/videos/hosted-demo.webm",
        "docs/media/videos/payload-reduction-demo.webm",
        "docs/media/videos/provenance-demo.webm",
        "docs/media/videos/abstain-safety-demo.webm",
        "docs/media/videos/object-evidence-demo.webm",
        "docs/media/videos/orbital-eclipse-demo.webm",
        "docs/media/videos/training-journey.webm",
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
    legal_docs = sorted(path.name for path in (docs_root / "legal").glob("*.md"))
    release_docs = sorted(path.name for path in (docs_root / "release").glob("*.md"))
    root_docs = sorted(path.name for path in docs_root.glob("*.md"))

    assert user_docs == ["DEMO_GUIDE.md", "HOSTED_DEMO.md", "OBJECT_EVIDENCE_MODE.md"]
    assert dev_docs == [
        "ARCHITECTURE.md",
        "DATASET_CYCLE_TUTORIAL.md",
        "MODEL_HANDOFF.md",
        "PITFALL_LEDGER.md",
        "REPOSITORY_BOUNDARY.md",
        "SEEDED_DATA_REGISTRY.md",
        "TODO.md",
    ]
    assert legal_docs == ["THIRD_PARTY_NOTICES.md"]
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
        *sorted(
            path
            for path in (REPO_ROOT / "docs").rglob("*.md")
            if "archive" not in path.relative_to(REPO_ROOT / "docs").parts
        ),
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
        *sorted(
            path
            for path in (REPO_ROOT / "docs").rglob("*.md")
            if "archive" not in path.relative_to(REPO_ROOT / "docs").parts
        ),
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


def test_active_product_copy_excludes_retired_competition_framing():
    active_paths = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs/README.md",
        REPO_ROOT / "docs/dev/ARCHITECTURE.md",
        REPO_ROOT / "docs/dev/MODEL_HANDOFF.md",
        *sorted((REPO_ROOT / "docs/user").glob("*.md")),
        REPO_ROOT / "source/backend/data/README.md",
        REPO_ROOT / "source/backend/data/HF_DATASET_CARD.md",
        REPO_ROOT / "source/backend/core/ground_agent_knowledge.py",
    ]
    leaked = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in active_paths
        if "hackathon" in path.read_text(encoding="utf-8", errors="ignore").lower()
    ]
    assert leaked == []

    bank = json.loads((REPO_ROOT / "summary_bank.json").read_text(encoding="utf-8"))
    for group_name in ("issue_group_hackathon_scope_agent_first_polish", "issue_group_hackathon_release_qa"):
        assert bank["groups"][group_name].get("_archived") is True


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


def test_readme_keeps_run_first_product_shape():
    markdown = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    required_sections = [
        "![What is LFM-ORBIT?](docs/media/infographics/what-is-lfm-orbit-info.png)",
        "## Run The App",
        "## Record The Showcase",
        "## What It Proves",
        "## Proof Gallery",
        "## Validation Snapshot",
        "## Model + Training Loop",
        "## Requirements",
        "## Docs",
    ]

    positions = [markdown.find(section) for section in required_sections]
    assert all(position >= 0 for position in positions)
    assert positions == sorted(positions)

    pre_run = markdown[: positions[1]]
    assert "\n## " not in pre_run
    assert ".\\run.ps1" in markdown
    assert "Choose **1. Install/Repair + Fetch trained Orbit GGUF -> Run**." in markdown
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


def test_validation_snapshots_match_current_release_gate():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    todo = (REPO_ROOT / "docs/dev/TODO.md").read_text(encoding="utf-8")
    release = (REPO_ROOT / "docs/release/v0.4.0-public-proof.md").read_text(encoding="utf-8")

    assert "561 passed" in readme
    assert "561 passed" in release
    for source in (readme, release):
        assert "Playwright" in source
        assert "104 passed" not in source

    assert "Latest Validation Snapshot" not in todo
    assert "Current State" not in todo


def test_replay_rescan_docs_describe_cached_data_contract():
    docs = "\n".join(
        [
            (REPO_ROOT / "README.md").read_text(encoding="utf-8"),
            (REPO_ROOT / "docs/dev/ARCHITECTURE.md").read_text(encoding="utf-8"),
            (REPO_ROOT / "docs/dev/TODO.md").read_text(encoding="utf-8"),
            (REPO_ROOT / "docs/dev/MODEL_HANDOFF.md").read_text(encoding="utf-8"),
        ]
    )

    assert "Replay Cache" in docs
    assert "cached_rescan_current_model" in docs
    assert "Start Rescan" not in docs
    assert "live rescan" not in docs.lower()
    assert "current runtime/model stack" not in docs


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


def test_active_docs_fit_maintenance_budgets():
    budgets = {
        "README.md": 25 * 1024,
        "docs/dev/ARCHITECTURE.md": 12 * 1024,
        "docs/dev/TODO.md": 8 * 1024,
        "docs/user/HOSTED_DEMO.md": 6 * 1024,
        "docs/user/DEMO_GUIDE.md": 6 * 1024,
    }
    active_docs = [
        REPO_ROOT / "README.md",
        *sorted(
            path
            for path in (REPO_ROOT / "docs").rglob("*.md")
            if "archive" not in path.relative_to(REPO_ROOT / "docs").parts
        ),
    ]
    oversized = []
    for path in active_docs:
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative.startswith("docs/legal/"):
            continue
        limit = budgets.get(relative, 10 * 1024)
        if path.stat().st_size > limit:
            oversized.append((relative, path.stat().st_size, limit))

    assert oversized == []


def test_summary_bank_defaults_and_archived_routes_are_recoverable():
    bank = json.loads((REPO_ROOT / "summary_bank.json").read_text(encoding="utf-8"))
    default_groups = bank["defaults"]["groups"]

    assert default_groups
    assert all(group in bank["groups"] for group in default_groups)
    assert all(not bank["groups"][group].get("_archived") for group in default_groups)

    for group_name, group in bank["groups"].items():
        if not group.get("_archived"):
            assert group.get("description"), group_name
            continue

        archive_ref = group.get("_archive_ref", "")
        assert "#groups." in archive_ref, group_name
        archive_path, archived_name = archive_ref.split("#groups.", 1)
        archive = json.loads((REPO_ROOT / archive_path).read_text(encoding="utf-8"))
        assert archive["schema"] == "summary_bank_archive_v1"
        assert archived_name == group_name
        assert group_name in archive["groups"]


def test_public_model_handoff_matches_current_repo_identity_and_runtime_boundary():
    handoff = json.loads(
        (REPO_ROOT / "docs/model/orbit_model_handoff.json").read_text(encoding="utf-8")
    )

    assert handoff["producer"]["name"] == "GenUni"
    assert handoff["source"]["repo_id"] == "Shoozes/lfm2.5-450m-vl-orbit-satellite"
    assert handoff["source"]["revision"] == "0fc90b8caaa6b8e07d1dc0a9125969c2730e4353"
    assert handoff["source"]["file_sha256"] == "9e488f38f64dc4b897c768bec4b37ba01a671309910fd08c470220fa244e14f6"
    assert handoff["source"]["file_bytes"] == 219310432
    assert handoff["runtime"]["mmproj_filename"] == ""
    assert handoff["artifact"]["browser_manifest"] == "source/frontend/hosted/model-manifest.json"

    manifest = json.loads(
        (REPO_ROOT / "source/frontend/hosted/model-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["revision"] == handoff["source"]["revision"]
    assert manifest["sha256"] == handoff["source"]["file_sha256"]
    assert manifest["bytes"] == handoff["source"]["file_bytes"]
    assert manifest["capabilities"] == {"textReasoning": True, "imageInput": False, "mmproj": None}


def test_summary_bank_tracks_current_hosted_integrity_surfaces():
    bank = json.loads((REPO_ROOT / "summary_bank.json").read_text(encoding="utf-8"))
    hosted = bank["groups"]["feature_group_hosted_browser_portfolio"]
    coordinator = bank["groups"]["issue_group_scan_producer_and_agent_deduplication"]

    assert "source/frontend/hosted/demoPackages.ts" in hosted["files"]
    assert "source/frontend/public/demo-packages/index.json" in hosted["files"]
    assert "source/frontend/hosted/model-manifest.json" in hosted["files"]
    assert "source/frontend/hosted/HostedEvidenceDemo.tsx" in hosted["files"]
    pages = bank["groups"]["issue_group_hosted_pages_path_and_deployment"]
    assert "source/frontend/e2e/hosted.pages.live.static.spec.ts" in pages["files"]
    assert "source/frontend/playwright.hosted.pages.live.static.config.ts" in pages["files"]
    scanner = bank["groups"]["issue_group_scan_producer_and_agent_deduplication"]
    assert "source/backend/core/acquisition.py" in scanner["files"]
    assert "source/frontend/e2e/hosted.pages.spec.ts" in pages["files"]
    assert "source/frontend/playwright.hosted.pages.config.ts" in pages["files"]
    assert "source/frontend/vite.config.ts" in hosted["files"]
    assert "source/backend/core/scan_coordinator.py" in coordinator["files"]


def test_hosted_demo_packages_are_versioned_and_trace_to_saved_replays():
    manifest = json.loads(
        (REPO_ROOT / "source/frontend/public/demo-packages/index.json").read_text(encoding="utf-8")
    )
    assert manifest["schemaVersion"] == 2
    packages = manifest["packages"]
    assert packages
    package_ids = {package["id"] for package in packages}
    assert len(package_ids) == len(packages)

    for package in packages:
        image_src = package.get("imageSrc")
        image_alt = package.get("imageAlt")
        assert isinstance(image_src, str)
        assert re.fullmatch(r"demo-assets/[a-z0-9._/-]+", image_src)
        assert isinstance(image_alt, str) and image_alt.strip()
        image_path = REPO_ROOT / "source/frontend/public" / image_src
        assert image_path.exists(), package["id"]
        with Image.open(image_path) as image:
            assert image.width >= 480 and image.height >= 270, package["id"]

        evidence = package["evidence"]
        assert evidence["runtimeTruthMode"] == "replay"
        assert evidence["imageryOrigin"] == "cached_api"
        assert evidence["retentionDecision"] in {"candidate", "review", "abstain"}
        bbox = evidence["bbox"]
        assert len(bbox) == 4
        assert bbox[0] < bbox[2] and bbox[1] < bbox[3]
        source_asset = evidence["sourceAsset"]
        assert re.fullmatch(r"source/backend/assets/replays/[a-z0-9_]+\.json", source_asset)
        replay_path = REPO_ROOT / source_asset
        assert replay_path.exists(), package["id"]
        replay = json.loads(replay_path.read_text(encoding="utf-8"))
        assert replay["replay_id"] == evidence["sourceReplayId"]
        assert list(replay["bbox"]) == bbox
        first_alert = replay["alerts"][0]
        runtime_truth_mode = replay.get("runtime_truth_mode") or first_alert.get("runtime_truth_mode") or "replay"
        imagery_origin = replay.get("imagery_origin") or first_alert.get("imagery_origin") or "cached_api"
        scoring_basis = replay.get("scoring_basis") or first_alert.get("scoring_basis") or "visual_only"
        assert runtime_truth_mode == "replay"
        assert imagery_origin == "cached_api"
        assert scoring_basis == evidence["scoringBasis"]


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
