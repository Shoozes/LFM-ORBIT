"""Retag exported Orbit image assets into deduplicated training rows.

The script is intentionally self-contained so it can be run from an exported
dataset directory:

    python retag_training_assets.py --dataset-dir . --provider heuristic

It expands still images and timelapse videos into unique image assets, dedupes
by SHA-256, preserves references back to every source sample, and writes both
Orbit JSONL and Hugging Face ImageFolder-style metadata.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import imageio.v3 as iio
import numpy as np
from PIL import Image


_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_UNSUPPORTED_IMAGE_SUFFIXES = {".svg"}
_VIDEO_SUFFIXES = {".webm", ".mp4", ".mov", ".m4v"}
_JSONL_SKIP_NAMES = {
    "training.jsonl",
    "train_training.jsonl",
    "eval_training.jsonl",
    "retagged_assets.jsonl",
    "training_assets.jsonl",
    "metadata.jsonl",
    "review_queue.jsonl",
    "skipped_assets.jsonl",
    "tagger_failures.jsonl",
    "temporal_sequences.jsonl",
    "training_temporal_sequences.jsonl",
    "sequence_tagger_failures.jsonl",
}
_DEFAULT_OUTPUT_DIR = "retagged_training"
_PROMPT_VERSION = "orbit_asset_retag_prompt_v1"
_SCRIPT_VERSION = "orbit_retag_training_assets_v1"
_HF_IMAGE_DIR = "images"
_DEFAULT_OLLAMA_MODEL = "qwen3.6:27b"


@dataclass
class AssetRef:
    sample_id: str | None
    asset_key: str
    record_type: str | None = None
    target_task: str | None = None
    target_category: str | None = None
    target_action: str | None = None
    observation_source: str | None = None
    reason_codes: list[str] = field(default_factory=list)
    source: str = "sample_record"
    video_source: str | None = None
    frame_index: int | None = None


@dataclass
class AssetCandidate:
    path: Path
    source_kind: str
    asset_key: str
    refs: list[AssetRef] = field(default_factory=list)


@dataclass
class TemporalSequenceCandidate:
    video_path: Path
    refs: list[AssetRef]
    frame_candidates: list[AssetCandidate]
    decoded_frames_count: int
    sampled_indices: list[int]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned.strip("._") or "asset"


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _should_skip_path(path: Path, dataset_dir: Path, output_dir: Path) -> bool:
    parts = {part.lower() for part in path.relative_to(dataset_dir).parts if part}
    if _is_relative_to(path, output_dir):
        return True
    return bool(parts & {".git", "__pycache__", "node_modules", "playwright-report", "test-results"})


def _record_ref(record: dict[str, Any], asset_key: str, *, source: str = "sample_record") -> AssetRef:
    return AssetRef(
        sample_id=str(record.get("sample_id") or record.get("event_id") or "") or None,
        asset_key=asset_key,
        record_type=str(record.get("record_type") or "") or None,
        target_task=str(record.get("target_task") or "") or None,
        target_category=str(record.get("target_category") or "") or None,
        target_action=str(record.get("target_action") or "") or None,
        observation_source=str(record.get("observation_source") or "") or None,
        reason_codes=[str(item) for item in record.get("reason_codes", []) if item],
        source=source,
    )


def _load_records(dataset_dir: Path, output_dir: Path) -> list[dict[str, Any]]:
    primary = dataset_dir / "samples.jsonl"
    if primary.exists():
        return _read_jsonl(primary)

    records_by_key: dict[str, dict[str, Any]] = {}
    for path in sorted(dataset_dir.rglob("*.jsonl")):
        if _should_skip_path(path, dataset_dir, output_dir) or path.name in _JSONL_SKIP_NAMES:
            continue
        for record in _read_jsonl(path):
            key = str(record.get("sample_id") or record.get("event_id") or record.get("cell_id") or "")
            if key:
                records_by_key.setdefault(key, record)
    return list(records_by_key.values())


def _iter_asset_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str)]
    if isinstance(value, dict):
        values: list[str] = []
        for nested in value.values():
            values.extend(_iter_asset_values(nested))
        return values
    return []


def _resolve_asset_path(dataset_dir: Path, record: dict[str, Any], asset_value: str) -> Path | None:
    if not asset_value or asset_value.startswith(("http://", "https://", "data:")):
        return None

    raw = Path(asset_value)
    if raw.is_absolute() and raw.exists():
        return raw

    sample_id = str(record.get("sample_id") or "")
    candidates: list[Path] = []
    if sample_id:
        candidates.append(dataset_dir / "samples" / sample_id / raw)
    candidates.append(dataset_dir / raw)
    candidates.append(dataset_dir / "images" / raw.name)

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _collect_record_assets(dataset_dir: Path, output_dir: Path) -> tuple[list[AssetCandidate], list[dict[str, Any]]]:
    candidates: list[AssetCandidate] = []
    skipped: list[dict[str, Any]] = []

    for record in _load_records(dataset_dir, output_dir):
        assets = record.get("assets") if isinstance(record.get("assets"), dict) else {}
        for asset_key, raw_value in assets.items():
            for asset_value in _iter_asset_values(raw_value):
                path = _resolve_asset_path(dataset_dir, record, asset_value)
                if path is None:
                    skipped.append({
                        "reason": "unresolved_asset_path",
                        "sample_id": record.get("sample_id"),
                        "asset_key": asset_key,
                        "asset_value": asset_value,
                    })
                    continue
                suffix = path.suffix.lower()
                if suffix in _IMAGE_SUFFIXES:
                    candidates.append(AssetCandidate(path=path, source_kind="image", asset_key=str(asset_key), refs=[_record_ref(record, str(asset_key))]))
                elif suffix in _VIDEO_SUFFIXES:
                    candidates.append(AssetCandidate(path=path, source_kind="video", asset_key=str(asset_key), refs=[_record_ref(record, str(asset_key))]))
                elif suffix in _UNSUPPORTED_IMAGE_SUFFIXES:
                    skipped.append({
                        "reason": "unsupported_svg_for_vision_retag",
                        "sample_id": record.get("sample_id"),
                        "asset_key": asset_key,
                        "path": str(path),
                    })
    return candidates, skipped


def _collect_loose_assets(dataset_dir: Path, output_dir: Path) -> tuple[list[AssetCandidate], list[dict[str, Any]]]:
    candidates: list[AssetCandidate] = []
    skipped: list[dict[str, Any]] = []
    for path in sorted(dataset_dir.rglob("*")):
        if not path.is_file() or _should_skip_path(path, dataset_dir, output_dir):
            continue
        suffix = path.suffix.lower()
        if suffix in _IMAGE_SUFFIXES:
            candidates.append(AssetCandidate(
                path=path,
                source_kind="image",
                asset_key=path.stem,
                refs=[AssetRef(sample_id=None, asset_key=path.name, source="loose_scan")],
            ))
        elif suffix in _VIDEO_SUFFIXES:
            candidates.append(AssetCandidate(
                path=path,
                source_kind="video",
                asset_key=path.stem,
                refs=[AssetRef(sample_id=None, asset_key=path.name, source="loose_scan")],
            ))
        elif suffix in _UNSUPPORTED_IMAGE_SUFFIXES:
            skipped.append({"reason": "unsupported_svg_for_vision_retag", "path": str(path)})
    return candidates, skipped


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    return "application/octet-stream"


def _image_data_url(path: Path) -> str:
    return f"data:{_mime_type(path)};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _save_frame(frame: np.ndarray, output_path: Path) -> None:
    image = Image.fromarray(frame).convert("RGB")
    image.save(output_path, format="JPEG", quality=92)


def _sample_indices(count: int, target: int) -> list[int]:
    if count <= 0:
        return []
    target = max(1, min(target, count))
    if target == 1:
        return [0]
    span = count - 1
    return sorted({round(index * span / (target - 1)) for index in range(target)})


def _read_video_frames(path: Path) -> list[np.ndarray]:
    try:
        return [np.asarray(frame) for frame in iio.imiter(path, plugin="pyav")]
    except Exception:
        return [np.asarray(frame) for frame in iio.imiter(path)]


def _extract_video_frames(
    candidate: AssetCandidate,
    frames_dir: Path,
    *,
    frame_count: int,
    min_video_frames: int,
) -> tuple[list[AssetCandidate], TemporalSequenceCandidate | None, list[dict[str, Any]]]:
    frames_dir.mkdir(parents=True, exist_ok=True)
    skipped: list[dict[str, Any]] = []
    try:
        frames = _read_video_frames(candidate.path)
    except Exception as exc:
        return [], None, [{"reason": "video_decode_failed", "path": str(candidate.path), "error": str(exc)}]

    if len(frames) < min_video_frames:
        return [], None, [{
            "reason": "invalid_timelapse_too_few_frames",
            "path": str(candidate.path),
            "frames_count": len(frames),
            "minimum_frames": min_video_frames,
        }]

    expanded: list[AssetCandidate] = []
    sampled_indices = _sample_indices(len(frames), frame_count)
    video_key = _sha256(candidate.path)[:16]
    for index in sampled_indices:
        frame_path = frames_dir / f"{_safe_name(candidate.path.stem)}_{video_key}__frame_{index:04d}.jpg"
        _save_frame(frames[index], frame_path)
        refs = []
        for ref in candidate.refs:
            refs.append(AssetRef(
                sample_id=ref.sample_id,
                asset_key=f"{ref.asset_key}:frame_{index}",
                record_type=ref.record_type,
                target_task=ref.target_task,
                target_category=ref.target_category,
                target_action=ref.target_action,
                observation_source=ref.observation_source,
                reason_codes=list(ref.reason_codes),
                source=ref.source,
                video_source=str(candidate.path),
                frame_index=index,
            ))
        expanded.append(AssetCandidate(
            path=frame_path,
            source_kind="video_frame",
            asset_key=f"{candidate.asset_key}:frame_{index}",
            refs=refs,
        ))
    sequence = TemporalSequenceCandidate(
        video_path=candidate.path,
        refs=candidate.refs,
        frame_candidates=expanded,
        decoded_frames_count=len(frames),
        sampled_indices=sampled_indices,
    )
    return expanded, sequence, skipped


def _merge_candidates_by_path(candidates: list[AssetCandidate]) -> list[AssetCandidate]:
    merged: dict[Path, AssetCandidate] = {}
    for candidate in candidates:
        key = candidate.path.resolve()
        if key not in merged:
            merged[key] = AssetCandidate(
                path=candidate.path,
                source_kind=candidate.source_kind,
                asset_key=candidate.asset_key,
                refs=[],
            )
        merged[key].refs.extend(candidate.refs)
    return list(merged.values())


def _dedupe_image_candidates(candidates: list[AssetCandidate]) -> dict[str, AssetCandidate]:
    by_hash: dict[str, AssetCandidate] = {}
    for candidate in candidates:
        digest = _sha256(candidate.path)
        if digest not in by_hash:
            by_hash[digest] = AssetCandidate(
                path=candidate.path,
                source_kind=candidate.source_kind,
                asset_key=candidate.asset_key,
                refs=[],
            )
        by_hash[digest].refs.extend(candidate.refs)
    return by_hash


def _refs_to_json(refs: list[AssetRef]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ref in refs:
        payload = {
            "sample_id": ref.sample_id,
            "asset_key": ref.asset_key,
            "record_type": ref.record_type,
            "target_task": ref.target_task,
            "target_category": ref.target_category,
            "target_action": ref.target_action,
            "observation_source": ref.observation_source,
            "reason_codes": ref.reason_codes,
            "source": ref.source,
            "video_source": ref.video_source,
            "frame_index": ref.frame_index,
        }
        key = json.dumps(payload, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        payloads.append(payload)
    return payloads


def _reference_consensus(refs: list[AssetRef]) -> dict[str, Any]:
    def first_value(attr: str) -> str | None:
        for ref in refs:
            value = getattr(ref, attr)
            if value:
                return str(value)
        return None

    reason_codes: list[str] = []
    for ref in refs:
        for code in ref.reason_codes:
            if code not in reason_codes:
                reason_codes.append(code)
    return {
        "target_task": first_value("target_task") or "temporal_change_review",
        "target_category": first_value("target_category") or "unknown",
        "target_action": first_value("target_action") or "review",
        "observation_source": first_value("observation_source") or "unknown",
        "reason_codes": reason_codes,
    }


def _prompt_for_asset(candidate: AssetCandidate, refs: list[AssetRef]) -> str:
    consensus = _reference_consensus(refs)
    return (
        "You are retagging Earth-observation imagery for a training dataset. "
        "Return JSON only, no markdown. Use this schema: "
        "{"
        "\"target_category\": string, "
        "\"target_action\": \"alert\"|\"review\"|\"prune\"|\"discard\"|\"unknown\", "
        "\"visual_summary\": string, "
        "\"labels\": [string], "
        "\"reason_codes\": [string], "
        "\"confidence\": number, "
        "\"quality\": \"usable\"|\"low_quality\"|\"invalid\", "
        "\"temporal_evidence\": string, "
        "\"needs_human_review\": boolean"
        "}. "
        "If the image is a single frame from a timelapse, label only what is visible in that frame; "
        "do not claim temporal change unless the metadata supports it. "
        f"Asset kind: {candidate.source_kind}. "
        f"Existing metadata: {json.dumps(consensus, sort_keys=True)}"
    )


def _prompt_for_sequence(sequence: TemporalSequenceCandidate) -> str:
    consensus = _reference_consensus(sequence.refs)
    return (
        "You are retagging an ordered satellite timelapse for temporal-change training. "
        "Return JSON only, no markdown. Use this schema: "
        "{"
        "\"target_category\": string, "
        "\"target_action\": \"alert\"|\"review\"|\"prune\"|\"discard\"|\"unknown\", "
        "\"temporal_summary\": string, "
        "\"change_labels\": [string], "
        "\"reason_codes\": [string], "
        "\"confidence\": number, "
        "\"sequence_quality\": \"usable\"|\"low_quality\"|\"invalid\", "
        "\"temporal_validity\": \"multi_frame_context\"|\"static_or_duplicate_frames\"|\"unclear\", "
        "\"needs_human_review\": boolean"
        "}. "
        "A true timelapse requires contextual imagery slices changing over time. "
        "If frames appear duplicated or only color-tinted, mark temporal_validity as static_or_duplicate_frames. "
        f"Decoded frames: {sequence.decoded_frames_count}; sampled positions: {sequence.sampled_indices}. "
        f"Existing metadata: {json.dumps(consensus, sort_keys=True)}"
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    payload_text = match.group(0) if match else stripped
    payload = json.loads(payload_text)
    if not isinstance(payload, dict):
        raise ValueError("provider response was not a JSON object")
    return payload


def _heuristic_retag(candidate: AssetCandidate, refs: list[AssetRef], model: str) -> dict[str, Any]:
    consensus = _reference_consensus(refs)
    labels = [str(consensus["target_category"])]
    labels.extend(str(code) for code in consensus["reason_codes"])
    labels = [label for index, label in enumerate(labels) if label and label not in labels[:index]]
    if candidate.source_kind == "video_frame":
        labels.append("timelapse_frame")
    return {
        "target_category": consensus["target_category"],
        "target_action": consensus["target_action"],
        "visual_summary": (
            f"{candidate.source_kind.replace('_', ' ')} asset for "
            f"{consensus['target_task']} from {consensus['observation_source']}."
        ),
        "labels": labels,
        "reason_codes": consensus["reason_codes"],
        "confidence": 0.0,
        "quality": "usable",
        "temporal_evidence": "metadata_inherited; visual retag not model-generated",
        "needs_human_review": True,
        "provider_note": f"heuristic labels generated locally by {model}",
    }


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def _ollama_retag(
    candidate: AssetCandidate,
    refs: list[AssetRef],
    model: str,
    *,
    base_url: str,
    timeout: float,
) -> dict[str, Any]:
    image_b64 = base64.b64encode(candidate.path.read_bytes()).decode("ascii")
    payload = {
        "model": model,
        "prompt": _prompt_for_asset(candidate, refs),
        "images": [image_b64],
        "format": "json",
        "stream": False,
        "think": False,
    }
    response = _post_json(
        f"{base_url.rstrip('/')}/api/generate",
        payload,
        {"Content-Type": "application/json"},
        timeout,
    )
    return _extract_json_object(str(response.get("response") or ""))


def _openai_output_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return str(response["output_text"])
    chunks: list[str] = []
    for output in response.get("output", []):
        if not isinstance(output, dict):
            continue
        for content in output.get("content", []):
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "\n".join(chunks)


def _openai_retag(
    candidate: AssetCandidate,
    refs: list[AssetRef],
    model: str,
    *,
    api_key: str,
    base_url: str,
    detail: str,
    timeout: float,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": _prompt_for_asset(candidate, refs)},
                    {"type": "input_image", "image_url": _image_data_url(candidate.path), "detail": detail},
                ],
            }
        ],
    }
    response = _post_json(
        f"{base_url.rstrip('/')}/responses",
        payload,
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        timeout,
    )
    return _extract_json_object(_openai_output_text(response))


def _heuristic_sequence_retag(sequence: TemporalSequenceCandidate, model: str, frame_hashes: list[str]) -> dict[str, Any]:
    consensus = _reference_consensus(sequence.refs)
    unique_frame_count = len(set(frame_hashes))
    temporal_validity = (
        "multi_frame_context"
        if unique_frame_count >= 2 and sequence.decoded_frames_count >= 2
        else "static_or_duplicate_frames"
    )
    labels = [str(consensus["target_category"]), "timelapse_sequence"]
    labels.extend(str(code) for code in consensus["reason_codes"])
    labels = [label for index, label in enumerate(labels) if label and label not in labels[:index]]
    return {
        "target_category": consensus["target_category"],
        "target_action": consensus["target_action"],
        "temporal_summary": (
            f"Ordered timelapse sequence for {consensus['target_task']} with "
            f"{unique_frame_count} unique sampled frames from {sequence.decoded_frames_count} decoded frames."
        ),
        "change_labels": labels,
        "reason_codes": consensus["reason_codes"],
        "confidence": 0.0,
        "sequence_quality": "usable" if temporal_validity == "multi_frame_context" else "invalid",
        "temporal_validity": temporal_validity,
        "needs_human_review": True,
        "provider_note": f"heuristic temporal labels generated locally by {model}",
    }


def _ollama_sequence_retag(
    sequence: TemporalSequenceCandidate,
    model: str,
    *,
    base_url: str,
    timeout: float,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "prompt": _prompt_for_sequence(sequence),
        "images": [base64.b64encode(frame.path.read_bytes()).decode("ascii") for frame in sequence.frame_candidates],
        "format": "json",
        "stream": False,
        "think": False,
    }
    response = _post_json(
        f"{base_url.rstrip('/')}/api/generate",
        payload,
        {"Content-Type": "application/json"},
        timeout,
    )
    return _extract_json_object(str(response.get("response") or ""))


def _openai_sequence_retag(
    sequence: TemporalSequenceCandidate,
    model: str,
    *,
    api_key: str,
    base_url: str,
    detail: str,
    timeout: float,
) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "input_text", "text": _prompt_for_sequence(sequence)}]
    for frame in sequence.frame_candidates:
        content.append({"type": "input_image", "image_url": _image_data_url(frame.path), "detail": detail})
    payload = {"model": model, "input": [{"role": "user", "content": content}]}
    response = _post_json(
        f"{base_url.rstrip('/')}/responses",
        payload,
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        timeout,
    )
    return _extract_json_object(_openai_output_text(response))


def _normalize_retag(payload: dict[str, Any]) -> dict[str, Any]:
    labels = payload.get("labels") if isinstance(payload.get("labels"), list) else []
    reason_codes = payload.get("reason_codes") if isinstance(payload.get("reason_codes"), list) else []
    try:
        confidence = max(0.0, min(float(payload.get("confidence", 0.0)), 1.0))
    except (TypeError, ValueError):
        confidence = 0.0
    quality = str(payload.get("quality") or "usable")
    if quality not in {"usable", "low_quality", "invalid"}:
        quality = "usable"
    return {
        "target_category": str(payload.get("target_category") or "unknown"),
        "target_action": str(payload.get("target_action") or "review"),
        "visual_summary": str(payload.get("visual_summary") or ""),
        "labels": [str(item) for item in labels if item],
        "reason_codes": [str(item) for item in reason_codes if item],
        "confidence": confidence,
        "quality": quality,
        "temporal_evidence": str(payload.get("temporal_evidence") or ""),
        "needs_human_review": bool(payload.get("needs_human_review", quality != "usable")),
    }


def _normalize_sequence_retag(payload: dict[str, Any]) -> dict[str, Any]:
    labels = payload.get("change_labels") if isinstance(payload.get("change_labels"), list) else []
    reason_codes = payload.get("reason_codes") if isinstance(payload.get("reason_codes"), list) else []
    try:
        confidence = max(0.0, min(float(payload.get("confidence", 0.0)), 1.0))
    except (TypeError, ValueError):
        confidence = 0.0
    quality = str(payload.get("sequence_quality") or "usable")
    if quality not in {"usable", "low_quality", "invalid"}:
        quality = "usable"
    validity = str(payload.get("temporal_validity") or "unclear")
    if validity not in {"multi_frame_context", "static_or_duplicate_frames", "unclear"}:
        validity = "unclear"
    return {
        "target_category": str(payload.get("target_category") or "unknown"),
        "target_action": str(payload.get("target_action") or "review"),
        "temporal_summary": str(payload.get("temporal_summary") or ""),
        "change_labels": [str(item) for item in labels if item],
        "reason_codes": [str(item) for item in reason_codes if item],
        "confidence": confidence,
        "sequence_quality": quality,
        "temporal_validity": validity,
        "needs_human_review": bool(payload.get("needs_human_review", quality != "usable" or validity != "multi_frame_context")),
    }


def _copy_unique_image(source: Path, images_dir: Path, asset_id: str) -> str:
    images_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".jpg" if source.suffix.lower() == ".jpeg" else source.suffix.lower()
    target = images_dir / f"{asset_id}{suffix}"
    if not target.exists():
        shutil.copyfile(source, target)
    return f"{_HF_IMAGE_DIR}/{target.name}"


def _load_existing_retag_rows(existing_dir: Path | None, filename: str, key_name: str) -> dict[str, dict[str, Any]]:
    if existing_dir is None:
        return {}
    path = existing_dir / filename
    if not path.exists():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(path):
        key = str(row.get(key_name) or "")
        if key and isinstance(row.get("retag"), dict):
            rows.setdefault(key, row)
    return rows


def retag_dataset(
    dataset_dir: Path,
    output_dir: Path,
    *,
    provider: str = "heuristic",
    model: str | None = None,
    frame_count: int = 4,
    min_video_frames: int = 2,
    tag_temporal_sequences: bool = True,
    scan_loose_assets: bool = True,
    ollama_base_url: str = "http://127.0.0.1:11434",
    openai_base_url: str = "https://api.openai.com/v1",
    openai_detail: str = "low",
    timeout: float = 120.0,
    sleep_seconds: float = 0.0,
    max_provider_assets: int | None = None,
    max_provider_sequences: int | None = None,
    reuse_existing_dir: Path | None = None,
    reuse_existing_sequences: bool = True,
    tagger: Callable[[AssetCandidate, list[AssetRef], str], dict[str, Any]] | None = None,
    sequence_tagger: Callable[[TemporalSequenceCandidate, str, list[str]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    dataset_dir = dataset_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    reuse_existing_dir = reuse_existing_dir.resolve() if reuse_existing_dir else None
    frames_dir = output_dir / "frames"
    images_dir = output_dir / _HF_IMAGE_DIR

    model_name = model or {
        "heuristic": "orbit_heuristic_v1",
        "queue": "manual_review_queue",
        "ollama": _DEFAULT_OLLAMA_MODEL,
        "openai": "gpt-4.1-mini",
    }.get(provider, "orbit_heuristic_v1")

    existing_asset_rows = _load_existing_retag_rows(reuse_existing_dir, "retagged_assets.jsonl", "asset_sha256")
    existing_sequence_rows = (
        _load_existing_retag_rows(reuse_existing_dir, "temporal_sequences.jsonl", "video_sha256")
        if reuse_existing_sequences
        else {}
    )

    record_candidates, skipped = _collect_record_assets(dataset_dir, output_dir)
    candidates = record_candidates
    if scan_loose_assets:
        loose_candidates, loose_skipped = _collect_loose_assets(dataset_dir, output_dir)
        candidates.extend(loose_candidates)
        skipped.extend(loose_skipped)

    expanded_candidates: list[AssetCandidate] = []
    sequence_candidates: list[TemporalSequenceCandidate] = []
    for candidate in _merge_candidates_by_path(candidates):
        if candidate.source_kind == "video":
            frame_candidates, sequence, frame_skipped = _extract_video_frames(
                candidate,
                frames_dir,
                frame_count=frame_count,
                min_video_frames=min_video_frames,
            )
            expanded_candidates.extend(frame_candidates)
            if sequence is not None:
                sequence_candidates.append(sequence)
            skipped.extend(frame_skipped)
        else:
            expanded_candidates.append(candidate)

    unique = _dedupe_image_candidates(expanded_candidates)
    asset_rows: list[dict[str, Any]] = []
    training_rows: list[dict[str, Any]] = []
    sequence_rows: list[dict[str, Any]] = []
    sequence_training_rows: list[dict[str, Any]] = []
    metadata_rows: list[dict[str, Any]] = []
    queue_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    sequence_failures: list[dict[str, Any]] = []
    digest_to_file: dict[str, str] = {}
    provider_asset_calls = 0
    provider_sequence_calls = 0
    provider_budget_fallbacks = 0
    provider_sequence_budget_fallbacks = 0
    reused_asset_tags = 0
    reused_sequence_tags = 0

    def provider_budget_allows(limit: int | None, used: int) -> bool:
        if limit is None or limit < 0:
            return True
        if limit == 0:
            return False
        return used < limit

    for index, (digest, candidate) in enumerate(sorted(unique.items()), start=1):
        asset_id = digest[:16]
        refs = candidate.refs
        image_file = _copy_unique_image(candidate.path, images_dir, asset_id)
        digest_to_file[digest] = image_file
        prompt = _prompt_for_asset(candidate, refs)
        asset_provider = provider
        asset_model = model_name
        existing_asset_row = existing_asset_rows.get(digest)

        if existing_asset_row is not None:
            reused_asset_tags += 1
            asset_provider = str(existing_asset_row.get("provider") or "reused")
            asset_model = str(existing_asset_row.get("model") or model_name)
            retag = _normalize_retag(existing_asset_row.get("retag") or {})
        else:
            try:
                if tagger is not None:
                    raw_retag = tagger(candidate, refs, model_name)
                elif provider == "queue":
                    raw_retag = _heuristic_retag(candidate, refs, asset_model)
                elif provider == "ollama":
                    if provider_budget_allows(max_provider_assets, provider_asset_calls):
                        provider_asset_calls += 1
                        raw_retag = _ollama_retag(
                            candidate,
                            refs,
                            model_name,
                            base_url=ollama_base_url,
                            timeout=timeout,
                        )
                    else:
                        provider_budget_fallbacks += 1
                        asset_provider = "heuristic"
                        asset_model = "orbit_heuristic_budget_fallback_v1"
                        raw_retag = _heuristic_retag(candidate, refs, asset_model)
                elif provider == "openai":
                    api_key = os.getenv("OPENAI_API_KEY", "")
                    if not api_key:
                        raise RuntimeError("OPENAI_API_KEY is required for --provider openai")
                    if provider_budget_allows(max_provider_assets, provider_asset_calls):
                        provider_asset_calls += 1
                        raw_retag = _openai_retag(
                            candidate,
                            refs,
                            model_name,
                            api_key=api_key,
                            base_url=openai_base_url,
                            detail=openai_detail,
                            timeout=timeout,
                        )
                    else:
                        provider_budget_fallbacks += 1
                        asset_provider = "heuristic"
                        asset_model = "orbit_heuristic_budget_fallback_v1"
                        raw_retag = _heuristic_retag(candidate, refs, asset_model)
                else:
                    raw_retag = _heuristic_retag(candidate, refs, asset_model)
                retag = _normalize_retag(raw_retag)
            except Exception as exc:
                failures.append({"asset_id": asset_id, "path": str(candidate.path), "error": str(exc)})
                asset_provider = "heuristic"
                asset_model = "orbit_heuristic_fallback_v1"
                retag = _normalize_retag(_heuristic_retag(candidate, refs, asset_model))

        references = _refs_to_json(refs)
        duplicate_reference_count = max(0, len(references) - 1)
        asset_row = {
            "format": "orbit_asset_retag_v1",
            "asset_id": asset_id,
            "asset_sha256": digest,
            "source_asset_path": str(candidate.path.relative_to(dataset_dir)) if _is_relative_to(candidate.path, dataset_dir) else str(candidate.path),
            "file_name": image_file,
            "source_kind": candidate.source_kind,
            "mime_type": _mime_type(candidate.path),
            "requested_provider": provider,
            "provider": asset_provider,
            "model": asset_model,
            "script_version": _SCRIPT_VERSION,
            "prompt_version": _PROMPT_VERSION,
            "reused_existing_tag": existing_asset_row is not None,
            "duplicate_reference_count": duplicate_reference_count,
            "references": references,
            "retag": retag,
        }
        asset_rows.append(asset_row)
        metadata_rows.append({
            "file_name": image_file,
            "asset_id": asset_id,
            "asset_sha256": digest,
            "target_category": retag["target_category"],
            "target_action": retag["target_action"],
            "labels": retag["labels"],
            "reason_codes": retag["reason_codes"],
            "visual_summary": retag["visual_summary"],
            "quality": retag["quality"],
            "confidence": retag["confidence"],
            "duplicate_reference_count": duplicate_reference_count,
        })
        training_rows.append({
            "format": "orbit_asset_sft_v1",
            "asset_id": asset_id,
            "image": image_file,
            "messages": [
                {
                    "role": "system",
                    "content": "You label Earth-observation imagery for temporal-change training data.",
                },
                {
                    "role": "user",
                    "content": "Retag this image for Orbit training. Return structured labels.",
                },
                {
                    "role": "assistant",
                    "content": json.dumps(retag, sort_keys=True),
                },
            ],
            "metadata": {
                "asset_sha256": digest,
                "source_kind": candidate.source_kind,
                "requested_provider": provider,
                "provider": asset_provider,
                "model": asset_model,
                "references": references,
            },
        })
        queue_rows.append({
            "asset_id": asset_id,
            "file_name": image_file,
            "prompt": prompt,
            "references": references,
        })

        if sleep_seconds > 0 and index < len(unique):
            time.sleep(sleep_seconds)

    if tag_temporal_sequences:
        merged_sequences: dict[str, TemporalSequenceCandidate] = {}
        for sequence in sequence_candidates:
            video_digest = _sha256(sequence.video_path)
            if video_digest not in merged_sequences:
                merged_sequences[video_digest] = TemporalSequenceCandidate(
                    video_path=sequence.video_path,
                    refs=[],
                    frame_candidates=sequence.frame_candidates,
                    decoded_frames_count=sequence.decoded_frames_count,
                    sampled_indices=sequence.sampled_indices,
                )
            merged_sequences[video_digest].refs.extend(sequence.refs)

        for video_digest, sequence in sorted(merged_sequences.items()):
            frame_hashes = [_sha256(frame.path) for frame in sequence.frame_candidates]
            ordered_frames = [
                {
                    "frame_index": sequence.sampled_indices[index],
                    "asset_id": frame_hash[:16],
                    "asset_sha256": frame_hash,
                    "file_name": digest_to_file.get(frame_hash, ""),
                }
                for index, frame_hash in enumerate(frame_hashes)
            ]
            try:
                sequence_provider = provider
                sequence_model = model_name
                existing_sequence_row = existing_sequence_rows.get(video_digest)
                if existing_sequence_row is not None:
                    reused_sequence_tags += 1
                    sequence_provider = str(existing_sequence_row.get("provider") or "reused")
                    sequence_model = str(existing_sequence_row.get("model") or model_name)
                    sequence_retag = _normalize_sequence_retag(existing_sequence_row.get("retag") or {})
                elif sequence_tagger is not None:
                    raw_sequence = sequence_tagger(sequence, model_name, frame_hashes)
                    sequence_retag = _normalize_sequence_retag(raw_sequence)
                else:
                    if provider == "queue":
                        raw_sequence = _heuristic_sequence_retag(sequence, model_name, frame_hashes)
                    elif provider == "ollama":
                        if provider_budget_allows(max_provider_sequences, provider_sequence_calls):
                            provider_sequence_calls += 1
                            raw_sequence = _ollama_sequence_retag(
                                sequence,
                                model_name,
                                base_url=ollama_base_url,
                                timeout=timeout,
                            )
                        else:
                            provider_sequence_budget_fallbacks += 1
                            sequence_provider = "heuristic"
                            sequence_model = "orbit_heuristic_sequence_budget_fallback_v1"
                            raw_sequence = _heuristic_sequence_retag(sequence, sequence_model, frame_hashes)
                    elif provider == "openai":
                        api_key = os.getenv("OPENAI_API_KEY", "")
                        if not api_key:
                            raise RuntimeError("OPENAI_API_KEY is required for --provider openai")
                        if provider_budget_allows(max_provider_sequences, provider_sequence_calls):
                            provider_sequence_calls += 1
                            raw_sequence = _openai_sequence_retag(
                                sequence,
                                model_name,
                                api_key=api_key,
                                base_url=openai_base_url,
                                detail=openai_detail,
                                timeout=timeout,
                            )
                        else:
                            provider_sequence_budget_fallbacks += 1
                            sequence_provider = "heuristic"
                            sequence_model = "orbit_heuristic_sequence_budget_fallback_v1"
                            raw_sequence = _heuristic_sequence_retag(sequence, sequence_model, frame_hashes)
                    else:
                        raw_sequence = _heuristic_sequence_retag(sequence, model_name, frame_hashes)
                    sequence_retag = _normalize_sequence_retag(raw_sequence)
            except Exception as exc:
                sequence_failures.append({"video_sha256": video_digest, "path": str(sequence.video_path), "error": str(exc)})
                sequence_provider = "heuristic"
                sequence_model = "orbit_heuristic_sequence_fallback_v1"
                sequence_retag = _normalize_sequence_retag(
                    _heuristic_sequence_retag(sequence, sequence_model, frame_hashes)
                )

            references = _refs_to_json(sequence.refs)
            sequence_id = video_digest[:16]
            sequence_rows.append({
                "format": "orbit_temporal_sequence_retag_v1",
                "sequence_id": sequence_id,
                "video_sha256": video_digest,
                "source_video_path": str(sequence.video_path.relative_to(dataset_dir)) if _is_relative_to(sequence.video_path, dataset_dir) else str(sequence.video_path),
                "decoded_frames_count": sequence.decoded_frames_count,
                "sampled_indices": sequence.sampled_indices,
                "ordered_frames": ordered_frames,
                "unique_frame_assets": len({frame["asset_sha256"] for frame in ordered_frames}),
                "requested_provider": provider,
                "provider": sequence_provider,
                "model": sequence_model,
                "script_version": _SCRIPT_VERSION,
                "prompt_version": _PROMPT_VERSION,
                "reused_existing_tag": video_digest in existing_sequence_rows,
                "references": references,
                "retag": sequence_retag,
            })
            sequence_training_rows.append({
                "format": "orbit_temporal_sequence_sft_v1",
                "sequence_id": sequence_id,
                "images": [frame["file_name"] for frame in ordered_frames if frame["file_name"]],
                "messages": [
                    {
                        "role": "system",
                        "content": "You label ordered Earth-observation image sequences for temporal-change training data.",
                    },
                    {
                        "role": "user",
                        "content": "Retag this ordered image sequence as temporal evidence. Return structured labels.",
                    },
                    {
                        "role": "assistant",
                        "content": json.dumps(sequence_retag, sort_keys=True),
                    },
                ],
                "metadata": {
                    "video_sha256": video_digest,
                    "ordered_frames": ordered_frames,
                    "requested_provider": provider,
                    "provider": sequence_provider,
                    "model": sequence_model,
                    "references": references,
                },
            })

    _write_jsonl(output_dir / "retagged_assets.jsonl", asset_rows)
    _write_jsonl(output_dir / "training_assets.jsonl", training_rows)
    _write_jsonl(output_dir / "temporal_sequences.jsonl", sequence_rows)
    _write_jsonl(output_dir / "training_temporal_sequences.jsonl", sequence_training_rows)
    _write_jsonl(output_dir / "metadata.jsonl", metadata_rows)
    _write_jsonl(output_dir / "review_queue.jsonl", queue_rows)
    _write_jsonl(output_dir / "skipped_assets.jsonl", skipped)
    _write_jsonl(output_dir / "tagger_failures.jsonl", failures)
    _write_jsonl(output_dir / "sequence_tagger_failures.jsonl", sequence_failures)

    manifest = {
        "format": "orbit_retag_manifest_v1",
        "dataset_dir": str(dataset_dir),
        "output_dir": str(output_dir),
        "reuse_existing_dir": str(reuse_existing_dir) if reuse_existing_dir else None,
        "reuse_existing_sequences": reuse_existing_sequences,
        "provider": provider,
        "model": model_name,
        "provider_asset_call_budget": max_provider_assets,
        "provider_sequence_call_budget": max_provider_sequences,
        "provider_asset_calls": provider_asset_calls,
        "provider_sequence_calls": provider_sequence_calls,
        "provider_budget_fallbacks": provider_budget_fallbacks,
        "provider_sequence_budget_fallbacks": provider_sequence_budget_fallbacks,
        "reused_asset_tags": reused_asset_tags,
        "reused_sequence_tags": reused_sequence_tags,
        "unique_training_assets": len(asset_rows),
        "unique_temporal_sequences": len(sequence_rows),
        "source_candidates": len(candidates),
        "expanded_image_candidates": len(expanded_candidates),
        "duplicate_assets_removed": max(0, len(expanded_candidates) - len(asset_rows)),
        "skipped_assets": len(skipped),
        "tagger_failures": len(failures),
        "sequence_tagger_failures": len(sequence_failures),
        "video_frame_count": frame_count,
        "minimum_valid_video_frames": min_video_frames,
        "paths": {
            "hf_imagefolder": "./",
            "metadata_jsonl": "metadata.jsonl",
            "retagged_assets_jsonl": "retagged_assets.jsonl",
            "training_assets_jsonl": "training_assets.jsonl",
            "temporal_sequences_jsonl": "temporal_sequences.jsonl",
            "training_temporal_sequences_jsonl": "training_temporal_sequences.jsonl",
            "review_queue_jsonl": "review_queue.jsonl",
            "images": f"{_HF_IMAGE_DIR}/",
        },
        "notes": [
            "Rows are deduplicated by SHA-256. Duplicate sample references are preserved in each row.",
            "Timelapse videos are expanded into sampled still frames before tagging.",
            "Valid timelapse videos also produce temporal sequence rows with ordered frame references.",
            "Videos with fewer than the configured minimum frame count are skipped as invalid temporal evidence.",
            "The output directory is Hugging Face ImageFolder-compatible via images/ plus metadata.jsonl.",
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retag Orbit dataset images and timelapse frames into deduplicated training assets.")
    parser.add_argument("--dataset-dir", type=Path, default=Path("."), help="Orbit export/data directory. Defaults to the current directory.")
    parser.add_argument("--output-dir", type=Path, default=None, help=f"Output directory. Defaults to <dataset-dir>/{_DEFAULT_OUTPUT_DIR}.")
    parser.add_argument("--provider", choices=["heuristic", "queue", "ollama", "openai"], default="ollama", help="Retag provider.")
    parser.add_argument("--model", default=None, help=f"Provider model name. Ollama defaults to {_DEFAULT_OLLAMA_MODEL}.")
    parser.add_argument("--video-frame-count", type=int, default=4, help="Maximum frames to extract per valid timelapse video.")
    parser.add_argument("--min-video-frames", type=int, default=2, help="Minimum decoded frames required before a video becomes training evidence.")
    parser.add_argument("--no-temporal-sequences", action="store_true", help="Extract video frames but skip ordered temporal sequence JSONL rows.")
    parser.add_argument("--no-loose-scan", action="store_true", help="Only process assets referenced by JSONL/sample records.")
    parser.add_argument("--ollama-base-url", default="http://127.0.0.1:11434", help="Ollama base URL.")
    parser.add_argument("--openai-base-url", default="https://api.openai.com/v1", help="OpenAI-compatible API base URL.")
    parser.add_argument("--openai-detail", choices=["low", "high", "auto"], default="low", help="OpenAI image detail level.")
    parser.add_argument("--timeout", type=float, default=120.0, help="Provider HTTP timeout in seconds.")
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="Optional pause between provider calls.")
    parser.add_argument(
        "--reuse-existing-dir",
        type=Path,
        default=None,
        help="Reuse retag/sequence labels from an existing retagged_training folder when SHA-256 hashes match.",
    )
    parser.add_argument(
        "--no-reuse-existing-sequences",
        action="store_true",
        help="Reuse matching image tags but force temporal sequence labels to be regenerated.",
    )
    parser.add_argument(
        "--max-provider-assets",
        type=int,
        default=16,
        help="Maximum Ollama/OpenAI image calls before heuristic fallback. Use -1 for unlimited full-model retagging.",
    )
    parser.add_argument(
        "--max-provider-sequences",
        type=int,
        default=0,
        help="Maximum Ollama/OpenAI temporal-sequence calls before heuristic fallback. Use 0 to keep sequences heuristic, -1 for unlimited.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    dataset_dir = args.dataset_dir.resolve()
    output_dir = args.output_dir.resolve() if args.output_dir else dataset_dir / _DEFAULT_OUTPUT_DIR
    manifest = retag_dataset(
        dataset_dir,
        output_dir,
        provider=args.provider,
        model=args.model,
        frame_count=max(1, int(args.video_frame_count)),
        min_video_frames=max(2, int(args.min_video_frames)),
        tag_temporal_sequences=not args.no_temporal_sequences,
        scan_loose_assets=not args.no_loose_scan,
        ollama_base_url=args.ollama_base_url,
        openai_base_url=args.openai_base_url,
        openai_detail=args.openai_detail,
        timeout=max(1.0, float(args.timeout)),
        sleep_seconds=max(0.0, float(args.sleep_seconds)),
        max_provider_assets=int(args.max_provider_assets),
        max_provider_sequences=int(args.max_provider_sequences),
        reuse_existing_dir=args.reuse_existing_dir,
        reuse_existing_sequences=not args.no_reuse_existing_sequences,
    )
    print(
        "[Orbit] Retagged {unique_training_assets} unique assets to {path} "
        "({duplicate_assets_removed} duplicates removed, {skipped_assets} skipped, {tagger_failures} tagger failures).".format(
            path=output_dir,
            **manifest,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
