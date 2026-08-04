#!/usr/bin/env python3
"""Fast, dependency-free checks for active documentation and context routing."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit


REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS_ROOT = REPO_ROOT / "docs"
ARCHIVE_PARTS = {"archive"}
LOCAL_TARGET_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
STALE_HEADING_RE = re.compile(
    r"^#+\s+(?:Completed in This Pass|Latest Validation Snapshot|Changes in This Pass)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

DOC_BUDGETS = {
    "README.md": 25 * 1024,
    "docs/dev/ARCHITECTURE.md": 12 * 1024,
    "docs/dev/TODO.md": 8 * 1024,
    "docs/user/HOSTED_DEMO.md": 6 * 1024,
    "docs/user/DEMO_GUIDE.md": 6 * 1024,
}
DEFAULT_ACTIVE_DOC_BUDGET = 10 * 1024


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _is_archived(path: Path) -> bool:
    return bool(ARCHIVE_PARTS.intersection(path.relative_to(DOCS_ROOT).parts))


def _local_markdown_targets(markdown: str) -> list[str]:
    targets: list[str] = []
    for match in LOCAL_TARGET_RE.finditer(markdown):
        raw = match.group(1).strip().strip("<>")
        if not raw:
            continue
        parsed = urlsplit(raw)
        if parsed.scheme or parsed.netloc or raw.startswith("#"):
            continue
        target = parsed.path
        if target:
            targets.append(target)
    return targets


def _check_markdown_links(errors: list[str]) -> None:
    markdown_paths = [REPO_ROOT / "README.md", *sorted(DOCS_ROOT.rglob("*.md"))]
    for path in markdown_paths:
        if not path.exists():
            continue
        if path != REPO_ROOT / "README.md" and _is_archived(path):
            continue
        markdown = path.read_text(encoding="utf-8", errors="ignore")
        for target in _local_markdown_targets(markdown):
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(REPO_ROOT)
            except ValueError:
                errors.append(f"{_relative(path)} links outside repository: {target}")
                continue
            if not resolved.exists():
                errors.append(f"{_relative(path)} links to missing target: {target}")


def _check_budgets(errors: list[str]) -> None:
    active_markdown = [
        REPO_ROOT / "README.md",
        *sorted(path for path in DOCS_ROOT.rglob("*.md") if not _is_archived(path)),
    ]
    for path in active_markdown:
        relative = _relative(path)
        if relative.startswith("docs/legal/"):
            continue
        budget = DOC_BUDGETS.get(relative, DEFAULT_ACTIVE_DOC_BUDGET)
        if path.stat().st_size > budget:
            errors.append(
                f"{relative} is {path.stat().st_size} bytes; budget is {budget} bytes"
            )


def _check_summary_bank(errors: list[str]) -> None:
    bank_path = REPO_ROOT / "summary_bank.json"
    try:
        bank = json.loads(bank_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"summary_bank.json is unreadable: {exc}")
        return

    groups = bank.get("groups")
    defaults = bank.get("defaults", {}).get("groups")
    if not isinstance(groups, dict) or not isinstance(defaults, list) or not defaults:
        errors.append("summary_bank.json must define groups and a non-empty defaults.groups list")
        return

    for group_name in defaults:
        group = groups.get(group_name)
        if not isinstance(group, dict) or group.get("_archived"):
            errors.append(f"summary-bank default is missing or archived: {group_name}")

    for group_name, group in groups.items():
        if not isinstance(group, dict):
            errors.append(f"summary-bank group is not an object: {group_name}")
            continue
        if group.get("_archived"):
            continue
        files = group.get("files", [])
        if not isinstance(files, list) or len(files) != len(set(files)):
            errors.append(f"summary-bank group has duplicate or invalid files: {group_name}")
            continue
        if not isinstance(group.get("description"), str) or not group["description"].strip():
            errors.append(f"summary-bank group has no description: {group_name}")
        for relative in files:
            if not isinstance(relative, str) or Path(relative).is_absolute():
                errors.append(f"summary-bank group has non-relative file: {group_name}: {relative}")
            elif not (REPO_ROOT / relative).exists():
                errors.append(f"summary-bank group has missing file: {group_name}: {relative}")


def _check_active_headings(errors: list[str]) -> None:
    for relative in ("docs/dev/TODO.md", "docs/dev/ARCHITECTURE.md"):
        path = REPO_ROOT / relative
        markdown = path.read_text(encoding="utf-8")
        if STALE_HEADING_RE.search(markdown):
            errors.append(f"{relative} contains a historical status heading")


def main() -> int:
    errors: list[str] = []
    _check_markdown_links(errors)
    _check_budgets(errors)
    _check_summary_bank(errors)
    _check_active_headings(errors)

    if errors:
        print("Documentation contract failures:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Documentation contracts passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
