"""neuraltree_generate_index — Generate _INDEX.md for a directory."""
from __future__ import annotations

import os
import re

from fastmcp import FastMCP

from neuraltree_mcp.validation import validate_project_root, validate_within_root


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def neuraltree_generate_index(
        directory: str,
        project_root: str = ".",
    ) -> dict:
        """Generate an _INDEX.md for a directory based on its .md files.

        Scans the directory for markdown files, reads their frontmatter
        (name, description), and produces an index with links.

        Args:
            directory: Relative path to the directory (e.g. "memory/rules").
            project_root: Project root directory.

        Returns:
            dict with directory, files found, generated index content, and subdirectories.
        """
        try:
            root = validate_project_root(project_root)
        except (ValueError, OSError) as e:
            return {"error": str(e)}

        dir_path = root / directory
        try:
            validate_within_root(dir_path, root)
        except ValueError as e:
            return {"error": f"Path escapes project root: {e}"}

        if not dir_path.is_dir():
            return {"error": f"Not a directory: {directory}"}

        entries = []
        subdirectories = []
        warnings = []
        for fpath in sorted(dir_path.iterdir()):
            if fpath.is_dir():
                subdirectories.append(fpath.name)
                continue
            if not fpath.name.endswith(".md") or fpath.name == "_INDEX.md":
                continue
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                warnings.append(f"Could not read {fpath.name}: {e}")
                continue

            # Extract name and description from frontmatter
            name = fpath.stem.replace("_", " ").replace("-", " ").title()
            description = ""
            fm_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
            if fm_match:
                fm = fm_match.group(1)
                name_match = re.search(r'name:\s*(.+)', fm)
                desc_match = re.search(r'description:\s*(.+)', fm)
                if name_match:
                    name = name_match.group(1).strip()
                if desc_match:
                    description = desc_match.group(1).strip()

            if not description:
                # Use first non-empty, non-heading line as description
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                        description = stripped[:100]
                        break

            entries.append({
                "file": fpath.name,
                "name": name,
                "description": description,
            })

        # Generate index content
        dir_name = os.path.basename(directory).replace("_", " ").title()
        idx_lines = [
            f"# {dir_name}\n",
            "",
        ]
        for e in entries:
            desc_suffix = f" — {e['description']}" if e["description"] else ""
            idx_lines.append(f"- [{e['name']}]({e['file']}){desc_suffix}")

        index_content = "\n".join(idx_lines) + "\n"

        return {
            "directory": directory,
            "file_count": len(entries),
            "entries": entries,
            "index_content": index_content,
            "subdirectories": subdirectories,
            "warnings": warnings,
        }
