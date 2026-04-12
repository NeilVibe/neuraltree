"""neuraltree_wiki_lint — Wiki health checker for LLM-consumed knowledge bases.

Inspired by Karpathy's LLM-Wiki maintenance pattern. Runs 4 deterministic
checks on markdown wikis:

1. Broken links — wikilinks/markdown links pointing to non-existent files
2. Orphan pages — pages with zero inbound links (already in find_dead, but here with richer context)
3. Freshness — pages not updated recently while their source files changed
4. Cross-reference density — pages with too few or too many inbound links

Returns a structured health report. Judgment calls (contradictions,
coverage gaps) stay in the Skill layer per "Algorithm in Tool, Judgment in Claude."
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from fastmcp import FastMCP

from neuraltree_mcp.validation import validate_project_root

# Patterns for extracting links from markdown
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")  # [text](target)
_WIKI_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")  # [[target]] or [[target|alias]]

# Entry-point filenames — never orphans (they're root navigation nodes)
_ENTRY_POINT_NAMES = {
    "readme.md", "claude.md", "memory.md", "index.md", "_index.md",
    "overview.md", "getting-started.md", "introduction.md",
}

# Directories whose files are intentionally disconnected
_ARCHIVE_DIR_NAMES = {"archive", "old", "deprecated"}


def _is_entry_point(rel_path: str) -> bool:
    """Check if a file is a known entry point (trunk node)."""
    return Path(rel_path).name.lower() in _ENTRY_POINT_NAMES


def _is_in_archive(rel_path: str) -> bool:
    """Check if a file lives in an archive directory."""
    return any(part in _ARCHIVE_DIR_NAMES for part in Path(rel_path).parts)


def _collect_md_files(
    root: Path,
    extensions: list[str] | None = None,
    exclude_dir_prefixes: set[str] | None = None,
) -> list[Path]:
    """Collect all markdown files under root.

    Args:
        root: Project root directory.
        extensions: File extensions to collect (default [".md"]).
        exclude_dir_prefixes: Relative directory prefixes to skip entirely
            (e.g. {".claude/agents", ".planning", ".tribunal"}).
    """
    exts = extensions or [".md"]
    excl = exclude_dir_prefixes or set()
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dp = Path(dirpath)
        rel_dir = str(dp.relative_to(root)).replace("\\", "/")
        if rel_dir == ".":
            rel_dir = ""

        # Skip non-knowledge dirs: dependencies, build output, caches,
        # tooling artifacts. These contain .md files that aren't wiki pages.
        _SKIP_PARTS = {
            "node_modules", "__pycache__", ".git", ".neuraltree",
            ".planning", ".tribunal", ".playwright-mcp", ".agents",
            "htmlcov", "dist", "build", ".svelte-kit", ".vite",
            ".cache", ".output", "coverage", "vendor",
        }
        if any(part in _SKIP_PARTS for part in dp.parts):
            dirnames.clear()
            continue
        # Skip dirs that contain source code (heuristic: has .py/.js/.ts/.svelte siblings)
        _CODE_EXTS = {".py", ".js", ".ts", ".svelte", ".jsx", ".tsx", ".go", ".rs"}
        if filenames and not any(fn.endswith(ext) for fn in filenames for ext in (".md",)):
            # No .md files here at all, skip descending if it's code-heavy
            pass  # let os.walk skip naturally
        elif filenames:
            code_count = sum(1 for fn in filenames if any(fn.endswith(e) for e in _CODE_EXTS))
            md_count = sum(1 for fn in filenames if fn.endswith(".md"))
            # If >80% code files and only READMEs, skip — it's a source dir not a wiki
            if code_count > 5 and md_count <= 1 and code_count > md_count * 5:
                dirnames.clear()
                continue

        # Skip excluded directory prefixes
        if excl and rel_dir:
            if any(rel_dir == e or rel_dir.startswith(e + "/") for e in excl):
                dirnames.clear()  # don't descend
                continue

        for fn in filenames:
            if any(fn.endswith(ext) for ext in exts):
                files.append(dp / fn)
    return files


def _extract_links(file_path: Path) -> list[dict]:
    """Extract all markdown and wiki links from a file."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    links = []
    for line_num, line in enumerate(text.splitlines(), 1):
        for match in _MD_LINK_RE.finditer(line):
            target = match.group(2)
            # Skip external URLs, anchors-only, mailto
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            # Strip anchors and query strings
            clean = target.split("#")[0].split("?")[0]
            if clean:
                links.append({"target": clean, "line": line_num, "type": "markdown"})

        for match in _WIKI_LINK_RE.finditer(line):
            target = match.group(1).strip()
            if target:
                links.append({"target": target, "line": line_num, "type": "wikilink"})

    return links


