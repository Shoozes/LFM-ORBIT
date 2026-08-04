#!/usr/bin/env python3
# PROJECT GENA
# File: _gen_bank.py
# Purpose: summary_bank.json generator/maintainer.

from __future__ import annotations

import os
import json
import argparse
import fnmatch
import copy
from pathlib import Path
from typing import Dict, List, Optional, Tuple


DEFAULT_SCHEMA = {
    "defaults": {
        "groups": [],
        "tree": True,
        "max_kb": 256,
        "skip_dirs": [
            "node_modules",
            "venv",
            ".venv",
            "__pycache__",
            "runtime-data",
            "dist",
            "build",
            "release",
            "models",
            "public",
            "tests",
            "test",
            "docs",
            ".git",
            ".github",
            "target",
            ".secrets",
            ".vscode",
            ".idea",
        ],
    },
    "groups": {},
    "exclusions": {},
}

DEFAULT_SKIP_FILES = [
    "package-lock.json",
    "Cargo.lock",
    "yarn.lock",
    "pnpm-lock.yaml",
    "setup_log.txt",
    "debug_log.txt",
    "_struct_summary.txt",
    "_structure_with_content.txt",
]

AUDIT_DEFAULT_MAX_GROUP_FILES = 40
AUDIT_DEFAULT_MAX_DEFAULT_GROUPS = 15
AUDIT_DEFAULT_HOTSPOT_MIN_GROUPS = 12
# The serialized registry guard is distinct from the 256 KB focused-route ceiling.
AUDIT_DEFAULT_MAX_BANK_KB = 384


def _normalize_group_entries(value: object) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [item for item in value if isinstance(item, str) and item]
    return []


def _unique(seq: List[str]) -> List[str]:
    return list(dict.fromkeys([s for s in seq if s]))


def find_repo_root(start: Path) -> Optional[Path]:
    p = start.resolve()
    for cur in [p] + list(p.parents):
        if (cur / ".git").exists():
            return cur
    return None


def load_gitignore(root_dir: str) -> List[str]:
    gitignore_path = os.path.join(root_dir, ".gitignore")
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return []


def _has_glob_meta(pat: str) -> bool:
    return any(ch in pat for ch in ("*", "?", "["))


def infer_skip_dirnames_from_gitignore(patterns: List[str]) -> List[str]:
    """
    Best-effort inference of directory names from .gitignore patterns so we can prune os.walk early.

    We intentionally keep this conservative:
    - ignore negations (!)
    - treat trailing "/" or "/**" as directory patterns
    - treat simple non-glob patterns (no slashes) as potential directory names
    """
    out: List[str] = []

    for raw in patterns:
        s = (raw or "").strip()
        if not s or s.startswith("#") or s.startswith("!"):
            continue

        anchored = s.startswith("/")
        if anchored:
            s = s[1:]

        # Normalize common "dir/**" case to "dir"
        if s.endswith("/**"):
            s = s[:-3]

        is_dir_pattern = s.endswith("/")
        if is_dir_pattern:
            s = s.rstrip("/")

        if not s:
            continue

        # If pattern has path separators, we can't convert it safely into a single dir name.
        # For our repo tools use-case, the common ignores are top-level (e.g. ".tools/", ".github/").
        if "/" in s or "\\" in s:
            continue

        # If it has globs, it's not a stable directory name.
        if _has_glob_meta(s):
            continue

        # If it explicitly looked like a directory pattern, keep it.
        # If it's a simple token, keep it as a potential directory name (harmless if no dir matches).
        if is_dir_pattern or (not is_dir_pattern):
            out.append(s)

    return _unique(out)


def is_ignored(rel_path: str, patterns: List[str]) -> bool:
    rel_path = rel_path.replace(os.sep, "/")
    for pattern in patterns:
        anchored = pattern.startswith("/")
        if anchored:
            pattern = pattern[1:]
        if pattern.endswith("/"):
            pattern = pattern[:-1] + "/*"
        if anchored:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
        else:
            parts = rel_path.split("/")
            for i in range(len(parts) + 1):
                subpath = "/".join(parts[:i]) + ("/" if i > 0 else "") + pattern
                if fnmatch.fnmatch(rel_path, subpath):
                    return True
    return False


