"""neuraltree_diagnose — Classify query failures by gap type."""
from __future__ import annotations

import os
import re
from pathlib import Path

from fastmcp import FastMCP

from neuraltree_mcp.text_utils import extract_keywords, walk_project_files
from neuraltree_mcp.validation import validate_project_root

# Gap types — universal, no formatting conventions
GAP_TYPES = {
    "CONTENT_GAP": "No file covers this topic",
    "EMBEDDING_GAP": "File exists but Viking can't find it",
    "ISOLATION_GAP": "File exists but has no connections in the knowledge graph",
    "FOCUS_GAP": "Answer buried in oversized file (needs splitting)",
}

_TEXT_EXTENSIONS = {".md", ".txt"}


def _viking_uri_matches_file(vuri: str, local_rel_path: str) -> bool:
    """Check if a Viking URI refers to a local file, using segment matching.

    Viking URIs look like:
      viking://resources/newfin/docs/GUIDE.md/Section_Title/chunk_hash.md
    We check if the local filename appears as an exact path segment,
    not just a substring (avoids GUIDE.md matching DEBUGGING_GUIDE.md).
    """
    uri_segments = vuri.split("/")
    basename = os.path.basename(local_rel_path)
    if basename in uri_segments:
        return True
    rel_segments = local_rel_path.split("/")
    for i in range(len(uri_segments) - len(rel_segments) + 1):
        if uri_segments[i:i + len(rel_segments)] == rel_segments:
            return True
    return False


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
        - ISOLATION_GAP: File exists but has no edges in the knowledge graph.
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
        except (ValueError, OSError) as e:
            return {"diagnoses": [], "gap_counts": {g: 0 for g in GAP_TYPES},
                    "fix_priority": [], "total_failures": 0, "warnings": [], "error": str(e)}
        all_files = walk_project_files(root, _TEXT_EXTENSIONS)

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
                rel = os.path.relpath(f, root)
                warnings.append(f"Could not read {rel}: {e}")

        # Build viking results lookup
        viking_lookup: dict[str, list[str]] = {}
        if viking_results:
            for vr in viking_results:
                key = vr.get("query", "").strip().lower()
                viking_lookup[key] = vr.get("results", [])

        # Load knowledge map edges for isolation detection
        km_edges: set[str] = set()
        km_path = root / ".neuraltree" / "knowledge_map.json"
        if km_path.exists():
            try:
                import json
                km = json.loads(km_path.read_text(encoding="utf-8"))
                for edge in km.get("edges", []):
                    km_edges.add(edge.get("source", ""))
                    km_edges.add(edge.get("target", ""))
            except (json.JSONDecodeError, OSError):
                warnings.append("Could not load knowledge map for isolation detection")

        diagnoses: list[dict] = []
        gap_counts: dict[str, int] = {g: 0 for g in GAP_TYPES}

        for fq in failed_queries:
            query_text = fq.get("text", "")
            if not query_text:
                warnings.append(f"Skipping query with empty text: {fq}")
                continue
            hint = fq.get("expected_topic", "")

            keywords = extract_keywords(query_text + " " + hint, min_freq=1)

            scored_matches: list[tuple[int, str]] = []
            for rel, content in file_contents.items():
                content_lower = content.lower()
                matched = sum(1 for kw in keywords if kw in content_lower)
                if matched >= max(1, len(keywords) // 2):
                    scored_matches.append((matched, rel))
            scored_matches.sort(key=lambda x: x[0], reverse=True)
            matching_files = [rel for _, rel in scored_matches]

            if not matching_files:
                gap_type = "CONTENT_GAP"
                fix = f"Create a new file covering: {query_text}"
            else:
                best_match = matching_files[0]
                best_size = file_sizes.get(best_match, 0)

                # Check if Viking found a matching file
                viking_found = viking_lookup.get(query_text.strip().lower(), [])
                viking_has_match = False
                for vuri in viking_found:
                    for mf in matching_files:
                        if _viking_uri_matches_file(vuri, mf):
                            viking_has_match = True
                            break
                    if viking_has_match:
                        break

                # Check if file is connected in knowledge graph
                is_isolated = best_match not in km_edges if km_edges else False

                if viking_has_match:
                    if best_size > 500:
                        gap_type = "FOCUS_GAP"
                        fix = f"Split {best_match} ({best_size} lines) into focused files"
                    elif is_isolated:
                        gap_type = "ISOLATION_GAP"
                        fix = f"Connect {best_match} to related files in the knowledge graph"
                    else:
                        gap_type = "CONTENT_GAP"
                        fix = f"Improve content in {best_match} for: {query_text}"
                else:
                    if viking_results is not None:
                        if best_size > 500:
                            gap_type = "FOCUS_GAP"
                            fix = f"Split {best_match} ({best_size} lines) — too large for effective indexing"
                        else:
                            gap_type = "EMBEDDING_GAP"
                            fix = f"Re-index {best_match} in Viking"
                    else:
                        if is_isolated:
                            gap_type = "ISOLATION_GAP"
                            fix = f"Connect {best_match} to related files"
                        elif best_size > 500:
                            gap_type = "FOCUS_GAP"
                            fix = f"Split {best_match} ({best_size} lines)"
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

        # Priority: cheapest fix first
        priority_order = ["ISOLATION_GAP", "EMBEDDING_GAP", "FOCUS_GAP", "CONTENT_GAP"]
        fix_priority = []
        for gt in priority_order:
            for d in diagnoses:
                if d["gap_type"] == gt:
                    fix_priority.append(d)

        return {
            "diagnoses": diagnoses,
            "gap_counts": gap_counts,
            "fix_priority": fix_priority,
            "total_failures": len(diagnoses),
            "warnings": warnings,
        }