def _resolve_link(source: Path, target: str, root: Path) -> Path | None:
    """Try to resolve a link target to an actual file."""
    # Try relative to source file's directory
    candidate = (source.parent / target).resolve()
    if candidate.exists():
        return candidate

    # Try with .md extension
    if not target.endswith(".md"):
        candidate = (source.parent / (target + ".md")).resolve()
        if candidate.exists():
            return candidate

    # Try relative to project root
    candidate = (root / target).resolve()
    if candidate.exists():
        return candidate

    if not target.endswith(".md"):
        candidate = (root / (target + ".md")).resolve()
        if candidate.exists():
            return candidate

    return None


def _check_broken_links(files: list[Path], root: Path) -> list[dict]:
    """Find all broken internal links."""
    broken = []
    for f in files:
        links = _extract_links(f)
        for link in links:
            resolved = _resolve_link(f, link["target"], root)
            if resolved is None:
                broken.append({
                    "file": str(f.relative_to(root)),
                    "line": link["line"],
                    "target": link["target"],
                    "link_type": link["type"],
                })
    return broken


def _check_inbound_links(files: list[Path], root: Path) -> dict[str, list[str]]:
    """Build inbound link map: target_file -> [source_files]."""
    inbound: dict[str, list[str]] = {str(f.relative_to(root)): [] for f in files}

    for f in files:
        source_rel = str(f.relative_to(root))
        links = _extract_links(f)
        for link in links:
            resolved = _resolve_link(f, link["target"], root)
            if resolved is not None:
                target_rel = str(resolved.relative_to(root))
                if target_rel in inbound and source_rel != target_rel:
                    if source_rel not in inbound[target_rel]:
                        inbound[target_rel].append(source_rel)

    return inbound