def collect_all_files(
    root_dir: str,
    skip_dirs: List[str],
    skip_prefixes: Tuple[str, ...],
    skip_suffixes: Tuple[str, ...],
    skip_files: List[str],
    git_patterns: List[str],
) -> Dict[str, object]:
    all_files: Dict[str, List[str]] = {}
    all_dirs: set[str] = set()

    for root, dirs, files in os.walk(root_dir):
        rel_root = os.path.relpath(root, root_dir).replace(os.sep, "/")
        rel_root = "" if rel_root == "." else rel_root

        for d in list(dirs):
            if d.startswith(skip_prefixes):
                dirs.remove(d)
                continue

            rel_d = (rel_root + "/" + d).strip("/") if rel_root else d
            if d in skip_dirs or is_ignored(rel_d, git_patterns):
                dirs.remove(d)
            else:
                all_dirs.add(rel_d)

        for file in files:
            if file in skip_files:
                continue
            if file.startswith(skip_prefixes) or file.endswith(skip_suffixes):
                continue

            rel_path = (rel_root + "/" + file).strip("/") if rel_root else file
            if is_ignored(rel_path, git_patterns):
                continue

            dir_key = rel_root
            all_files.setdefault(dir_key, []).append(file)

    return {"files": all_files, "dirs": all_dirs}


def _group_file_entries(group: Dict) -> List[str]:
    return _unique(_normalize_group_entries(group.get("files")) + _normalize_group_entries(group.get("paths")))


