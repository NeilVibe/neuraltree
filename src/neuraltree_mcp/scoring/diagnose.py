"""neuraltree_diagnose — Classify query failures by gap type."""
from __future__ import annotations

import os
import re
from datetime import date, timedelta
from pathlib import Path

from fastmcp import FastMCP

from neuraltree_mcp.text_utils import extract_keywords, walk_project_files
from neuraltree_mcp.validation import validate_project_root

# Gap types from the spec
GAP_TYPES = {
    "CONTENT_GAP": "No file covers this topic",
    "EMBEDDING_GAP": "File exists but Viking can't find it",
    "SYNAPSE_GAP": "File exists, no cross-refs lead to it",
    "FRESHNESS_GAP": "File exists but content is stale (>30 days or no date)",
    "FOCUS_GAP": "Answer buried in 500+ line file (needs splitting)",
}

# Only search documentation files for gap classification.
# Source code (.py, .js, etc.) produces noise — generic words match everything.
_TEXT_EXTENSIONS = {".md", ".txt"}
_STALE_DAYS = 30


def _viking_uri_matches_file(vuri: str, local_rel_path: str) -> bool:
    """Check if a Viking URI refers to a local file, using segment matching.

    Viking URIs look like:
      viking://resources/newfin/docs/GUIDE.md/Section_Title/chunk_hash.md
    We check if the local filename appears as an exact path segment,
    not just a substring (avoids GUIDE.md matching DEBUGGING_GUIDE.md).
    """
    uri_segments = vuri.split("/")
    basename = os.path.basename(local_rel_path)
    # Exact segment match for basename
    if basename in uri_segments:
        return True
    # Full relative path as consecutive segments match
    # e.g. "docs/GUIDE.md" should match ".../docs/GUIDE.md/..." but not ".../docs/DEBUGGING_GUIDE.md/..."
    rel_segments = local_rel_path.split("/")
    for i in range(len(uri_segments) - len(rel_segments) + 1):
        if uri_segments[i:i + len(rel_segments)] == rel_segments:
            return True
    return False


def _is_stale(content: str) -> tuple[bool, str | None]:
    """Check if content has a stale or missing last_verified date.

    Returns (is_stale, date_string_or_none).
    """
    date_match = re.search(r'last_verified:\s*(\d{4}-\d{2}-\d{2})', content)
    if not date_match:
        return True, None  # No date = treat as stale
    try:
        verified = date.fromisoformat(date_match.group(1))
        days_old = (date.today() - verified).days
        return days_old > _STALE_DAYS, date_match.group(1)
    except ValueError:
        return True, date_match.group(1)  # Invalid date = stale


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
        - FRESHNESS_GAP: File exists but last_verified is stale (>30 days) or missing.
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
                rel = os.path.relpath(f, root)
                warnings.append(f"Could not read {rel}: {e}")

        # Build viking results lookup (case-insensitive keys)
        viking_lookup: dict[str, list[str]] = {}
        if viking_results:
            for vr in viking_results:
                key = vr.get("query", "").strip().lower()
                viking_lookup[key] = vr.get("results", [])

        diagnoses: list[dict] = []
        gap_counts: dict[str, int] = {g: 0 for g in GAP_TYPES}

        for fq in failed_queries:
            query_text = fq.get("text", "")
            if not query_text:
                warnings.append(f"Skipping query with empty text: {fq}")
                continue
            hint = fq.get("expected_topic", "")

            # Extract search keywords from query + hint
            keywords = extract_keywords(query_text + " " + hint, min_freq=1)

            # Find files that match keywords, scored by match count
            scored_matches: list[tuple[int, str]] = []
            for rel, content in file_contents.items():
                content_lower = content.lower()
                matched = sum(1 for kw in keywords if kw in content_lower)
                if matched >= max(1, len(keywords) // 2):
                    scored_matches.append((matched, rel))
            scored_matches.sort(key=lambda x: x[0], reverse=True)
            matching_files = [rel for _, rel in scored_matches]

            # Determine gap type
            if not matching_files:
                gap_type = "CONTENT_GAP"
                fix = f"Create a new file covering: {query_text}"
            else:
                best_match = matching_files[0]
                best_content = file_contents.get(best_match, "")
                best_size = file_sizes.get(best_match, 0)

                # Check if Viking found a file matching any local match (segment-based)
                viking_found = viking_lookup.get(query_text.strip().lower(), [])
                viking_has_match = False
                for vuri in viking_found:
                    for mf in matching_files:
                        if _viking_uri_matches_file(vuri, mf):
                            viking_has_match = True
                            break
                    if viking_has_match:
                        break

                # Structural properties of best match
                has_related = "## Related" in best_content
                has_docs = "## Docs" in best_content
                stale, verified_date = _is_stale(best_content)

                if viking_has_match:
                    # Viking found it — problem is structural, not indexing
                    if best_size > 500:
                        gap_type = "FOCUS_GAP"
                        fix = f"Split {best_match} ({best_size} lines) into focused leaves"
                    elif not has_related and not has_docs:
                        gap_type = "SYNAPSE_GAP"
                        fix = f"Add ## Related/## Docs to {best_match}"
                    elif stale:
                        gap_type = "FRESHNESS_GAP"
                        if verified_date:
                            fix = f"Update {best_match} (last verified: {verified_date})"
                        else:
                            fix = f"Add last_verified frontmatter to {best_match}"
                    else:
                        # Well-wired, fresh, <500 lines, but still failed query
                        # Content exists but doesn't answer the specific question well
                        gap_type = "CONTENT_GAP"
                        fix = f"Improve content in {best_match} for: {query_text}"
                else:
                    # Viking didn't find it — check why
                    if viking_results is not None:
                        # Viking was available but missed this file
                        if best_size > 500:
                            gap_type = "FOCUS_GAP"
                            fix = f"Split {best_match} ({best_size} lines) — too large for effective indexing"
                        elif not has_related and not has_docs:
                            gap_type = "EMBEDDING_GAP"
                            fix = f"Re-index {best_match} in Viking + add ## Related"
                        else:
                            gap_type = "EMBEDDING_GAP"
                            fix = f"Re-index {best_match} in Viking"
                    else:
                        # No Viking data available
                        if not has_related and not has_docs:
                            gap_type = "SYNAPSE_GAP"
                            fix = f"Wire {best_match} with ## Related and ## Docs"
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

        # Priority order: cheapest/quickest fix first
        # SYNAPSE (add links) > FRESHNESS (update date) > EMBEDDING (re-index) > FOCUS (split) > CONTENT (create)
        priority_order = ["SYNAPSE_GAP", "FRESHNESS_GAP", "EMBEDDING_GAP", "FOCUS_GAP", "CONTENT_GAP"]
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
