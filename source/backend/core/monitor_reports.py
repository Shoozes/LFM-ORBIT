from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.paths import REPO_ROOT, get_runtime_data_dir


MONITOR_REPORTS_SUBDIR = "monitor-reports"
REPORT_PERSISTENCE_SCHEMA = "orbit_monitor_report_persistence_v1"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def get_monitor_reports_dir() -> Path:
    return get_runtime_data_dir() / MONITOR_REPORTS_SUBDIR


def _safe_slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    return cleaned.strip("._") or "monitor_report"


def _relative_display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _report_prefix(report: dict[str, Any]) -> str:
    mode = str(report.get("mode") or "monitor_report")
    if mode == "orbit_lifeline_monitoring_v1":
        asset = report.get("asset") if isinstance(report.get("asset"), dict) else {}
        return _safe_slug(f"lifeline_{asset.get('asset_id') or 'asset'}")
    if mode == "orbit_maritime_monitoring_v1":
        target = report.get("target") if isinstance(report.get("target"), dict) else {}
        return _safe_slug(f"maritime_{target.get('lat')}_{target.get('lon')}_{target.get('timestamp')}")
    return _safe_slug(mode)


def persist_monitor_report(report: dict[str, Any]) -> dict[str, Any]:
    payload = dict(report)
    reports_dir = get_monitor_reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    filename = f"{_report_prefix(payload)}_{digest}.json"
    path = reports_dir / filename
    persistence = {
        "schema": REPORT_PERSISTENCE_SCHEMA,
        "saved_at": _now(),
        "path": _relative_display_path(path),
        "filename": filename,
    }
    payload["persistence"] = persistence
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return persistence


def list_monitor_report_files(limit: int = 100) -> list[dict[str, Any]]:
    reports_dir = get_monitor_reports_dir()
    if not reports_dir.exists():
        return []
    files = sorted(reports_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    return [
        {
            "filename": path.name,
            "path": _relative_display_path(path),
            "bytes": path.stat().st_size,
            "modified_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        for path in files[: max(1, min(int(limit), 500))]
    ]
