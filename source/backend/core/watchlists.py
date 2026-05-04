"""JSON-backed operational watchlist loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.mission import start_mission


WATCHLIST_DIR = Path(__file__).resolve().parent.parent / "assets" / "watchlists"
REPO_ROOT = Path(__file__).resolve().parents[3]


def _repo_relative_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def list_watchlists() -> list[dict[str, Any]]:
    watchlists: list[dict[str, Any]] = []
    for path in sorted(WATCHLIST_DIR.glob("*.json")):
        payload = _load_json(path)
        if not payload:
            continue
        watchlist_id = str(payload.get("watchlist_id") or payload.get("watch_id") or path.stem)
        assets = payload.get("assets") if isinstance(payload.get("assets"), list) else []
        watchlists.append({
            "watchlist_id": watchlist_id,
            "display_name": payload.get("display_name") or payload.get("risk_area_label") or watchlist_id,
            "purpose": payload.get("purpose") or payload.get("task_text") or "",
            "asset_count": len(assets),
            "path": _repo_relative_path(path),
        })
    return watchlists


def get_watchlist(watchlist_id: str) -> dict[str, Any] | None:
    requested = watchlist_id.strip().lower()
    if not requested:
        return None
    for path in sorted(WATCHLIST_DIR.glob("*.json")):
        payload = _load_json(path)
        if not payload:
            continue
        current_id = str(payload.get("watchlist_id") or payload.get("watch_id") or path.stem).strip().lower()
        if current_id == requested or path.stem.lower() == requested:
            payload = dict(payload)
            payload["watchlist_id"] = str(payload.get("watchlist_id") or payload.get("watch_id") or path.stem)
            return payload
    return None


def list_watchlist_assets(watchlist_id: str) -> list[dict[str, Any]] | None:
    watchlist = get_watchlist(watchlist_id)
    if watchlist is None:
        return None
    assets = watchlist.get("assets")
    return list(assets) if isinstance(assets, list) else []


def build_mission_from_watchlist_asset(watchlist_id: str, asset_id: str) -> dict[str, Any]:
    watchlist = get_watchlist(watchlist_id)
    if watchlist is None:
        raise LookupError(f"Watchlist not found: {watchlist_id}")
    assets = watchlist.get("assets") if isinstance(watchlist.get("assets"), list) else []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        if str(asset.get("asset_id") or "").strip().lower() != asset_id.strip().lower():
            continue
        target_pack_id = str(asset.get("target_pack") or asset.get("target_pack_id") or "") or None
        task_text = (
            f"Run {watchlist.get('display_name') or watchlist['watchlist_id']} for "
            f"{asset.get('display_name') or asset.get('asset_id')}."
        )
        return start_mission(
            task_text,
            bbox=asset.get("bbox") if isinstance(asset.get("bbox"), list) else None,
            mission_mode="live",
            summary=str(watchlist.get("purpose") or ""),
            target_pack_id=target_pack_id,
        )
    raise LookupError(f"Watchlist asset not found: {asset_id}")
