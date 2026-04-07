"""neuraltree_split_and_wire — Split a large file and wire all pieces."""
from __future__ import annotations

import os
import re

from fastmcp import FastMCP

from neuraltree_mcp.validation import validate_project_root, validate_within_root


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def neuraltree_split_and_wire(
        target: str,
        project_root: str = ".",
        max_lines: int = 500,
    ) -> dict:
        """Split a large file into focused pieces, wire them all, replace original with index.

        Atomic operation: splits by ## headings, writes each section as a separate
        file with ## Related back-links to siblings, replaces the original with an
        index file linking to all pieces. No orphans created.

        Args:
            target: Relative path of the file to split (e.g. "docs/MEGA_GUIDE.md").
            project_root: Project root directory.
            max_lines: Only split if file exceeds this line count (default 500).

        Returns:
            dict with original_lines, split_files created, index_file, wiring info.
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
        original_lines = len(lines)

        if original_lines <= max_lines:
            return {
                "target": target,
                "original_lines": original_lines,
                "needs_split": False,
                "message": f"File is {original_lines} lines — no split needed (max: {max_lines})",
            }

        # Parse ## sections (skip code blocks and frontmatter)
        sections: list[dict] = []
        current: dict | None = None
        in_code = False
        in_fm = False

        for i, line in enumerate(lines):
            if i == 0 and line.strip() == "---":
                in_fm = True
                continue
            if in_fm and line.strip() == "---":
                in_fm = False
                continue
            if in_fm:
                continue
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            if re.match(r'^##\s+', line) and not re.match(r'^###', line):
                if current:
                    current["end"] = i
                heading = re.sub(r'^##\s+', '', line).strip()
                current = {"heading": heading, "start": i, "end": len(lines)}
                sections.append(current)

        if current:
            current["end"] = len(lines)

        if not sections:
            return {
                "target": target,
                "original_lines": original_lines,
                "needs_split": True,
                "split_files": [],
                "message": "No ## headings found — cannot auto-split",
            }

        target_dir = os.path.dirname(target)
        target_stem = os.path.splitext(os.path.basename(target))[0]
        split_files: list[dict] = []
        split_filenames: list[str] = []
        warnings: list[str] = []

        # Preamble (content before first ## heading)
        first_section_start = sections[0]["start"]
        if first_section_start > 0:
            preamble_content = "\n".join(lines[:first_section_start]).strip()
            if preamble_content:
                preamble_name = f"{target_stem}_preamble.md"
                preamble_rel = os.path.join(target_dir, preamble_name) if target_dir else preamble_name
                preamble_path = root / preamble_rel
                preamble_path.parent.mkdir(parents=True, exist_ok=True)
                preamble_path.write_text(preamble_content + "\n", encoding="utf-8")
                split_files.append({"filename": preamble_rel, "heading": "(preamble)", "lines": first_section_start})
                split_filenames.append(preamble_rel)

        # Write each section as a separate file with ## Related to siblings
        for sec in sections:
            slug = re.sub(r'[^\w\s-]', '', sec["heading"].lower())
            slug = re.sub(r'\s+', '_', slug).strip('_')[:50]
            if not slug:
                slug = f"section_{len(split_files) + 1}"

            filename = f"{target_stem}_{slug}.md"
            file_rel = os.path.join(target_dir, filename) if target_dir else filename
            file_path = root / file_rel

            section_content = "\n".join(lines[sec["start"]:sec["end"]])

            # Add ## Related linking to all siblings
            related_lines = ["\n\n## Related\n"]
            for other in sections:
                if other["heading"] != sec["heading"]:
                    other_slug = re.sub(r'[^\w\s-]', '', other["heading"].lower())
                    other_slug = re.sub(r'\s+', '_', other_slug).strip('_')[:50]
                    other_name = f"{target_stem}_{other_slug}.md" if other_slug else f"{target_stem}_section.md"
                    related_lines.append(f"- [{other['heading']}]({other_name})")

            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(section_content + "\n".join(related_lines) + "\n", encoding="utf-8")

            section_lines = sec["end"] - sec["start"]
            split_files.append({"filename": file_rel, "heading": sec["heading"], "lines": section_lines})
            split_filenames.append(file_rel)

        # Replace original with index linking to all pieces
        idx_lines = [f"# {target_stem.replace('_', ' ').title()} — Index\n"]
        for sf in split_files:
            idx_lines.append(f"- [{sf['heading']}]({os.path.basename(sf['filename'])})")
        idx_lines.append(f"\n## Related\n")
        # Link index to first few split files
        for sf in split_files[:5]:
            idx_lines.append(f"- [{sf['heading']}]({os.path.basename(sf['filename'])})")

        target_path.write_text("\n".join(idx_lines) + "\n", encoding="utf-8")

        return {
            "target": target,
            "original_lines": original_lines,
            "needs_split": True,
            "split_files": split_files,
            "new_files": split_filenames,
            "index_file": target,  # original becomes the index
            "total_pieces": len(split_files),
            "warnings": warnings,
        }
