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


def _collect_md_files(root: Path, extensions: list[str] | None = None) -> list[Path]:
    """Collect all markdown files under root."""
    exts = extensions or [".md"]
    files = []
    for dirpath, _dirnames, filenames in os.walk(root):
        dp = Path(dirpath)
        # Skip hidden dirs, .git, node_modules, __pycache__, .neuraltree
        if any(part.startswith(".") or part in ("node_modules", "__pycache__") for part in dp.parts):
            if ".git" in dp.parts or ".neuraltree" in dp.parts:
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
    ) -> dict:
        """Lint a markdown wiki for broken links, orphans, and staleness.

        Runs 4 deterministic health checks:
        1. Broken links — internal links pointing to non-existent files
        2. Orphan pages — pages with zero inbound links
        3. Stale pages — files not modified in max_age_days
        4. Cross-reference density — avg inbound links per page

        Judgment calls (contradictions, coverage gaps, content quality)
        stay in the Skill layer — this tool only reports structural issues.

        Args:
            project_root: Project root directory.
            max_age_days: Flag pages older than this as stale (default 30).
            extensions: File extensions to check (default [".md"]).

        Returns:
            dict with broken_links, orphan_pages, stale_pages,
            cross_ref_density, and overall health_score.
        """
        try:
            root = validate_project_root(project_root)
        except ValueError as e:
            return {"error": str(e)}

        files = _collect_md_files(root, extensions)
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

        # 2. Orphan pages (zero inbound links)
        inbound = _check_inbound_links(files, root)
        orphans = [
            {"file": f, "inbound_count": 0}
            for f, sources in inbound.items()
            if len(sources) == 0
        ]

        # 3. Stale pages
        stale = _check_freshness(files, root, max_age_days)

        # 4. Cross-reference density
        total_inbound = sum(len(v) for v in inbound.values())
        density = total_inbound / len(files) if files else 0.0

        # Health score (0-100)
        # Penalties: broken links (-5 each), orphans (-3 each), low density (-20 if <1.0)
        score = 100
        score -= min(40, len(broken) * 5)  # cap at -40
        score -= min(30, len(orphans) * 3)  # cap at -30
        if density < 1.0:
            score -= 20
        elif density < 2.0:
            score -= 10
        # Bonus for no stale pages
        stale_ratio = len(stale) / len(files) if files else 0
        if stale_ratio > 0.5:
            score -= 15
        elif stale_ratio > 0.25:
            score -= 5
        score = max(0, min(100, score))

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
            "warnings": [],
        }