def audit_summary_bank(
    bank_path: str,
    root_dir: Optional[str] = None,
    max_group_files: int = AUDIT_DEFAULT_MAX_GROUP_FILES,
    max_default_groups: int = AUDIT_DEFAULT_MAX_DEFAULT_GROUPS,
    hotspot_min_groups: int = AUDIT_DEFAULT_HOTSPOT_MIN_GROUPS,
    max_bank_kb: int = AUDIT_DEFAULT_MAX_BANK_KB,
) -> Dict[str, object]:
    """Return a compact usefulness audit for summary_bank.json."""
    data = _load_or_init_bank(bank_path)
    groups = data.get("groups", {}) or {}
    defaults = data.get("defaults", {}) or {}
    default_groups = _normalize_group_entries(defaults.get("groups"))
    default_group_set = set(default_groups)
    default_context_budget_kb = int(defaults.get("max_kb", 256) or 256)
    bank_size_kb = round(os.path.getsize(bank_path) / 1024, 1) if os.path.exists(bank_path) else 0.0

    path_to_groups: Dict[str, List[str]] = {}
    group_reports: List[Dict[str, object]] = []
    missing_files: List[Dict[str, str]] = []
    required_file_issues: List[Dict[str, str]] = []
    default_expanded_paths: set[str] = set()

    for group_name, group in groups.items():
        files = _group_file_entries(group if isinstance(group, dict) else {})
        archived = bool(group.get("_archived")) if isinstance(group, dict) else False
        temporary = bool(group.get("_temporary")) if isinstance(group, dict) else False
        description = group.get("description") if isinstance(group, dict) else ""
        required_files = _normalize_group_entries(group.get("required_files")) if isinstance(group, dict) else []
        budget_enforced = bool(group.get("budget_enforced")) if isinstance(group, dict) else False
        group_budget_kb = (
            int(group.get("max_kb", default_context_budget_kb) or default_context_budget_kb)
            if isinstance(group, dict)
            else default_context_budget_kb
        )
        normalized_files = set(files)
        expanded_bytes = 0
        issues: List[str] = []
        if len(files) > max_group_files:
            issues.append("too_many_files")
        if group_name in default_group_set and len(files) > max_group_files:
            issues.append("broad_default")
        if group_name in default_group_set and archived:
            issues.append("archived_default")
        if not isinstance(description, str) or not description.strip():
            issues.append("missing_description")

        for required_path in required_files:
            if required_path not in normalized_files:
                issues.append("required_file_not_listed")
                required_file_issues.append(
                    {"group": group_name, "path": required_path, "issue": "not_listed"}
                )

        if root_dir:
            for rel_path in files:
                if "*" in rel_path or "?" in rel_path or "[" in rel_path:
                    continue
                absolute_path = os.path.join(root_dir, rel_path)
                if not os.path.exists(absolute_path):
                    issues.append("missing_file")
                    missing_files.append({"group": group_name, "path": rel_path})
                elif os.path.isfile(absolute_path):
                    expanded_bytes += os.path.getsize(absolute_path)
                    if group_name in default_group_set:
                        default_expanded_paths.add(rel_path)

            for required_path in required_files:
                if "*" in required_path or "?" in required_path or "[" in required_path:
                    issues.append("required_file_must_be_explicit")
                    required_file_issues.append(
                        {"group": group_name, "path": required_path, "issue": "glob_not_allowed"}
                    )
                    continue
                if not os.path.isfile(os.path.join(root_dir, required_path)):
                    issues.append("required_file_missing")
                    required_file_issues.append(
                        {"group": group_name, "path": required_path, "issue": "missing"}
                    )

        expanded_kb = round(expanded_bytes / 1024, 1)
        if group_name in default_group_set and expanded_kb > default_context_budget_kb:
            issues.append("default_expanded_bytes_over_budget")
        if budget_enforced and expanded_kb > group_budget_kb:
            issues.append("enforced_expanded_bytes_over_budget")

        for rel_path in files:
            path_to_groups.setdefault(rel_path, []).append(group_name)

        group_reports.append(
            {
                "name": group_name,
                "file_count": len(files),
                "expanded_kb": expanded_kb,
                "default": group_name in default_group_set,
                "archived": archived,
                "temporary": temporary,
                "budget_enforced": budget_enforced,
                "max_kb": group_budget_kb,
                "issues": sorted(set(issues)),
                "description": description or "",
            }
        )

    hotspots = [
        {"path": path, "group_count": len(names), "groups": sorted(names)}
        for path, names in path_to_groups.items()
        if len(names) >= hotspot_min_groups
    ]
    hotspots.sort(key=lambda item: (-int(item["group_count"]), str(item["path"])))
    group_reports.sort(key=lambda item: (-int(item["file_count"]), str(item["name"])))

    broad_unarchived = [
        item
        for item in group_reports
        if int(item["file_count"]) > max_group_files and not item["archived"]
    ]
    broad_defaults = [
        item
        for item in group_reports
        if item["default"] and int(item["file_count"]) > max_group_files
    ]
    archived_defaults = [item for item in group_reports if item["default"] and item["archived"]]
    oversized_expanded_defaults = [
        item for item in group_reports if "default_expanded_bytes_over_budget" in item["issues"]
    ]
    oversized_enforced_groups = [
        item for item in group_reports if "enforced_expanded_bytes_over_budget" in item["issues"]
    ]
    oversized_active_groups = [
        item
        for item in group_reports
        if not item["archived"]
        and not item["temporary"]
        and float(item["expanded_kb"]) > int(item["max_kb"])
    ]
    oversized_active_groups.sort(
        key=lambda item: (-float(item["expanded_kb"]), str(item["name"]))
    )
    default_expanded_bytes = 0
    if root_dir:
        for rel_path in default_expanded_paths:
            absolute_path = os.path.join(root_dir, rel_path)
            if os.path.isfile(absolute_path):
                default_expanded_bytes += os.path.getsize(absolute_path)
    default_expanded_kb = round(default_expanded_bytes / 1024, 1)

    issues: List[str] = []
    if bank_size_kb > max_bank_kb:
        issues.append("bank_size_over_budget")
    if len(default_groups) > max_default_groups:
        issues.append("too_many_default_groups")
    if broad_defaults:
        issues.append("broad_default_groups")
    if archived_defaults:
        issues.append("archived_default_groups")
    if missing_files:
        issues.append("missing_files")
    if oversized_expanded_defaults or default_expanded_kb > default_context_budget_kb:
        issues.append("default_context_over_budget")
    if oversized_enforced_groups:
        issues.append("enforced_group_context_over_budget")
    if required_file_issues:
        issues.append("required_file_issues")

    return {
        "success": not any(
            issue in issues
            for issue in (
                "bank_size_over_budget",
                "too_many_default_groups",
                "broad_default_groups",
                "archived_default_groups",
                "missing_files",
                "default_context_over_budget",
                "enforced_group_context_over_budget",
                "required_file_issues",
            )
        ),
        "issues": issues,
        "bank_size_kb": bank_size_kb,
        "max_bank_kb": max_bank_kb,
        "group_count": len(groups),
        "default_group_count": len(default_groups),
        "default_context_budget_kb": default_context_budget_kb,
        "default_expanded_kb": default_expanded_kb,
        "max_default_groups": max_default_groups,
        "max_group_files": max_group_files,
        "hotspot_min_groups": hotspot_min_groups,
        "broad_unarchived_count": len(broad_unarchived),
        "broad_default_count": len(broad_defaults),
        "oversized_active_count": len(oversized_active_groups),
        "missing_file_count": len(missing_files),
        "required_file_issue_count": len(required_file_issues),
        "groups": group_reports,
        "broad_unarchived_groups": broad_unarchived[:25],
        "broad_default_groups": broad_defaults[:25],
        "oversized_active_groups": oversized_active_groups[:25],
        "oversized_enforced_groups": oversized_enforced_groups[:25],
        "hotspots": hotspots[:25],
        "missing_files": missing_files[:25],
        "required_file_issues": required_file_issues[:25],
    }


