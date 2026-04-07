"""neuraltree_plan_split — Plan how to split a large file."""
from __future__ import annotations

import os
import re

from fastmcp import FastMCP

from neuraltree_mcp.validation import validate_project_root, validate_within_root


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def neuraltree_plan_split(
        target: str,
        project_root: str = ".",
        max_lines: int = 80,
    ) -> dict:
        """Plan how to split a large file into focused neurons.

        Analyzes a file's ## headings (skipping code blocks) and proposes splitting
        it into multiple smaller files, one per major section. Includes preamble
        content before the first heading.

        Args:
            target: Relative path of the file to split (e.g. "docs/MEGA_GUIDE.md").
            project_root: Project root directory.
            max_lines: Maximum lines per output file (default 80, per neuron format).

        Returns:
            dict with proposed splits, each with filename, heading, line_range, estimated_lines.
        """
        try:
            root = validate_project_root(project_root)
        except (ValueError, OSError) as e:
            return {"error": str(e)}

        target_path = root / target
        try:
            validate_within_root(target_path, root)
        except ValueError as e:
            return {"error": f"Path escapes project root: {e}"}

        if not target_path.exists():
            return {"error": f"File does not exist: {target}"}

        try:
            content = target_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return {"error": f"Cannot read file: {e}"}

        lines = content.splitlines()
        total_lines = len(lines)

        if total_lines <= max_lines:
            return {
                "target": target,
                "total_lines": total_lines,
                "needs_split": False,
                "splits": [],
                "message": f"File is {total_lines} lines — no split needed (max: {max_lines})",
            }

        # Find ## headings, skipping code blocks and frontmatter
        sections: list[dict] = []
        current_section: dict | None = None
        in_code_block = False
        in_frontmatter = False

        for i, line in enumerate(lines):
            # Track frontmatter (only at start of file)
            if i == 0 and line.strip() == "---":
                in_frontmatter = True
                continue
            if in_frontmatter and line.strip() == "---":
                in_frontmatter = False
                continue
            if in_frontmatter:
                continue

            # Track fenced code blocks
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            # Detect ## headings (but not ### or deeper)
            if re.match(r'^##\s+', line) and not re.match(r'^###', line):
                if current_section:
                    current_section["end_line"] = i
                    current_section["line_count"] = i - current_section["start_line"]
                heading = re.sub(r'^##\s+', '', line).strip()
                current_section = {
                    "heading": heading,
                    "start_line": i,
                    "end_line": total_lines,
                    "line_count": 0,
                }
                sections.append(current_section)

        if current_section:
            current_section["end_line"] = total_lines
            current_section["line_count"] = total_lines - current_section["start_line"]

        # If no sections found, can't auto-split
        if not sections:
            return {
                "target": target,
                "total_lines": total_lines,
                "needs_split": True,
                "splits": [],
                "message": f"File is {total_lines} lines but has no ## headings — manual split needed",
            }

        # Generate split proposals
        target_dir = os.path.dirname(target)
        target_stem = os.path.splitext(os.path.basename(target))[0]
        splits = []

        # Preamble: content before first ## heading
        first_heading_line = sections[0]["start_line"]
        if first_heading_line > 0:
            preamble_file = os.path.join(target_dir, f"{target_stem}_preamble.md") if target_dir else f"{target_stem}_preamble.md"
            splits.append({
                "filename": preamble_file,
                "heading": "(preamble — title and intro)",
                "start_line": 1,
                "end_line": first_heading_line,
                "estimated_lines": first_heading_line,
            })

        for sec in sections:
            # Generate a filename from the heading
            slug = re.sub(r'[^\w\s-]', '', sec["heading"].lower())
            slug = re.sub(r'\s+', '_', slug).strip('_')[:50]
            if not slug:
                slug = f"section_{len(splits) + 1}"

            filename = os.path.join(target_dir, f"{target_stem}_{slug}.md") if target_dir else f"{target_stem}_{slug}.md"

            splits.append({
                "filename": filename,
                "heading": sec["heading"],
                "start_line": sec["start_line"] + 1,  # 1-indexed for display
                "end_line": sec["end_line"],
                "estimated_lines": sec["line_count"],
            })

        # Also plan an index file
        index_file = os.path.join(target_dir, f"{target_stem}_INDEX.md") if target_dir else f"{target_stem}_INDEX.md"

        return {
            "target": target,
            "total_lines": total_lines,
            "needs_split": True,
            "section_count": len(sections),
            "splits": splits,
            "index_file": index_file,
            "references_to_update": f"Run neuraltree_plan_move('{target}', ...) to find references",
        }
