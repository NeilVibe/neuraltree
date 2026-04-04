"""neuraltree_diagnose — Classify query failures by gap type."""
from __future__ import annotations

import os
import re
from pathlib import Path

from fastmcp import FastMCP

from neuraltree_mcp.text_utils import extract_keywords, walk_project_files
from neuraltree_mcp.validation import validate_project_root

# Gap types from the spec
GAP_TYPES = {
    "CONTENT_GAP": "No file covers this topic",
    "EMBEDDING_GAP": "File exists but Viking can't find it",
    "SYNAPSE_GAP": "File exists, no cross-refs lead to it",
    "FRESHNESS_GAP": "File exists but content is stale/wrong",
    "FOCUS_GAP": "Answer buried in 500+ line file (needs splitting)",
}


_TEXT_EXTENSIONS = {".md", ".py", ".js", ".ts", ".yml", ".yaml", ".json", ".txt", ".sh"}


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def neuraltree_diagnose(
        failed_queries: list[dict],
        project_root: str = ".",
        viking_results: list[dict] | None = None,
    ) -> dict:
        """Classify query failures by gap type.

        For each failed query, determines WHY it failed:
        - CONTENT_GAP: No file in the project covers the topic at all.
        - EMBEDDING_GAP: A file exists with the content but Viking didn't return it.
        - SYNAPSE_GAP: File exists but has no ## Related or ## Docs pointing to it.
        - FRESHNESS_GAP: File exists but last_verified is stale (>30 days).
        - FOCUS_GAP: Relevant content buried in a file >500 lines.

        Args:
            failed_queries: List of {"text": "query", "expected_topic": "optional hint"}.
            project_root: Project root directory.
            viking_results: Optional Viking search results for each query,
                           as [{"query": "...", "results": ["file1", "file2"]}].

        Returns:
            dict with diagnoses (per query), summary counts, and fix_priority.
        """
        try:
            root = validate_project_root(project_root)
        except ValueError as e:
            return {"diagnoses": [], "gap_counts": {g: 0 for g in GAP_TYPES},
                    "fix_priority": [], "total_failures": 0, "warnings": [], "error": str(e)}
        all_files = walk_project_files(root, _TEXT_EXTENSIONS)

        # Build a simple content index for keyword matching
        file_contents: dict[str, str] = {}
        file_sizes: dict[str, int] = {}
        warnings: list[str] = []
        for f in all_files:
            try:
                rel = os.path.relpath(f, root)
                content = f.read_text(encoding="utf-8", errors="replace")
                file_contents[rel] = content
                file_sizes[rel] = len(content.splitlines())
            except OSError as e:
                warnings.append(f"Could not read {f}: {e}")

        # Build viking results lookup
        viking_lookup: dict[str, list[str]] = {}
        if viking_results:
            for vr in viking_results:
                viking_lookup[vr["query"]] = vr.get("results", [])

        diagnoses: list[dict] = []
        gap_counts: dict[str, int] = {g: 0 for g in GAP_TYPES}

        for fq in failed_queries:
            query_text = fq.get("text", "")
            hint = fq.get("expected_topic", "")

            # Extract search keywords from query + hint
            keywords = extract_keywords(query_text + " " + hint, min_freq=1)

            # Find files that match keywords
            matching_files = []
            for rel, content in file_contents.items():
                content_lower = content.lower()
                matched = sum(1 for kw in keywords if kw in content_lower)
                if matched >= max(1, len(keywords) // 2):
                    matching_files.append(rel)

            # Determine gap type
            if not matching_files:
                gap_type = "CONTENT_GAP"
                fix = f"Create a new file covering: {query_text}"
            else:
                # Check if Viking found these files
                viking_found = viking_lookup.get(query_text, [])
                viking_found_set = {os.path.basename(v) for v in viking_found}
                matching_basenames = {os.path.basename(m) for m in matching_files}

                if viking_found_set & matching_basenames:
                    # Viking found it but it wasn't relevant enough
                    # Check if it's a freshness or focus issue
                    best_match = matching_files[0]
                    if file_sizes.get(best_match, 0) > 500:
                        gap_type = "FOCUS_GAP"
                        fix = f"Split {best_match} ({file_sizes[best_match]} lines) into focused leaves"
                    else:
                        # Check freshness
                        content = file_contents.get(best_match, "")
                        date_match = re.search(r'last_verified:\s*(\d{4}-\d{2}-\d{2})', content)
                        if date_match:
                            gap_type = "FRESHNESS_GAP"
                            fix = f"Update {best_match} (last verified: {date_match.group(1)})"
                        else:
                            gap_type = "SYNAPSE_GAP"
                            fix = f"Add ## Related/## Docs to {best_match}"
                else:
                    # File exists but Viking didn't find it
                    if viking_results is not None:
                        gap_type = "EMBEDDING_GAP"
                        fix = f"Re-index {matching_files[0]} in Viking"
                    else:
                        # No Viking data — check for synapse issues
                        best_match = matching_files[0]
                        content = file_contents.get(best_match, "")
                        has_related = "## Related" in content
                        has_docs = "## Docs" in content

                        if not has_related and not has_docs:
                            gap_type = "SYNAPSE_GAP"
                            fix = f"Wire {best_match} with ## Related and ## Docs"
                        elif file_sizes.get(best_match, 0) > 500:
                            gap_type = "FOCUS_GAP"
                            fix = f"Split {best_match} ({file_sizes[best_match]} lines)"
                        else:
                            gap_type = "CONTENT_GAP"
                            fix = f"Improve content in {best_match} for: {query_text}"

            gap_counts[gap_type] += 1
            diagnoses.append({
                "query": query_text,
                "gap_type": gap_type,
                "matching_files": matching_files[:3],
                "fix": fix,
            })

        # Priority: SYNAPSE > FOCUS > EMBEDDING > FRESHNESS > CONTENT
        # (cheapest fixes first)
        priority_order = ["SYNAPSE_GAP", "FOCUS_GAP", "EMBEDDING_GAP", "FRESHNESS_GAP", "CONTENT_GAP"]
        fix_priority = []
        for gap_type in priority_order:
            for d in diagnoses:
                if d["gap_type"] == gap_type:
                    fix_priority.append(d)

        return {
            "diagnoses": diagnoses,
            "gap_counts": gap_counts,
            "fix_priority": fix_priority,
            "total_failures": len(failed_queries),
            "warnings": warnings,
        }