def print_audit_report(report: Dict[str, object]) -> None:
    print("summary_bank audit")
    print(f"  size: {report['bank_size_kb']} KB (target <= {report['max_bank_kb']} KB)")
    print(f"  groups: {report['group_count']}")
    print(f"  defaults: {report['default_group_count']} (target <= {report['max_default_groups']})")
    print(
        f"  default expanded context: {report['default_expanded_kb']} KB "
        f"(target <= {report['default_context_budget_kb']} KB)"
    )
    print(f"  broad unarchived groups: {report['broad_unarchived_count']}")
    print(f"  broad default groups: {report['broad_default_count']}")
    print(f"  active groups over their advisory expanded-file budget: {report['oversized_active_count']}")
    issues = report.get("issues") or []
    print(f"  issues: {', '.join(issues) if issues else 'none'}")

    broad = report.get("broad_unarchived_groups") or []
    if broad:
        print("\nTop broad groups:")
        for item in broad[:10]:
            print(f"  - {item['name']}: {item['file_count']} files")

    hotspots = report.get("hotspots") or []
    if hotspots:
        print("\nTop file overlap hot spots:")
        for item in hotspots[:10]:
            print(f"  - {item['path']}: {item['group_count']} groups")

    missing = report.get("missing_files") or []
    if missing:
        print("\nMissing explicit file references:")
        for item in missing[:10]:
            print(f"  - {item['group']}: {item['path']}")

    required = report.get("required_file_issues") or []
    if required:
        print("\nRequired-file issues:")
        for item in required[:10]:
            print(f"  - {item['group']}: {item['path']} ({item['issue']})")

    oversized = report.get("oversized_enforced_groups") or []
    if oversized:
        print("\nBudget-enforced groups over their expanded-file limit:")
        for item in oversized[:10]:
            print(f"  - {item['name']}: {item['expanded_kb']} KB > {item['max_kb']} KB")

    oversized_active = report.get("oversized_active_groups") or []
    if oversized_active:
        print("\nTop active groups over their advisory expanded-file budget:")
        for item in oversized_active[:10]:
            enforcement = "enforced" if item["budget_enforced"] else "migration pending"
            print(
                f"  - {item['name']}: {item['expanded_kb']} KB > "
                f"{item['max_kb']} KB ({enforcement})"
            )


