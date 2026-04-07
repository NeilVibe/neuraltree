"""neuraltree_shrink_and_wire — Shrink a file by extracting sections."""
from __future__ import annotations

import os
import re

from fastmcp import FastMCP

from neuraltree_mcp.validation import validate_project_root, validate_within_root


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def neuraltree_shrink_and_wire(
        target: str,
        sections_to_extract: list[str],
        project_root: str = ".",
    ) -> dict:
        """Shrink a large file by extracting sections, then wire everything.

        Atomic operation: extracts named sections into separate files, replaces
        them with links in the original, generates ## Related for all new files,
        and creates _INDEX.md if needed. No orphans created.

        Args:
            target: Relative path of file to shrink (e.g. "CLAUDE.md").
            sections_to_extract: List of ## heading names to extract
                (e.g. ["Commands", "Project Structure"]).
            project_root: Project root directory.

        Returns:
            dict with original_lines, new_lines, extracted files, wiring results.
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
        target_dir = os.path.dirname(target)
        target_stem = os.path.splitext(os.path.basename(target))[0]
        warnings: list[str] = []
        extracted_files: list[dict] = []
        remaining_lines: list[str] = []
        link_insertions: list[str] = []

        # Parse sections
        i = 0
        while i < len(lines):
            line = lines[i]
            heading_match = re.match(r'^##\s+(.+)', line)

            if heading_match:
                heading_name = heading_match.group(1).strip()

                if heading_name in sections_to_extract:
                    # Find section end
                    section_lines = [line]
                    j = i + 1
                    while j < len(lines):
                        if re.match(r'^##\s+', lines[j]) and not re.match(r'^###', lines[j]):
                            break
                        section_lines.append(lines[j])
                        j += 1

                    # Generate filename
                    slug = re.sub(r'[^\w\s-]', '', heading_name.lower())
                    slug = re.sub(r'\s+', '_', slug).strip('_')[:50]
                    ext_filename = f"{target_stem}_{slug}.md" if slug else f"{target_stem}_section_{len(extracted_files)+1}.md"
                    ext_rel = os.path.join(target_dir, ext_filename) if target_dir else ext_filename
                    ext_path = root / ext_rel

                    # Write extracted file with ## Related back-link
                    section_content = "\n".join(section_lines)
                    related_block = f"\n\n## Related\n\n- [{target_stem}]({os.path.basename(target)}) — Parent document\n"
                    ext_path.parent.mkdir(parents=True, exist_ok=True)
                    ext_path.write_text(section_content + related_block, encoding="utf-8")

                    extracted_files.append({
                        "filename": ext_rel,
                        "heading": heading_name,
                        "lines": len(section_lines),
                    })

                    # Replace in original with link
                    link_line = f"See [{heading_name}]({ext_filename}) for details."
                    remaining_lines.append("")
                    remaining_lines.append(link_line)
                    remaining_lines.append("")
                    link_insertions.append(link_line)

                    i = j
                    continue

            remaining_lines.append(line)
            i += 1

        if not extracted_files:
            return {
                "target": target,
                "original_lines": original_lines,
                "new_lines": original_lines,
                "extracted": [],
                "message": f"No matching sections found for: {sections_to_extract}",
                "warnings": warnings,
            }

        # Write shrunk original
        target_path.write_text("\n".join(remaining_lines) + "\n", encoding="utf-8")

        # Generate _INDEX.md for the directory if multiple files now exist
        dir_path = root / target_dir if target_dir else root
        md_in_dir = [f for f in dir_path.iterdir() if f.suffix == ".md" and f.name != "_INDEX.md"]
        index_file = None
        if len(md_in_dir) > 3:
            idx_lines = [f"# {os.path.basename(target_dir or '.').replace('_',' ').title()}\n", ""]
            for f in sorted(md_in_dir):
                idx_lines.append(f"- [{f.stem.replace('_',' ').title()}]({f.name})")
            idx_content = "\n".join(idx_lines) + "\n"
            idx_path = dir_path / "_INDEX.md"
            idx_path.write_text(idx_content, encoding="utf-8")
            index_file = os.path.relpath(idx_path, root)

        # Collect all new files for result
        all_new = [e["filename"] for e in extracted_files]
        if index_file:
            all_new.append(index_file)

        return {
            "target": target,
            "original_lines": original_lines,
            "new_lines": len(remaining_lines),
            "extracted": extracted_files,
            "new_files": all_new,
            "index_file": index_file,
            "warnings": warnings,
        }
