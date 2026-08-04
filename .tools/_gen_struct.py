#!/usr/bin/env python3
# PROJECT GENA
# File: _gen_struct.py
# Purpose: Generates a single focused text summary of related selected files.

from __future__ import annotations

import os
import fnmatch
import json
import argparse
import glob
from pathlib import Path
from typing import Dict, List, Optional, Tuple

NOTE_DEFAULT = "[Collapsed Dir (+)]"
CONTEXT_MANIFEST_MAX_ITEMS = 100

def find_repo_root(start: Path) -> Optional[Path]:
    p = start.resolve()
    for cur in [p] + list(p.parents):
        git_path = cur / ".git"
        if git_path.exists():
            return cur
    return None

def _normalize_rel(p: str) -> str:
    p = (p or "").strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    while p.startswith("/"):
        p = p[1:]
    if p.endswith("/") and p != "/":
        p = p.rstrip("/")
    return p

def _archive_ref_parts(ref: object) -> Optional[Tuple[str, str]]:
    if not isinstance(ref, str) or "#groups." not in ref:
        return None
    archive_path, group_name = ref.split("#groups.", 1)
    archive_path = archive_path.strip()
    group_name = group_name.strip()
    if not archive_path or not group_name:
        return None
    return archive_path, group_name

def _load_archived_group_entries(group: Dict, summary_bank_dir: str) -> List[str]:
    ref_parts = _archive_ref_parts(group.get("_archive_ref"))
    if not ref_parts:
        return []
    archive_path_raw, archive_group_name = ref_parts
    archive_path = archive_path_raw
    if not os.path.isabs(archive_path):
        archive_path = os.path.join(summary_bank_dir, archive_path)
    archive_path = os.path.abspath(archive_path)
    if not os.path.exists(archive_path):
        return []

    with open(archive_path, "r", encoding="utf-8") as f:
        archive_data = json.load(f) or {}
    archived_group = (archive_data.get("groups", {}) or {}).get(archive_group_name)
    if not isinstance(archived_group, dict):
        return []
    paths = archived_group.get("paths")
    if paths is None:
        paths = archived_group.get("files", [])
    return [str(path) for path in (paths or []) if str(path)]

def _load_summary_bank(path: str) -> Tuple[Dict, Dict, Dict]:
    groups: Dict = {}
    exclusions: Dict = {}
    defaults: Dict = {"groups": [], "group": None, "tree": True, "max_kb": 200, "skip_dirs": []}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        groups = data.get("groups", {}) or {}
        exclusions = data.get("exclusions", {}) or {}
        d = data.get("defaults", {}) or {}
        defaults.update(d)
        if "group" in d and ("groups" not in d or not d.get("groups")):
            defaults["groups"] = [d["group"]] if d["group"] else []
    return groups, exclusions, defaults

def list_group_names(summary_bank: str) -> List[str]:
    groups, _exclusions, _defaults = _load_summary_bank(summary_bank)
    return sorted(str(name) for name in groups.keys())

def _read_gitignore(root_dir: str) -> List[str]:
    p = os.path.join(root_dir, ".gitignore")
    if not os.path.exists(p):
        return []
    with open(p, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]

def _is_ignored(rel_path: str, patterns: List[str]) -> bool:
    rel_path = rel_path.replace(os.sep, "/")
    for pat in patterns:
        anchored = pat.startswith("/")
        p = pat[1:] if anchored else pat
        if p.endswith("/"):
            p = p[:-1] + "/*"
        if anchored:
            if fnmatch.fnmatch(rel_path, p):
                return True
        else:
            parts = rel_path.split("/")
            for i in range(len(parts) + 1):
                subpath = "/".join(parts[:i]) + ("/" if i > 0 else "") + p
                if fnmatch.fnmatch(rel_path, subpath):
                    return True
    return False

def _walk_sorted(directory: str) -> List[str]:
    entries = os.listdir(directory)
    entries.sort()
    dirs = [e for e in entries if os.path.isdir(os.path.join(directory, e))]
    files = [e for e in entries if not os.path.isdir(os.path.join(directory, e))]
    return dirs + files