def update_groups(groups: Dict, all_files: Dict[str, object], root_dir: str, auto_add: bool = False) -> None:
    files_map: Dict[str, List[str]] = all_files["files"]  # type: ignore

    for group_name, group in groups.items():
        if group.get("_archived") and group.get("_archive_ref"):
            group.pop("files", None)
            group.pop("paths", None)
            continue

        new_files: List[str] = []

        for old_path in _group_file_entries(group):
            full_old = os.path.join(root_dir, old_path)
            if os.path.exists(full_old):
                new_files.append(old_path)
                continue

            file_name = os.path.basename(old_path)
            found = False
            for dir_path, files in files_map.items():
                if file_name in files:
                    new_path = (dir_path + "/" + file_name).strip("/")
                    new_files.append(new_path)
                    found = True
                    print(f"Fixed moved file in {group_name}: {old_path} -> {new_path}")
                    break
            if not found:
                print(f"Removed missing file from {group_name}: {old_path}")

        if auto_add:
            relevant_exts = (
                ".txt",
                ".css",
                ".js",
                ".ts",
                ".html",
                ".py",
                ".pyw",
                ".jsx",
                ".ps1",
                ".bat",
                ".json",
                ".tsx",
                ".rs",
                ".glsl",
                ".md",
                ".mjs",
            )
            current_count = len(new_files)
            do_auto_scan = True
            if current_count > 0 and current_count < 30:
                # Protection for small focused/curated groups (see test_docs_integrity size caps and AGENTS.md).
                # Prevents the broad dir-name heuristic from bloating manually-curated small lists (e.g. repo_integrity_tooling, gm2026_*, orbit_*, vlm_development).
                # Large legacy groups may still accumulate; agents must use small focused groups (defaults now point at them).
                do_auto_scan = False
                print(f"Protected small curated group {group_name} ({current_count} files) from auto-add bloat")
            if do_auto_scan:
                for dir_path, files in files_map.items():
                    if group_name.lower() in dir_path.lower() or (
                        group_name == "backend_sidecar" and "backend" in dir_path.lower()
                    ) or (
                        group_name == "frontend_logic" and "src" in dir_path.lower()
                    ):
                        for file in files:
                            if file.endswith(relevant_exts):
                                new_path = (dir_path + "/" + file).strip("/")
                                if new_path not in new_files:
                                    new_files.append(new_path)
                                    print(f"Auto-added to {group_name}: {new_path}")

        group["files"] = sorted(set(new_files))
        group.pop("paths", None)


def update_exclusions(exclusions: Dict, all_dirs: set) -> None:
    for dir_path in sorted(all_dirs):
        if dir_path not in exclusions:
            exclusions[dir_path] = {"note": "[collapsed (+)]"}
            print(f"Added exclusion for new dir: {dir_path}")

    for ex_dir in list(exclusions):
        if ex_dir not in all_dirs:
            del exclusions[ex_dir]
            print(f"Removed unused exclusion: {ex_dir}")


