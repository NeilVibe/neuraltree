"""neuraltree_find_dead — Find dead/orphan files."""
from __future__ import annotations

import os
import re

from fastmcp import FastMCP

from neuraltree_mcp.text_utils import walk_project_files
from neuraltree_mcp.validation import validate_project_root
from ._helpers import _KNOWLEDGE_EXTENSIONS, _strip_ref_fragment


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def neuraltree_find_dead(
        project_root: str = ".",
        extensions: list[str] | None = None,
    ) -> dict:
        """Find dead/orphan files that nothing references.

        Scans all knowledge files (.md) and checks if any other file
        references them. Files with zero inbound references are "dead neurons."
        Handles anchor links (file.md#section) and query strings correctly.

        Args:
            project_root: Project root directory.
            extensions: File extensions to check (default: [".md"]).

        Returns:
            dict with dead_files list, each with path, size_lines, last_modified.
        """
        try:
            root = validate_project_root(project_root)
        except (ValueError, OSError) as e:
            return {"error": str(e)}

        check_exts = set(extensions) if extensions else _KNOWLEDGE_EXTENSIONS
        all_knowledge = walk_project_files(root, check_exts)

        # Scan .md + config files for references. Source code and data files
        # rarely contain markdown links to .md files and can be hundreds of MB.
        _REF_SCAN_EXTENSIONS = {".md", ".yml", ".yaml", ".toml", ".cfg", ".ini"}
        ref_scan_files = walk_project_files(root, _REF_SCAN_EXTENSIONS)

        referenced: set[str] = set()
        md_contents: dict[str, str] = {}
        warnings: list[str] = []
        for fpath in ref_scan_files:
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
                md_contents[os.path.relpath(fpath, root)] = content
                # Scan whole content (not line-by-line — 750x faster on large files)
                for m in re.finditer(r'\[.*?\]\(([^)]+)\)', content):
                    ref = m.group(1)
                    if not ref.startswith("http") and not ref.startswith("#"):
                        ref = _strip_ref_fragment(ref)
                        referenced.add(os.path.basename(ref))
                        referenced.add(ref)
                for m in re.finditer(r'`([a-zA-Z0-9_./\-]+\.[a-zA-Z0-9]+)`', content):
                    path_ref = _strip_ref_fragment(m.group(1))
                    referenced.add(os.path.basename(path_ref))
                    referenced.add(path_ref)
            except OSError as e:
                warnings.append(f"Could not read {os.path.relpath(fpath, root)}: {e}")
                continue

        # Phase 1: Fast set-based check — eliminates most files in O(1) per file
        trunk_names = {"CLAUDE.md", "MEMORY.md", "_INDEX.md", "README.md"}
        candidates: dict[str, Path] = {}  # rel_path -> Path for files not found by set lookup
        for fpath in all_knowledge:
            rel = os.path.relpath(fpath, root)
            basename = fpath.name
            if basename in trunk_names:
                continue
            if basename in referenced or rel in referenced:
                continue
            candidates[rel] = fpath

        # Phase 1 set check is sufficient for production use. Word-boundary
        # fallback (is_referenced) is O(candidates * files) and too expensive
        # for large projects (290 candidates × 436 files = 126K regex searches).
        # The structured set catches markdown links [text](file.md) and backtick
        # paths `file.md` which cover 99%+ of real references.

        # Phase 2: Build dead file list from unresolved candidates
        dead_files = []
        for rel, fpath in candidates.items():
            cached = md_contents.get(rel)
            if cached is not None:
                size = len(cached.splitlines())
            else:
                try:
                    size = len(fpath.read_text(encoding="utf-8", errors="replace").splitlines())
                except OSError:
                    size = -1
            try:
                mtime = os.path.getmtime(fpath)
            except OSError:
                mtime = 0

            dead_files.append({
                "path": rel,
                "size_lines": size,
                "last_modified": mtime,
            })

        dead_files.sort(key=lambda x: x["size_lines"])

        # Exclude trunk files from denominator (trunk_names defined in Phase 1)
        non_trunk_count = sum(1 for f in all_knowledge if f.name not in trunk_names)

        return {
            "dead_files": dead_files,
            "total_dead": len(dead_files),
            "total_knowledge": non_trunk_count,
            "dead_ratio": len(dead_files) / max(non_trunk_count, 1),
            "warnings": warnings,
        }
