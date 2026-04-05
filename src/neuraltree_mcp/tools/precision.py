"""neuraltree_precision — Viking search + content retrieval for Precision@3 scoring.

Wraps Viking (semantic search) into a single tool. Returns search results
with content previews for the orchestrating agent (Claude) to judge relevance.

For each query:
  1. Search Viking for top-K results
  2. Read full content of each result
  3. Return results with content — Claude judges relevance externally
"""
from __future__ import annotations

import os
from pathlib import Path

import requests
from fastmcp import FastMCP

from neuraltree_mcp.validation import validate_project_root

# Defaults — overridable per call
_DEFAULT_VIKING_URL = "http://localhost:1933"
_DEFAULT_LIMIT = 3
_CONNECT_TIMEOUT = 5
_READ_TIMEOUT = 30
_CONTENT_PREVIEW_CHARS = 3000  # ~50 lines for Claude to judge


def _check_viking(viking_url: str) -> bool:
    """Return True if Viking is reachable."""
    try:
        r = requests.get(f"{viking_url}/health", timeout=_CONNECT_TIMEOUT)
        return r.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False


def _viking_search(viking_url: str, query: str, limit: int) -> list[dict]:
    """Search Viking and return list of {uri, score, abstract}."""
    try:
        r = requests.post(
            f"{viking_url}/api/v1/search/search",
            json={"query": query, "limit": limit},
            timeout=_READ_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        resources = data.get("result", {}).get("resources", [])
        return [
            {
                "uri": res.get("uri", ""),
                "score": res.get("score", 0.0),
                "abstract": res.get("abstract", ""),
            }
            for res in resources
        ]
    except (requests.ConnectionError, requests.Timeout, ValueError, OSError):
        return []


def _viking_read(viking_url: str, uri: str) -> str:
    """Read full content from Viking resource. Returns first N chars."""
    try:
        r = requests.post(
            f"{viking_url}/api/v1/content/read",
            json={"uri": uri},
            timeout=_READ_TIMEOUT,
        )
        if r.status_code != 200:
            return ""
        data = r.json()
        content = data.get("result", {}).get("content", "")
        return content[:_CONTENT_PREVIEW_CHARS]
    except (requests.ConnectionError, requests.Timeout, ValueError, OSError):
        return ""


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def neuraltree_precision(
        queries: list[dict],
        project_root: str = ".",
        viking_url: str = _DEFAULT_VIKING_URL,
        limit: int = _DEFAULT_LIMIT,
    ) -> dict:
        """Search Viking for each query and return results with content for judging.

        For each query, searches Viking for top results and reads their content.
        Returns results with content previews — the orchestrating agent (Claude)
        judges relevance externally and computes precision_at_3.

        Args:
            queries: List of query dicts with at least {"text": "..."}.
                     Typically from neuraltree_generate_queries output.
            project_root: Project root (for validation).
            viking_url: Viking API base URL.
            limit: Number of Viking results per query (default 3).

        Returns:
            dict with per-query results (including content for judging),
            and service availability flag. Verdicts are "PENDING" —
            the caller (Claude) judges relevance and computes precision_at_3.
        """
        try:
            validate_project_root(project_root)
        except ValueError as e:
            return {"error": str(e)}

        # Check service availability
        viking_ok = _check_viking(viking_url)

        if not viking_ok:
            return {
                "precision_at_3": None,
                "query_results": [],
                "passed": 0,
                "failed": 0,
                "total": len(queries),
                "viking_available": False,
                "warnings": ["Viking is not reachable — precision_at_3 cannot be computed"],
            }

        if not queries:
            return {
                "precision_at_3": None,
                "query_results": [],
                "passed": 0,
                "failed": 0,
                "total": 0,
                "viking_available": True,
                "warnings": ["No queries provided"],
            }

        if limit < 1:
            return {
                "precision_at_3": None,
                "query_results": [],
                "passed": 0,
                "failed": 0,
                "total": 0,
                "viking_available": True,
                "warnings": [f"limit must be >= 1, got {limit}"],
            }

        query_results = []
        warnings: list[str] = []

        for q in queries:
            if not isinstance(q, dict):
                warnings.append(f"Skipping non-dict query: {q!r}")
                continue
            query_text = q.get("text", "")
            if not query_text:
                warnings.append(f"Skipping query with no text: {q}")
                continue

            # Search Viking
            results = _viking_search(viking_url, query_text, limit)

            judgments = []
            for res in results[:limit]:
                # Read full content for Claude to judge
                content = _viking_read(viking_url, res["uri"])

                judgments.append(
                    {
                        "uri": res["uri"],
                        "score": res["score"],
                        "content": content,
                        "verdict": "PENDING",
                    }
                )

            query_results.append(
                {
                    "query": query_text,
                    "source": q.get("source", ""),
                    "judgments": judgments,
                }
            )

        return {
            "precision_at_3": None,  # Claude computes after judging
            "query_results": query_results,
            "total": len(queries),
            "viking_available": True,
            "warnings": warnings,
        }
