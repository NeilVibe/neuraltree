"""neuraltree_precision — Viking search + LLM judge for Precision@3 scoring.

Wraps Viking (semantic search) and Ollama (LLM-as-Judge) into a single tool
so the Skill doesn't need direct access to either service.

For each query:
  1. Search Viking for top-K results
  2. Read full content of each result
  3. Ask Qwen3.5 (via Ollama) to judge YES/NO relevance
  4. Compute per-query precision and aggregate precision_at_3
"""
from __future__ import annotations

import os
from pathlib import Path

import requests
from fastmcp import FastMCP

from neuraltree_mcp.validation import validate_project_root

# Defaults — overridable per call
_DEFAULT_VIKING_URL = "http://localhost:1933"
_DEFAULT_OLLAMA_URL = "http://localhost:11434"
_DEFAULT_MODEL = "qwen3.5:4b"
_DEFAULT_LIMIT = 3
_CONNECT_TIMEOUT = 5
_READ_TIMEOUT = 30
_JUDGE_TIMEOUT = 60
_CONTENT_PREVIEW_CHARS = 3000  # ~50 lines for judge context


def _check_viking(viking_url: str) -> bool:
    """Return True if Viking is reachable."""
    try:
        r = requests.get(f"{viking_url}/health", timeout=_CONNECT_TIMEOUT)
        return r.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False


def _check_ollama(ollama_url: str) -> bool:
    """Return True if Ollama is reachable."""
    try:
        r = requests.get(f"{ollama_url}/api/tags", timeout=_CONNECT_TIMEOUT)
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


def _judge_relevance(
    ollama_url: str, model: str, query_text: str, result_uri: str, result_content: str
) -> str:
    """Ask LLM to judge YES/NO relevance. Returns 'YES', 'NO', or 'ERROR'."""
    prompt = (
        "RELEVANCE JUDGMENT\n"
        f"<query>{query_text[:500]}</query>\n"
        f"<result_file>{result_uri}</result_file>\n"
        f"<result_content>{result_content}</result_content>\n\n"
        "Rubric: Would reading this file help answer the query?\n"
        "- YES if the file contains information directly useful for answering\n"
        "- NO if the file is unrelated or only tangentially mentions the topic\n\n"
        "Reply YES or NO only."
    )
    try:
        r = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {"temperature": 0, "num_predict": 10},
            },
            timeout=_JUDGE_TIMEOUT,
        )
        if r.status_code != 200:
            return "ERROR"
        text = r.json().get("response", "").strip().upper()
        if "YES" in text:
            return "YES"
        if "NO" in text:
            return "NO"
        return "NO"  # conservative default for malformed responses
    except (requests.ConnectionError, requests.Timeout, ValueError, OSError):
        return "ERROR"


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def neuraltree_precision(
        queries: list[dict],
        project_root: str = ".",
        viking_url: str = _DEFAULT_VIKING_URL,
        ollama_url: str = _DEFAULT_OLLAMA_URL,
        model: str = _DEFAULT_MODEL,
        limit: int = _DEFAULT_LIMIT,
    ) -> dict:
        """Compute Precision@3 by searching Viking and judging with a local LLM.

        For each query, searches Viking for top results, reads their content,
        then asks the LLM to judge YES/NO relevance. Aggregates into precision_at_3.

        Args:
            queries: List of query dicts with at least {"text": "..."}.
                     Typically from neuraltree_generate_queries output.
            project_root: Project root (for validation).
            viking_url: Viking API base URL.
            ollama_url: Ollama API base URL.
            model: Ollama model name for LLM-as-Judge.
            limit: Number of Viking results per query (default 3).

        Returns:
            dict with precision_at_3 (float or null), per-query results,
            pass/fail counts, and service availability flags.
        """
        try:
            validate_project_root(project_root)
        except ValueError as e:
            return {"error": str(e)}

        # Check service availability
        viking_ok = _check_viking(viking_url)
        ollama_ok = _check_ollama(ollama_url)

        if not viking_ok:
            return {
                "precision_at_3": None,
                "query_results": [],
                "passed": 0,
                "failed": 0,
                "total": len(queries),
                "viking_available": False,
                "ollama_available": ollama_ok,
                "warnings": ["Viking is not reachable — precision_at_3 cannot be computed"],
            }

        if not ollama_ok:
            return {
                "precision_at_3": None,
                "query_results": [],
                "passed": 0,
                "failed": 0,
                "total": len(queries),
                "viking_available": True,
                "ollama_available": False,
                "warnings": [
                    f"Ollama is not reachable — LLM judge unavailable, precision_at_3 cannot be computed"
                ],
            }

        if not queries:
            return {
                "precision_at_3": None,
                "query_results": [],
                "passed": 0,
                "failed": 0,
                "total": 0,
                "viking_available": True,
                "ollama_available": True,
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
                "ollama_available": True,
                "warnings": [f"limit must be >= 1, got {limit}"],
            }

        query_results = []
        total_precision = 0.0
        warnings: list[str] = []

        for q in queries:
            query_text = q.get("text", "")
            if not query_text:
                warnings.append(f"Skipping query with no text: {q}")
                continue

            # Search Viking
            results = _viking_search(viking_url, query_text, limit)

            judgments = []
            for res in results[:limit]:
                # Read full content
                content = _viking_read(viking_url, res["uri"])

                # Judge relevance
                verdict = _judge_relevance(
                    ollama_url, model, query_text, res["uri"], content
                )

                judgments.append(
                    {
                        "uri": res["uri"],
                        "score": res["score"],
                        "relevant": verdict == "YES",
                        "verdict": verdict,
                    }
                )

            # Compute per-query precision — exclude ERROR verdicts from denominator
            error_count = sum(1 for j in judgments if j["verdict"] == "ERROR")
            scored_judgments = [j for j in judgments if j["verdict"] != "ERROR"]
            yes_count = sum(1 for j in scored_judgments if j["relevant"])
            denominator = min(len(scored_judgments), limit)
            # 2/3 relevant rounds to 0.667 which is below the 0.67 PASS threshold
            precision = yes_count / denominator if denominator > 0 else 0.0

            if error_count:
                warnings.append(
                    f"Query '{query_text[:60]}': {error_count} judgment(s) returned ERROR and were excluded"
                )

            status = "PASS" if precision >= 0.67 else "FAIL"

            query_results.append(
                {
                    "query": query_text,
                    "source": q.get("source", ""),
                    "precision": round(precision, 3),
                    "status": status,
                    "judgments": judgments,
                    "error_count": error_count,
                }
            )
            total_precision += precision

        # Aggregate
        scored_count = len(query_results)
        precision_at_3 = round(total_precision / scored_count, 3) if scored_count > 0 else None
        passed = sum(1 for qr in query_results if qr["status"] == "PASS")
        failed = sum(1 for qr in query_results if qr["status"] == "FAIL")

        return {
            "precision_at_3": precision_at_3,
            "query_results": query_results,
            "passed": passed,
            "failed": failed,
            "total": len(queries),
            "scored": scored_count,
            "viking_available": True,
            "ollama_available": True,
            "warnings": warnings,
        }