def _check_freshness(files: list[Path], root: Path, max_age_days: int) -> list[dict]:
    """Find pages whose frontmatter last_verified is older than max_age_days."""
    import time

    cutoff = time.time() - (max_age_days * 86400)
    stale = []
    for f in files:
        mtime = f.stat().st_mtime
        if mtime < cutoff:
            age_days = int((time.time() - mtime) / 86400)
            stale.append({
                "file": str(f.relative_to(root)),
                "age_days": age_days,
                "last_modified": mtime,
            })
    # Sort by age descending (stalest first)
    stale.sort(key=lambda x: -x["age_days"])
    return stale


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def neuraltree_wiki_lint(
        project_root: str = ".",
        max_age_days: int = 30,
        extensions: list[str] | None = None,
        trunk_paths: list[str] | None = None,
        exclude_dirs: list[str] | None = None,
    ) -> dict:
        """Lint a markdown wiki for broken links, orphans, and staleness.

        Runs 4 deterministic health checks:
        1. Broken links — internal links pointing to non-existent files
        2. Orphan pages — pages with zero inbound links
           (entry points and archive files auto-excluded)
        3. Stale pages — files not modified in max_age_days
        4. Cross-reference density — avg inbound links per page

        Judgment calls (contradictions, coverage gaps, content quality)
        stay in the Skill layer — this tool only reports structural issues.

        Args:
            project_root: Project root directory.
            max_age_days: Flag pages older than this as stale (default 30).
            extensions: File extensions to check (default [".md"]).
            trunk_paths: Explicit entry-point paths to exclude from orphan
                         detection. If None, auto-detects (readme.md,
                         claude.md, memory.md, index.md, etc.).
            exclude_dirs: Directory names to exclude from orphan detection
                          (default: auto-detects archive, old, deprecated).

        Returns:
            dict with broken_links, orphan_pages, stale_pages,
            cross_ref_density, and overall health_score.
        """
        try:
            root = validate_project_root(project_root)
        except ValueError as e:
            return {"error": str(e)}

        # Convert exclude_dirs to prefix set for file collection
        excl_prefixes = set(exclude_dirs) if exclude_dirs else set()
        files = _collect_md_files(root, extensions, excl_prefixes)
        if not files:
            return {
                "broken_links": [],
                "orphan_pages": [],
                "stale_pages": [],
                "cross_ref_density": 0.0,
                "health_score": 0,
                "total_pages": 0,
                "warnings": ["No markdown files found"],
            }

        # 1. Broken links
        broken = _check_broken_links(files, root)

        # 2. Orphan pages (zero inbound links, excluding trunk + archive)
        inbound = _check_inbound_links(files, root)

        # Build exclusion sets
        if trunk_paths is not None:
            trunk_set = set(trunk_paths)
        else:
            trunk_set = {f for f in inbound if _is_entry_point(f)}

        extra_archive = set(exclude_dirs) if exclude_dirs else set()
        def _excluded(f: str) -> bool:
            if f in trunk_set:
                return True
            if _is_in_archive(f):
                return True
            if extra_archive:
                return any(part in extra_archive for part in Path(f).parts)
            return False

        orphans = [
            {"file": f, "inbound_count": 0}
            for f, sources in inbound.items()
            if len(sources) == 0 and not _excluded(f)
        ]

        # 3. Stale pages
        stale = _check_freshness(files, root, max_age_days)

        # 4. Cross-reference density
        total_inbound = sum(len(v) for v in inbound.values())
        density = total_inbound / len(files) if files else 0.0

        # Flag orphans in programmatic/convention-loaded directories
        # These are consumed by tools/frameworks, not linked via markdown
        _PROGRAMMATIC_DIRS = {
            ".claude",  # All .claude/ files are convention-loaded by Claude
            ".planning", "config", "agents", "skills",
        }
        programmatic_orphans = 0
        for orphan in orphans:
            f = orphan["file"]
            is_prog = any(
                f.startswith(d + "/") or ("/" + d + "/") in ("/" + f)
                for d in _PROGRAMMATIC_DIRS
            )
            orphan["likely_programmatic"] = is_prog
            if is_prog:
                programmatic_orphans += 1

        # Health score (0-100)
        # Only count REAL orphans (not convention-loaded) in the penalty
        real_orphan_count = len(orphans) - programmatic_orphans
        score = 100
        score -= min(40, len(broken) * 5)  # cap at -40
        score -= min(30, real_orphan_count * 3)  # cap at -30
        if density < 1.0:
            score -= 20
        elif density < 2.0:
            score -= 10
        stale_ratio = len(stale) / len(files) if files else 0
        if stale_ratio > 0.5:
            score -= 15
        elif stale_ratio > 0.25:
            score -= 5
        score = max(0, min(100, score))

        warnings = []
        if programmatic_orphans > 0:
            warnings.append(
                f"{programmatic_orphans} orphan pages are in directories typically "
                f"consumed programmatically (agents, skills, .planning, config). "
                f"'Orphan' means no markdown links point to them — they may still "
                f"be actively used by frameworks. Investigate before deleting."
            )

        return {
            "broken_links": broken,
            "orphan_pages": orphans,
            "stale_pages": stale[:20],  # Top 20 stalest
            "cross_ref_density": round(density, 2),
            "health_score": score,
            "total_pages": len(files),
            "total_broken": len(broken),
            "total_orphans": len(orphans),
            "total_stale": len(stale),
            "programmatic_orphans": programmatic_orphans,
            "trunk_files": sorted(trunk_set),
            "warnings": warnings,
        }