def _load_or_init_bank(bank_path: str) -> Dict:
    if os.path.exists(bank_path):
        with open(bank_path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    print(f"Initialized new {bank_path} with default schema.")
    return copy.deepcopy(DEFAULT_SCHEMA)


def maintain_summary_bank(
    root_dir: str,
    bank_path: str,
    use_gitignore: bool = True,
    skip_dirs: Optional[List[str]] = None,
    skip_prefixes: Tuple[str, ...] = ("__",),
    skip_suffixes: Tuple[str, ...] = (),
    skip_files: Optional[List[str]] = None,
    auto_add: bool = False,
) -> None:
    if skip_dirs is None:
        skip_dirs = []
    if skip_files is None:
        skip_files = list(DEFAULT_SKIP_FILES)

    enforced_skip_dirs = [".secrets"]

    # Load existing bank first so scan uses existing defaults (fixes the ".github/.tools exclusions explosion").
    data = _load_or_init_bank(bank_path)
    data.setdefault("defaults", {})
    data.setdefault("groups", {})
    data.setdefault("exclusions", {})

    existing_defaults = data.get("defaults", {}) or {}
    existing_skip = _normalize_group_entries(existing_defaults.get("skip_dirs"))
    base_skip = list((DEFAULT_SCHEMA.get("defaults", {}) or {}).get("skip_dirs", []) or [])

    git_patterns = load_gitignore(root_dir) if use_gitignore else []
    inferred_skip = infer_skip_dirnames_from_gitignore(git_patterns) if use_gitignore else []

    scan_skip_dirs = _unique(
        base_skip
        + existing_skip
        + _normalize_group_entries(skip_dirs)
        + enforced_skip_dirs
        + inferred_skip
    )

    all_files = collect_all_files(
        root_dir=root_dir,
        skip_dirs=scan_skip_dirs,
        skip_prefixes=skip_prefixes,
        skip_suffixes=skip_suffixes,
        skip_files=skip_files,
        git_patterns=git_patterns,
    )

    # Persist merged defaults
    data["defaults"] = data.get("defaults", {}) or {}
    data["defaults"]["skip_dirs"] = sorted(set(scan_skip_dirs))

    update_groups(data["groups"], all_files, root_dir, auto_add)
    update_exclusions(data["exclusions"], all_files["dirs"])  # type: ignore

    with open(bank_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Updated {bank_path}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Maintain summary_bank.json: update file lists, fix moved, add dirs/exclusions."
    )
    parser.add_argument("--root", default=".", help="Project root directory.")
    parser.add_argument("--bank", default="summary_bank.json", help="Path to summary_bank.json.")
    parser.add_argument(
        "--no-gitignore",
        action="store_false",
        dest="use_gitignore",
        default=True,
        help="Ignore .gitignore.",
    )
    parser.add_argument("--skip-dirs", nargs="*", default=None, help="Additional skip_dirs to add to defaults.")
    parser.add_argument("--auto-add", action="store_true", help="Auto-add new relevant files to groups.")
    parser.add_argument("--audit", action="store_true", help="Print a usefulness audit instead of modifying the bank.")
    parser.add_argument("--audit-json", action="store_true", help="Print the usefulness audit as JSON.")
    parser.add_argument("--fail-on-audit", action="store_true", help="Exit non-zero when blocking audit issues are found.")
    parser.add_argument("--max-group-files", type=int, default=AUDIT_DEFAULT_MAX_GROUP_FILES)
    parser.add_argument("--max-default-groups", type=int, default=AUDIT_DEFAULT_MAX_DEFAULT_GROUPS)
    parser.add_argument("--hotspot-min-groups", type=int, default=AUDIT_DEFAULT_HOTSPOT_MIN_GROUPS)
    parser.add_argument("--max-bank-kb", type=int, default=AUDIT_DEFAULT_MAX_BANK_KB)
    args = parser.parse_args(argv)

    if args.root and args.root != ".":
        root_path = Path(args.root).expanduser().resolve()
    else:
        root_path = find_repo_root(Path.cwd()) or find_repo_root(Path(__file__).resolve().parent) or Path.cwd().resolve()

    bank_path = Path(args.bank)
    if not bank_path.is_absolute():
        bank_path = root_path / bank_path

    if args.audit or args.audit_json:
        report = audit_summary_bank(
            bank_path=str(bank_path),
            root_dir=str(root_path),
            max_group_files=int(args.max_group_files),
            max_default_groups=int(args.max_default_groups),
            hotspot_min_groups=int(args.hotspot_min_groups),
            max_bank_kb=int(args.max_bank_kb),
        )
        if args.audit_json:
            print(json.dumps(report, indent=2))
        else:
            print_audit_report(report)
        if args.fail_on_audit and not bool(report.get("success")):
            return 1
        return 0

    maintain_summary_bank(
        root_dir=str(root_path),
        bank_path=str(bank_path),
        use_gitignore=bool(args.use_gitignore),
        skip_dirs=args.skip_dirs,
        auto_add=bool(args.auto_add),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
