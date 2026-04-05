"""neuraltree_wire — Auto-generate ## Related and ## Docs for leaf files."""
from __future__ import annotations

import os
from pathlib import Path

from fastmcp import FastMCP

from neuraltree_mcp.text_utils import extract_keywords, jaccard, extract_backtick_paths, walk_project_files
from neuraltree_mcp.validation import validate_project_root, validate_within_root


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def neuraltree_wire(file_path: str, project_root: str = ".", all_leaf_paths: list[str] | None = None) -> dict:
        """Auto-generate ## Related and ## Docs suggestions for a leaf file.

        Uses keyword extraction + Jaccard similarity to find related files.
        Extracts backtick paths and grep results for ## Docs candidates.

        Args:
            file_path: The leaf file to wire (relative to project_root).
            project_root: Project root directory.
            all_leaf_paths: Optional list of all leaf paths to compare against.
                           If None, auto-discovers .md files.

        Returns:
            dict with related (scored candidates), docs (code references),
            suggested_content, and warnings.
        """
        try:
            root = validate_project_root(project_root)
        except (ValueError, OSError) as e:
            return {"error": str(e)}
        target = root / file_path

        try:
            validate_within_root(target, root)
        except ValueError:
            return {"error": f"Path escapes project root: {file_path}"}

        if not target.exists():
            return {"error": f"File not found: {file_path}"}

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return {"error": f"Cannot read {file_path}: {e}"}

        target_keywords = extract_keywords(content)
        warnings: list[str] = []

        # Discover leaf files if not provided
        if all_leaf_paths:
            leaves = [root / p for p in all_leaf_paths]
        else:
            leaves = walk_project_files(root, {".md"})

        target_resolved = target.resolve()
        target_dir = target.parent

        # Compute related candidates
        candidates: list[dict] = []
        for leaf in leaves:
            if not leaf.exists() or leaf.resolve() == target_resolved:
                continue
            try:
                leaf_content = leaf.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                warnings.append(f"Could not read {os.path.relpath(leaf, root)}: {e}")
                continue

            leaf_keywords = extract_keywords(leaf_content)
            score = jaccard(target_keywords, leaf_keywords)

            # Boost: shared ## Docs targets
            target_docs = set(extract_backtick_paths(content))
            leaf_docs = set(extract_backtick_paths(leaf_content))
            if target_docs & leaf_docs:
                score += 0.1

            # Boost: same parent directory
            if leaf.parent == target_dir:
                score += 0.05

            # Cap score at 1.0
            score = min(1.0, score)

            if score > 0.15:
                rel_leaf = os.path.relpath(leaf, root)
                shared = target_keywords & leaf_keywords
                reason = f"shared keywords: {', '.join(sorted(shared)[:5])}" if shared else "structural proximity"
                candidates.append({
                    "file": rel_leaf,
                    "score": round(score, 3),
                    "reason": reason,
                })

        # Sort by score descending, take top 3
        candidates.sort(key=lambda c: c["score"], reverse=True)
        related = candidates[:3]

        # Extract docs (backtick paths referenced BY this file = outbound)
        docs = []
        for bp in extract_backtick_paths(content):
            docs.append({"file": bp, "direction": "references"})

        # Build suggested markdown
        lines = []
        if related:
            lines.append("## Related")
            for r in related:
                lines.append(f"- [{Path(r['file']).name}]({r['file']}) — {r['reason']}")
        if docs:
            lines.append("\n## Docs")
            for d in docs:
                lines.append(f"- `{d['file']}` — {d['direction']}")

        return {
            "related": related,
            "docs": docs,
            "suggested_content": "\n".join(lines) if lines else "(no suggestions)",
            "warnings": warnings,
        }
