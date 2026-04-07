"""Shared helpers and constants for reorganize tools."""
from __future__ import annotations

import os
import re
from pathlib import Path

from neuraltree_mcp.text_utils import walk_project_files


_SEARCHABLE_EXTENSIONS = {
    ".md", ".py", ".js", ".ts", ".jsx", ".tsx", ".svelte", ".yml", ".yaml",
    ".json", ".sh", ".toml", ".cfg", ".ini", ".txt", ".html", ".css", ".scss",
    ".vue",
}

_KNOWLEDGE_EXTENSIONS = {".md"}


def _find_all_references(root: Path, old_path: str) -> tuple[list[dict], list[str]]:
    """Find all files that reference old_path (by basename or relative path).

    Uses word-boundary matching to prevent false positives (auth.md matching oauth.md).

    Returns (refs, warnings) where refs is list of {"file", "line", "text"}.
    """
    basename = os.path.basename(old_path)
    # Word-boundary patterns prevent substring false positives
    patterns = [re.compile(r'(?<![a-zA-Z0-9_])' + re.escape(basename) + r'(?![a-zA-Z0-9_])')]
    if old_path != basename:
        patterns.append(re.compile(r'(?<![a-zA-Z0-9_])' + re.escape(old_path) + r'(?![a-zA-Z0-9_])'))

    refs = []
    warnings = []
    for fpath in walk_project_files(root, _SEARCHABLE_EXTENSIONS):
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            warnings.append(f"Could not read {os.path.relpath(fpath, root)}: {e}")
            continue
        rel = os.path.relpath(fpath, root)
        for line_num, line in enumerate(content.splitlines(), 1):
            for pat in patterns:
                if pat.search(line):
                    refs.append({"file": rel, "line": line_num, "text": line.strip()})
                    break
    return refs, warnings


def _compute_rewrites(references: list[dict], old_path: str, new_path: str) -> list[dict]:
    """Compute text replacements needed for a file move.

    Uses targeted replacement within markdown link targets and backtick paths
    to avoid corrupting unrelated text on the same line.

    Returns list of {"file", "line", "old_text", "new_text"} for each replacement.
    """
    old_basename = os.path.basename(old_path)
    new_basename = os.path.basename(new_path)
    rewrites = []

    for ref in references:
        old_text = ref["text"]
        new_text = old_text

        # Replace full relative path first (more specific), with word boundaries
        if old_path in new_text:
            new_text = re.sub(
                r'(?<![a-zA-Z0-9_])' + re.escape(old_path) + r'(?![a-zA-Z0-9_])',
                new_path, new_text
            )
        # Then replace basename (less specific, only if path wasn't already replaced)
        elif old_basename != new_basename and old_basename in new_text:
            new_text = re.sub(
                r'(?<![a-zA-Z0-9_])' + re.escape(old_basename) + r'(?![a-zA-Z0-9_])',
                new_basename, new_text
            )

        if new_text != old_text:
            rewrites.append({
                "file": ref["file"],
                "line": ref["line"],
                "old_text": old_text,
                "new_text": new_text,
            })
    return rewrites


def _strip_ref_fragment(ref: str) -> str:
    """Strip #fragment and ?query from a reference path."""
    ref = ref.split("#")[0]
    ref = ref.split("?")[0]
    return ref
