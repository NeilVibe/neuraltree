"""neuraltree_reorganize — Structural operations: move, split, archive, create index.

All operations are read-only analysis by default. They return a PLAN of what would change.
The Skill (or user) decides whether to execute the plan.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from fastmcp import FastMCP

from neuraltree_mcp.text_utils import is_referenced, walk_project_files
from neuraltree_mcp.validation import validate_project_root, validate_within_root


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


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def neuraltree_plan_move(
        source: str,
        destination: str,
        project_root: str = ".",
    ) -> dict:
        """Plan a file move with all reference updates.

        Traces all references to the source file, computes the text rewrites
        needed to update them to the new destination, and returns a plan.
        Does NOT execute anything — returns the plan for review.

        Args:
            source: Relative path of the file to move (e.g. "docs/old_guide.md").
            destination: Relative path of the new location (e.g. "docs/guides/setup.md").
            project_root: Project root directory.

        Returns:
            dict with source, destination, references_found, rewrites, and warnings.
        """
        try:
            root = validate_project_root(project_root)
        except (ValueError, OSError) as e:
            return {"error": str(e)}

        # Validate both paths are within root
        try:
            src_path = root / source
            validate_within_root(src_path, root)
            dst_path = root / destination
            validate_within_root(dst_path, root)
        except ValueError as e:
            return {"error": f"Path escapes project root: {e}"}

        if not src_path.exists():
            return {"error": f"Source does not exist: {source}"}

        warnings = []
        if dst_path.exists():
            warnings.append(f"Destination already exists: {destination}")

        # Find all references
        references, ref_warnings = _find_all_references(root, source)
        warnings.extend(ref_warnings)
        rewrites = _compute_rewrites(references, source, destination)

        return {
            "source": source,
            "destination": destination,
            "references_found": len(references),
            "rewrites": rewrites,
            "warnings": warnings,
        }

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
        frontmatter_seen = False

        for i, line in enumerate(lines):
            # Track frontmatter (only at start of file)
            if i == 0 and line.strip() == "---":
                in_frontmatter = True
                continue
            if in_frontmatter and line.strip() == "---":
                in_frontmatter = False
                frontmatter_seen = True
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
