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
        all_searchable = walk_project_files(root, _SEARCHABLE_EXTENSIONS)

        # Single pass: build structured reference set AND cache contents for word-boundary fallback
        referenced: set[str] = set()
        searchable_contents: dict[str, str] = {}
        warnings: list[str] = []
        for fpath in all_searchable:
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
                searchable_contents[os.path.relpath(fpath, root)] = content
                for line in content.splitlines():
                    # Extract markdown links (strip #fragment and ?query)
                    for m in re.finditer(r'\[.*?\]\(([^)]+)\)', line):
                        ref = m.group(1)
                        if not ref.startswith("http") and not ref.startswith("#"):
                            ref = _strip_ref_fragment(ref)
                            referenced.add(os.path.basename(ref))
                            referenced.add(ref)
                    # Extract backtick paths
                    for m in re.finditer(r'`([a-zA-Z0-9_./\-]+\.[a-zA-Z0-9]+)`', line):
                        path_ref = _strip_ref_fragment(m.group(1))
                        referenced.add(os.path.basename(path_ref))
                        referenced.add(path_ref)
            except OSError as e:
                warnings.append(f"Could not read {os.path.relpath(fpath, root)}: {e}")
                continue

        dead_files = []
        for fpath in all_knowledge:
            rel = os.path.relpath(fpath, root)
            basename = fpath.name

            # Skip trunk files — they're always "alive" by definition
            if basename in ("CLAUDE.md", "MEMORY.md", "_INDEX.md", "README.md"):
                continue

            # Check structured references first (fast set lookup), then word-boundary fallback
            if basename in referenced or rel in referenced:
                continue

            # Word-boundary fallback: catches plain-text mentions not in links/backticks
            # Uses same logic as score.py orphan detection (shared is_referenced helper)
            found_by_text = any(
                other_rel != rel and is_referenced(basename, rel, content)
                for other_rel, content in searchable_contents.items()
            )
            if found_by_text:
                continue

            # Dead — not found by any method
            try:
                size = len(fpath.read_text(encoding="utf-8", errors="replace").splitlines())
                mtime = os.path.getmtime(fpath)
            except OSError:
                size = -1  # -1 signals "unreadable" (not 0 which implies "empty")
                mtime = 0

            dead_files.append({
                "path": rel,
                "size_lines": size,
                "last_modified": mtime,
            })

        dead_files.sort(key=lambda x: x["size_lines"])

        # Exclude trunk files from denominator — they can never be dead,
        # so including them understates the dead ratio
        trunk_names = {"CLAUDE.md", "MEMORY.md", "_INDEX.md", "README.md"}
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
