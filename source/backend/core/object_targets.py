"""Object target pack registry for mission evidence prompts."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, cast

from core.contracts import ObjectTarget, TargetPack
from core.paths import get_runtime_data_dir


DEFAULT_TARGET_PACKS_PATH = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "object_targets"
    / "default_target_packs.json"
)
CUSTOM_TARGET_PACKS_RELATIVE_PATH = Path("object-targets") / "custom_target_packs.json"

DENIED_TARGET_LABELS = frozenset(
    {
        "individual",
        "individuals",
        "manatee",
        "manatees",
        "people",
        "person",
        "persons",
        "population",
        "populations",
        "soldier",
        "soldiers",
        "strike",
        "strikes",
        "target",
        "targets",
        "weapon",
        "weapons",
    }
)


def _collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _normalize_label(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("Object target label must be a string.")
    label = _collapse_spaces(value).lower()
    if not label:
        raise ValueError("Object target label is required.")
    return label


def _normalize_prompt(value: Any, label: str) -> str:
    if value is None:
        return f"Find {label}"
    if not isinstance(value, str):
        raise ValueError(f"Prompt for object target '{label}' must be a string.")
    prompt = _collapse_spaces(value)
    return prompt or f"Find {label}"


def _normalize_class_key(value: Any) -> str:
    if value is None:
        return "custom"
    if not isinstance(value, str):
        raise ValueError("Object target class_key must be a string.")
    class_key = re.sub(r"[^a-z0-9_]+", "_", value.strip().lower()).strip("_")
    return class_key or "custom"


def _normalize_enabled(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value) if value is not None else True


def reject_unsafe_target_label(label: str) -> None:
    """Reject object labels outside the civilian evidence scope."""
    normalized = _normalize_label(label)
    tokens = set(re.findall(r"[a-z0-9]+", normalized))
    denied = normalized in DENIED_TARGET_LABELS or bool(tokens & DENIED_TARGET_LABELS)
    if denied:
        raise ValueError(
            f"Object target '{normalized}' is outside the civilian evidence scope for LFM-ORBIT."
        )


def normalize_object_target(target: Mapping[str, Any] | str) -> ObjectTarget:
    if isinstance(target, str):
        raw: Mapping[str, Any] = {"label": target}
    elif isinstance(target, Mapping):
        raw = target
    else:
        raise ValueError("Object target must be a mapping or label string.")

    label = _normalize_label(raw.get("label"))
    reject_unsafe_target_label(label)
    normalized: ObjectTarget = {
        "label": label,
        "prompt": _normalize_prompt(raw.get("prompt"), label),
        "class_key": _normalize_class_key(raw.get("class_key")),
        "enabled": _normalize_enabled(raw.get("enabled", True)),
    }
    return normalized


def normalize_object_targets(targets: Iterable[Mapping[str, Any] | str]) -> list[ObjectTarget]:
    return merge_custom_targets([], targets)


def merge_custom_targets(
    base_targets: Iterable[Mapping[str, Any] | str],
    custom_targets: Iterable[Mapping[str, Any] | str],
) -> list[ObjectTarget]:
    merged: list[ObjectTarget] = []
    label_to_index: dict[str, int] = {}

    for raw_target in [*base_targets, *custom_targets]:
        target = normalize_object_target(raw_target)
        existing_index = label_to_index.get(target["label"])
        if existing_index is None:
            label_to_index[target["label"]] = len(merged)
            merged.append(target)
        else:
            merged[existing_index] = target
    return merged


def _normalize_pack_id(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("Target pack id must be a string.")
    pack_id = re.sub(r"[^a-z0-9_-]+", "_", value.strip().lower()).strip("_-")
    if not pack_id:
        raise ValueError("Target pack id is required.")
    return pack_id


def _normalize_pack(data: Mapping[str, Any]) -> TargetPack:
    pack_id = _normalize_pack_id(data.get("id"))
    name = _collapse_spaces(str(data.get("name") or pack_id.replace("_", " ").title()))
    description = _collapse_spaces(str(data.get("description") or ""))
    targets = data.get("targets")
    if not isinstance(targets, list):
        raise ValueError(f"Target pack '{pack_id}' must contain a targets list.")

    normalized: TargetPack = {
        "id": pack_id,
        "name": name,
        "description": description,
        "targets": merge_custom_targets([], cast(list[Mapping[str, Any] | str], targets)),
    }
    return normalized


def _load_pack_file(path: Path, *, missing_ok: bool) -> list[TargetPack]:
    if not path.exists():
        if missing_ok:
            return []
        raise FileNotFoundError(f"Target pack file not found: {path}")
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Target pack file {path.name} must contain a JSON object.")
    packs = data.get("packs")
    if not isinstance(packs, list):
        raise ValueError(f"Target pack file {path.name} must contain a packs list.")
    normalized_packs: list[TargetPack] = []
    for pack in packs:
        if not isinstance(pack, Mapping):
            raise ValueError(f"Target pack file {path.name} contains a non-object pack entry.")
        normalized_packs.append(_normalize_pack(cast(Mapping[str, Any], pack)))
    return normalized_packs


def get_custom_target_packs_path(runtime_dir: Path | None = None) -> Path:
    root = runtime_dir if runtime_dir is not None else get_runtime_data_dir()
    return root / CUSTOM_TARGET_PACKS_RELATIVE_PATH


def list_default_target_packs() -> list[TargetPack]:
    return _load_pack_file(DEFAULT_TARGET_PACKS_PATH, missing_ok=False)


def list_custom_target_packs(runtime_dir: Path | None = None) -> list[TargetPack]:
    return _load_pack_file(get_custom_target_packs_path(runtime_dir), missing_ok=True)


def load_custom_target_packs(runtime_dir: Path | None = None) -> list[TargetPack]:
    return list_custom_target_packs(runtime_dir)


def list_target_packs(
    *,
    include_custom: bool = True,
    runtime_dir: Path | None = None,
) -> list[TargetPack]:
    packs = list_default_target_packs()
    if not include_custom:
        return packs

    pack_indexes = {pack["id"]: index for index, pack in enumerate(packs)}
    for custom_pack in list_custom_target_packs(runtime_dir):
        existing_index = pack_indexes.get(custom_pack["id"])
        if existing_index is None:
            pack_indexes[custom_pack["id"]] = len(packs)
            packs.append(custom_pack)
        else:
            packs[existing_index] = custom_pack
    return packs


def get_target_pack(
    pack_id: str,
    *,
    include_custom: bool = True,
    runtime_dir: Path | None = None,
) -> TargetPack | None:
    try:
        normalized_pack_id = _normalize_pack_id(pack_id)
    except ValueError:
        return None
    for pack in list_target_packs(include_custom=include_custom, runtime_dir=runtime_dir):
        if pack["id"] == normalized_pack_id:
            return pack
    return None


def save_custom_target_pack(
    pack: Mapping[str, Any],
    *,
    runtime_dir: Path | None = None,
) -> TargetPack:
    normalized_pack = _normalize_pack(pack)
    path = get_custom_target_packs_path(runtime_dir)
    existing = list_custom_target_packs(runtime_dir)
    existing_by_id = {item["id"]: item for item in existing}
    existing_by_id[normalized_pack["id"]] = normalized_pack
    ordered_packs = list(existing_by_id.values())

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"packs": ordered_packs}, handle, indent=2)
        handle.write("\n")
    return normalized_pack


def delete_custom_target_pack(
    pack_id: str,
    *,
    runtime_dir: Path | None = None,
) -> bool:
    normalized_pack_id = _normalize_pack_id(pack_id)
    path = get_custom_target_packs_path(runtime_dir)
    existing = list_custom_target_packs(runtime_dir)
    remaining = [pack for pack in existing if pack["id"] != normalized_pack_id]
    if len(remaining) == len(existing):
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"packs": remaining}, handle, indent=2)
        handle.write("\n")
    return True