def _emit_tree(
    root_dir: str,
    excludes: Dict,
    skip_dirs: List[str],
    skip_prefixes: Tuple[str, ...],
    skip_suffixes: Tuple[str, ...],
    skip_files: List[str],
    git_patterns: List[str],
) -> List[str]:
    lines = ["./"]

    def rec(directory: str, prefix: str = ""):
        entries = _walk_sorted(directory)
        filtered: List[str] = []

        for entry in entries:
            full = os.path.join(directory, entry)
            rel = os.path.relpath(full, root_dir).replace(os.sep, "/")
            rel = _normalize_rel(rel)

            if entry in skip_files:
                continue
            if entry.startswith(skip_prefixes) or entry.endswith(skip_suffixes):
                continue
            if os.path.isdir(full) and entry in skip_dirs:
                filtered.append(entry)
                continue
            if _is_ignored(rel, git_patterns):
                continue
            filtered.append(entry)

        for idx, entry in enumerate(filtered):
            full = os.path.join(directory, entry)
            rel = os.path.relpath(full, root_dir).replace(os.sep, "/")
            rel = _normalize_rel(rel)

            is_last = idx == len(filtered) - 1
            branch = "└── " if is_last else "├── "
            line = f"{prefix}{branch}{entry}"

            if os.path.isdir(full):
                if entry in skip_dirs:
                    lines.append(line + " [Dir Collapsed (+)]")
                    continue
                if rel in excludes:
                    note = (excludes.get(rel) or {}).get("note", NOTE_DEFAULT)
                    lines.append(f"{line} {note}")
                else:
                    lines.append(line)
                    sub_prefix = prefix + (" " if is_last else "│ ")
                    rec(full, sub_prefix)
            else:
                lines.append(line)

    rec(root_dir, "")
    return lines

