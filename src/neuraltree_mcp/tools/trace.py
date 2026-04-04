"""neuraltree_trace — Reference tracing for files and directories."""
from __future__ import annotations

import os
import re
from pathlib import Path

from fastmcp import FastMCP

from neuraltree_mcp.text_utils import walk_project_files
from neuraltree_mcp.validation import validate_project_root, validate_within_root

SEARCHABLE_EXTENSIONS = {
    ".md", ".py", ".js", ".ts", ".svelte", ".yml", ".yaml",
    ".json", ".sh", ".toml", ".cfg", ".ini", ".txt", ".html",
    ".css", ".scss",
}


def _collect_searchable_files(root: Path) -> list[Path]:
    """Collect all files with searchable extensions under root."""
    return walk_project_files(root, SEARCHABLE_EXTENSIONS)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def neuraltree_trace(target: str, project_root: str = ".") -> dict:
        """Trace ALL references to a file or directory.

        Greps through all searchable files (.md, .py, .js, .yml, etc.)
        for mentions of the target's basename and relative path.
        Also inspects the target file itself for outbound references.

        Args:
            target: File or directory path to trace.
            project_root: Project root for relative path resolution.

        Returns:
            dict with referenced_by, references_to, is_alive, permission_errors.
        """
        try:
            root = validate_project_root(project_root)
        except ValueError as e:
            return {"referenced_by": [], "references_to": [], "is_alive": False,
                    "permission_errors": [], "error": str(e)}
        target_path = Path(target)
        if not target_path.is_absolute():
            target_path = root / target_path
        target_path = target_path.resolve()

        try:
            validate_within_root(target_path, root)
        except ValueError:
            return {
                "referenced_by": [], "references_to": [],
                "is_alive": False, "permission_errors": [],
                "error": f"Target escapes project root: {target}",
            }

        rel_target = os.path.relpath(target_path, root)
        basename = target_path.name

        referenced_by: list[str] = []
        references_to: list[str] = []
        permission_errors: list[str] = []

        # Build search patterns
        patterns = []
        if basename:
            patterns.append(re.compile(re.escape(basename)))
        if rel_target and rel_target != basename:
            patterns.append(re.compile(re.escape(rel_target)))

        searchable = _collect_searchable_files(root)

        for fpath in searchable:
            # Don't search the target itself for inbound refs
            try:
                fpath_resolved = fpath.resolve()
            except OSError:
                permission_errors.append(str(fpath))
                continue

            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                permission_errors.append(str(fpath))
                continue

            rel_fpath = os.path.relpath(fpath, root)

            if fpath_resolved == target_path:
                # This IS the target — extract outbound references
                # Look for markdown links, backtick paths, import statements
                _extract_outbound_refs(content, root, references_to)
                continue

            # Search for inbound references to target
            for line_num, line in enumerate(content.splitlines(), 1):
                for pat in patterns:
                    if pat.search(line):
                        referenced_by.append(f"{rel_fpath}:{line_num}")
                        break  # one match per line is enough

        # Deduplicate
        referenced_by = sorted(set(referenced_by))
        references_to = sorted(set(references_to))

        return {
            "referenced_by": referenced_by,
            "references_to": references_to,
            "is_alive": len(referenced_by) > 0,
            "permission_errors": permission_errors,
        }


def _extract_outbound_refs(content: str, root: Path, refs: list[str]) -> None:
    """Extract outbound references from file content."""
    # Markdown links: [text](path)
    for m in re.finditer(r'\[.*?\]\(([^)]+)\)', content):
        ref = m.group(1)
        if not ref.startswith("http") and not ref.startswith("#"):
            refs.append(ref)

    # Backtick paths: `path/to/file`
    for m in re.finditer(r'`([a-zA-Z0-9_./\-]+\.[a-zA-Z0-9]+)`', content):
        refs.append(m.group(1))

    # Python imports: from X import Y / import X
    for m in re.finditer(r'(?:from|import)\s+([a-zA-Z0-9_.]+)', content):
        module = m.group(1).replace(".", "/")
        refs.append(module)