def _read_file_utf8(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        return "[Error reading file: Encoding issues]"
    except Exception as e:
        return f"[Error reading file: {e}]"

def _emit_region_block(path_rel: str, content: str) -> str:
    return "#region " + path_rel + "\n" + content.rstrip("\n") + "\n#endregion\n"

def _has_glob_meta(s: str) -> bool:
    return any(ch in s for ch in ("*", "?", "["))

def _expand_group_path_patterns(root_dir: str, pattern: str) -> List[str]:
    pat = _normalize_rel(pattern)
    if not pat:
        return []
    pat_os = pat.replace("/", os.sep)
    abs_pat = os.path.join(root_dir, pat_os)

    if _has_glob_meta(pat) or "**" in pat:
        matches = glob.glob(abs_pat, recursive=True)
        matches = [m for m in matches if os.path.isfile(m)]
        matches.sort()
        return matches

    return [os.path.join(root_dir, pat_os)]

def _collect_group_regions(
    root_dir: str,
    groups_conf: Dict,
    group_name: str,
    seen: set,
    git_patterns: List[str],
    skip_files: List[str],
    skip_prefixes: Tuple[str, ...],
    skip_suffixes: Tuple[str, ...],
    include_archived: bool = False,
    summary_bank_dir: str = ".",
) -> List[str]:
    grp = groups_conf.get(group_name)
    if not grp:
        return [f"#region REQUEST/context.txt\nGroup not found: {group_name}\n#endregion\n"]

    if grp.get("_archived") and not include_archived:
        archive_ref = grp.get("_archive_ref") or "summary_bank archive"
        note = grp.get("_archive_note") or "This group is intentionally excluded from normal context because it is too broad."
        return [
            "#region REQUEST/context.txt\n"
            f"Group archived: {group_name}\n"
            f"{note}\n"
            f"Archive reference: {archive_ref}\n"
            "Use a focused group or rerun with --include-archived if this broad context is truly required.\n"
            "#endregion\n"
        ]

    paths = grp.get("paths")
    if paths is None:
        paths = grp.get("files", [])
    paths = list(paths or [])
    if grp.get("_archived") and include_archived and not paths:
        paths = _load_archived_group_entries(grp, summary_bank_dir)

    required_paths = [str(path) for path in (grp.get("required_files") or []) if str(path)]
    required_set = {_normalize_rel(path) for path in required_paths}
    if required_paths:
        paths = required_paths + [path for path in paths if _normalize_rel(str(path)) not in required_set]

    regions: List[str] = []

    for raw in paths:
        raw = str(raw)
        for abs_path in _expand_group_path_patterns(root_dir, raw):
            if not os.path.isfile(abs_path):
                continue

            rel_norm = os.path.relpath(abs_path, root_dir).replace(os.sep, "/")
            rel_norm = _normalize_rel(rel_norm)

            base = os.path.basename(rel_norm)
            is_required = rel_norm in required_set
            if base in skip_files and not is_required:
                continue
            if base.startswith(skip_prefixes) or base.endswith(skip_suffixes):
                continue
            if _is_ignored(rel_norm, git_patterns):
                continue

            if rel_norm in seen:
                continue
            seen.add(rel_norm)
            regions.append(_emit_region_block(rel_norm, _read_file_utf8(abs_path)))

    return regions

def _region_path(block: str) -> str:
    if not block.startswith("#region "):
        return ""
    first_line = block.split("\n", 1)[0]
    return first_line.removeprefix("#region ").strip()

def _manifest_items(items: List[str]) -> Dict[str, object]:
    return {
        "count": len(items),
        "items": items[:CONTEXT_MANIFEST_MAX_ITEMS],
        "items_truncated": len(items) > CONTEXT_MANIFEST_MAX_ITEMS,
    }

def _append_with_budget(parts: List[str], block: str, budget_bytes: int, used_bytes: int) -> Tuple[int, bool]:
    block_bytes = len(block.encode("utf-8"))
    if used_bytes + block_bytes <= budget_bytes:
        parts.append(block)
        return used_bytes + block_bytes, True

    if block.startswith("#region "):
        header_end = block.find("\n")
        footer = "\n#endregion\n"
        header = block[: header_end + 1] if header_end != -1 else "#region unknown\n"

        remain_budget = max(0, budget_bytes - used_bytes - len((header + footer).encode("utf-8")))
        if remain_budget <= 0:
            return used_bytes, False

        body = block[header_end + 1 :] if header_end != -1 else block
        if "\n#endregion" in body:
            body = body.rsplit("\n#endregion", 1)[0]

        body_bytes = body.encode("utf-8")
        if len(body_bytes) > remain_budget:
            body = body_bytes[:remain_budget].decode("utf-8", errors="ignore") + "\n[truncated due to budget]"

        truncated = header + body + footer
        parts.append(truncated)
        return budget_bytes, True

    return used_bytes, False

def generate(
    root_dir: str,
    output_file: str,
    summary_bank: str,
    include_tree: Optional[bool] = None,
    only_groups: Optional[List[str]] = None,
    budget_kb: Optional[int] = None,
    use_gitignore: bool = True,
    skip_dirs: Optional[List[str]] = None,
    skip_prefixes: Tuple[str, ...] = ("__",),
    skip_suffixes: Tuple[str, ...] = (),
    skip_files: Optional[List[str]] = None,
    include_archived: bool = False,
) -> None:
    if skip_dirs is None:
        skip_dirs = []
    if skip_files is None:
        skip_files = [
            "package-lock.json",
            "Cargo.lock",
            "yarn.lock",
            "pnpm-lock.yaml",
            "setup_log.txt",
            "debug_log.txt",
            "_struct_summary.txt",
            "_structure_with_content.txt",
        ]

    enforced_skip_dirs = [".secrets"]
    git_patterns = _read_gitignore(root_dir) if use_gitignore else []

    groups, exclusions, defaults = _load_summary_bank(summary_bank)
    summary_bank_dir = os.path.dirname(os.path.abspath(summary_bank))

    exclusions_norm: Dict = {}
    for k, v in (exclusions or {}).items():
        nk = _normalize_rel(str(k))
        if nk:
            exclusions_norm[nk] = v or {}

    default_groups = list(defaults.get("groups") or [])
    default_tree = bool(defaults.get("tree", True))
    default_budget_kb = int(defaults.get("max_kb", 150))
    default_skip_dirs = list(defaults.get("skip_dirs") or [])

    if include_tree is None:
        include_tree = default_tree
    if budget_kb is None:
        budget_kb = default_budget_kb

    skip_dirs = list(dict.fromkeys((skip_dirs or []) + default_skip_dirs + enforced_skip_dirs))

    budget_bytes = max(1, budget_kb) * 1024
    manifest_reserve_bytes = min(8192, max(1024, budget_bytes // 4))
    content_budget_bytes = max(1, budget_bytes - manifest_reserve_bytes)
    out_parts: List[str] = []
    used_bytes = 0
    tree_truncated = False

    if include_tree:
        tree_lines = _emit_tree(root_dir, exclusions_norm, skip_dirs, skip_prefixes, skip_suffixes, skip_files, git_patterns)
        tree_blob = "\n".join(tree_lines) + "\n\n"
        tree_budget = min(content_budget_bytes // 4, 64 * 1024)
        tree_bytes = len(tree_blob.encode("utf-8"))
        used_bytes, tree_added = _append_with_budget(out_parts, tree_blob, tree_budget, used_bytes)
        tree_truncated = not tree_added or tree_bytes > tree_budget

    groups_to_emit: List[str] = []
    if only_groups:
        groups_to_emit = [g for g in only_groups if g]
    elif default_groups:
        groups_to_emit = [g for g in default_groups if g]

    seen_files: set = set()
    planned_blocks: List[str] = []
    for gname in groups_to_emit:
        planned_blocks.extend(_collect_group_regions(
            root_dir=root_dir,
            groups_conf=groups,
            group_name=gname,
            seen=seen_files,
            git_patterns=git_patterns,
            skip_files=skip_files,
            skip_prefixes=skip_prefixes,
            skip_suffixes=skip_suffixes,
            include_archived=include_archived,
            summary_bank_dir=summary_bank_dir,
        ))

    emitted: List[str] = []
    truncated: List[str] = []
    omitted: List[str] = []
    required_files: List[str] = []
    for gname in groups_to_emit:
        group = groups.get(gname) or {}
        for path in group.get("required_files") or []:
            normalized = _normalize_rel(str(path))
            if normalized and normalized not in required_files:
                required_files.append(normalized)
    required_set = set(required_files)
    budget_exhausted = False
    for block in planned_blocks:
        path = _region_path(block)
        if budget_exhausted:
            if path:
                omitted.append(path)
            continue
        block_bytes = len(block.encode("utf-8"))
        remaining = max(0, content_budget_bytes - used_bytes)
        if path and path not in required_set and block_bytes > remaining:
            omitted.append(path)
            continue
        used_bytes, added = _append_with_budget(out_parts, block, content_budget_bytes, used_bytes)
        if not added:
            if path:
                omitted.append(path)
            if path in required_set:
                budget_exhausted = True
        elif block_bytes > remaining:
            if path:
                truncated.append(path)
            budget_exhausted = True
        elif path:
            emitted.append(path)

    required_not_fully_emitted = [path for path in required_files if path not in emitted]
    manifest = {
        "schema": "lfm_orbit_context_emission_manifest_v1",
        "groups": groups_to_emit,
        "budget_bytes": budget_bytes,
        "content_budget_bytes": content_budget_bytes,
        "content_used_bytes": used_bytes,
        "tree_requested": bool(include_tree),
        "tree_truncated": tree_truncated,
        "emitted": _manifest_items(emitted),
        "truncated": _manifest_items(truncated),
        "omitted": _manifest_items(omitted),
        "required_files": required_files,
        "required_not_fully_emitted": required_not_fully_emitted,
    }
    manifest_block = _emit_region_block(
        "REQUEST/context-manifest.json",
        json.dumps(manifest, indent=2, ensure_ascii=False),
    )
    used_bytes, manifest_added = _append_with_budget(out_parts, manifest_block, budget_bytes, used_bytes)
    if not manifest_added:
        raise RuntimeError("Context emission manifest did not fit inside the configured budget.")

    if output_file == "-":
        import sys
        sys.stdout.buffer.write("".join(out_parts).encode("utf-8"))
    else:
        with open(output_file, "w", encoding="utf-8", newline="\n") as f:
            f.write("".join(out_parts))

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit REGION-ONLY summary constrained by a size budget and driven by summary_bank.json defaults."
    )
    parser.add_argument("--root", default=".", help="Root directory.")
    parser.add_argument("--out", default="_struct_summary.txt", help="Output file.")
    parser.add_argument("--bank", default="summary_bank.json", help="Path to summary_bank.json.")
    parser.add_argument("--group", action="append", help="Emit only this group (repeatable).")
    parser.add_argument("--groups", help="Comma-separated list of groups to emit, overrides defaults.groups if provided.")
    parser.add_argument("--list-groups", action="store_true", help="Print available summary-bank group names and exit.")
    parser.add_argument("--no-tree", action="store_true", help="Do not include ASCII tree.")
    parser.add_argument("--tree", action="store_true", help="Force include ASCII tree.")
    parser.add_argument("--budget-kb", type=int, default=None, help="Override defaults.max_kb.")
    parser.add_argument("--no-gitignore", action="store_true", help="Ignore .gitignore rules.")
    parser.add_argument("--skip-dirs", nargs="*", default=[], help="Extra directory names to skip at any depth in the tree.")
    parser.add_argument("--include-archived", action="store_true", help="Allow archived broad groups to emit context.")
    args = parser.parse_args()

    if args.root and args.root != ".":
        root_path = Path(args.root).expanduser().resolve()
    else:
        root_path = find_repo_root(Path.cwd()) or find_repo_root(Path(__file__).resolve().parent) or Path.cwd().resolve()

    if args.out == "-":
        out_path_str = "-"
    else:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = root_path / out_path
        out_path_str = str(out_path)

    bank_path = Path(args.bank)
    if not bank_path.is_absolute():
        bank_path = root_path / bank_path

    if args.list_groups:
        for group_name in list_group_names(str(bank_path)):
            print(group_name)
        return 0

    include_tree = None
    if args.no_tree:
        include_tree = False
    if args.tree:
        include_tree = True

    only_groups: Optional[List[str]] = None
    if args.group:
        only_groups = args.group
    if args.groups:
        only_groups = [g.strip() for g in args.groups.split(",") if g.strip()]

    generate(
        root_dir=str(root_path),
        output_file=out_path_str,
        summary_bank=str(bank_path),
        include_tree=include_tree,
        only_groups=only_groups,
        budget_kb=args.budget_kb,
        use_gitignore=not args.no_gitignore,
        skip_dirs=args.skip_dirs,
        include_archived=bool(args.include_archived),
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
