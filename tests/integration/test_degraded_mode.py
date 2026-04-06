"""Integration tests — degraded mode (no Viking available).

Proves that MCP tools work correctly when Viking is not available:
- Score computes 4 structural metrics from knowledge map, discoverability stays None
- Flow score formula uses degraded weights (capped at 0.90)
- Diagnose classifies using keyword matching only (no EMBEDDING_GAP)
- Lesson matching works purely on Jaccard similarity
"""
import asyncio
import json

import pytest

from neuraltree_mcp.server import mcp


def call_tool(name: str, args: dict) -> dict:
    """Helper to call an MCP tool synchronously and parse the result."""
    result = asyncio.run(mcp.call_tool(name, args))
    if hasattr(result, "structured_content") and result.structured_content is not None:
        return result.structured_content
    if hasattr(result, "content"):
        for block in result.content:
            if hasattr(block, "text"):
                return json.loads(block.text)
    return result


class TestScoreWithoutViking:
    """neuraltree_score returns 4 structural metrics from knowledge map; discoverability is None."""

    def _create_km(self, tmp_project):
        import json
        nt_dir = tmp_project / ".neuraltree"
        nt_dir.mkdir(exist_ok=True)
        km = {
            "files": {
                "CLAUDE.md": {"size_lines": 50},
                "memory/MEMORY.md": {"size_lines": 20},
                "memory/rules/coding.md": {"size_lines": 30},
            },
            "edges": [
                {"source": "CLAUDE.md", "target": "memory/MEMORY.md", "type": "reference"},
                {"source": "memory/MEMORY.md", "target": "memory/rules/coding.md", "type": "reference"},
            ],
            "clusters": [{"files": ["memory/MEMORY.md", "memory/rules/coding.md"]}],
        }
        (nt_dir / "knowledge_map.json").write_text(json.dumps(km))

    def test_score_without_viking(self, tmp_project):
        self._create_km(tmp_project)
        result = call_tool("neuraltree_score", {"project_root": str(tmp_project)})

        metrics = result["metrics"]

        # All 4 structural metrics present and numeric
        for key in ("reachability", "connectivity", "cluster_coherence", "size_balance"):
            assert key in metrics, f"Missing metric: {key}"
            assert isinstance(metrics[key], (int, float)), f"{key} should be numeric"
            assert 0.0 <= metrics[key] <= 1.0, f"{key} out of range: {metrics[key]}"

        # discoverability is None — Viking computes it, not MCP
        assert metrics["discoverability"] is None

        # Partial flow score is positive (project has connected files)
        assert result["flow_score_partial"] > 0

    def test_degraded_flow_score_formula(self, tmp_project):
        """Verify the degraded formula: discoverability=None means it contributes 0.

        Weights: reachability=0.30, connectivity=0.25, cluster_coherence=0.20,
                 size_balance=0.15, discoverability=0.10
        Degraded: discoverability is None so skipped. Max possible = 0.90.
        """
        self._create_km(tmp_project)
        result = call_tool("neuraltree_score", {"project_root": str(tmp_project)})

        metrics = result["metrics"]
        weights = result["flow_score_weights"]

        # Manually compute expected partial score (skip discoverability)
        expected = 0.0
        for key, weight in weights.items():
            if metrics[key] is not None:
                expected += metrics[key] * weight
        expected = round(expected, 3)

        assert result["flow_score_partial"] == expected

        # Degraded cap: max possible is sum of non-None weights = 0.90
        non_none_weight = sum(w for k, w in weights.items() if metrics[k] is not None)
        assert abs(non_none_weight - 0.90) < 0.001, f"Non-None weight sum should be 0.90, got {non_none_weight}"

        assert result["flow_score_partial"] <= 0.90 + 0.001


class TestDiagnoseWithoutViking:
    """neuraltree_diagnose with no viking_results uses keyword matching only."""

    def test_diagnose_without_viking_results(self, tmp_project):
        """When viking_results is omitted, diagnose never classifies as EMBEDDING_GAP."""
        result = call_tool("neuraltree_diagnose", {
            "failed_queries": [
                {"text": "PostgreSQL connection refused after router reboot", "expected_topic": "database"},
                {"text": "how to configure quantum flux capacitor", "expected_topic": ""},
            ],
            "project_root": str(tmp_project),
        })

        assert result["total_failures"] == 2
        assert len(result["diagnoses"]) == 2

        # No EMBEDDING_GAP without Viking results
        for diag in result["diagnoses"]:
            assert diag["gap_type"] != "EMBEDDING_GAP", (
                f"EMBEDDING_GAP should not occur without Viking: {diag}"
            )
            assert diag["gap_type"] in (
                "CONTENT_GAP", "ISOLATION_GAP", "FOCUS_GAP"
            )
            assert "fix" in diag

        # The DB query should find matching files (database.md has PG content)
        db_diag = result["diagnoses"][0]
        assert len(db_diag["matching_files"]) > 0, "Should find database-related files via keywords"

        # The quantum query should be CONTENT_GAP (nothing matches)
        quantum_diag = result["diagnoses"][1]
        assert quantum_diag["gap_type"] == "CONTENT_GAP"


class TestLessonMatchWithoutViking:
    """neuraltree_lesson_match is purely keyword-based — no Viking needed."""

    def test_lesson_match_works_without_viking(self, tmp_project):
        result = call_tool("neuraltree_lesson_match", {
            "symptoms": [
                "images not showing in Codex",
                "Chrome caching old images",
            ],
            "project_root": str(tmp_project),
        })

        assert result["total_matches"] > 0
        assert len(result["matches"]) == 2

        # First symptom should match the DDS/images lesson
        first = result["matches"][0]
        assert first["symptom_query"] == "images not showing in Codex"
        assert len(first["lessons"]) > 0

        top_match = first["lessons"][0]
        assert "score" in top_match
        assert top_match["score"] > 0.2  # Above threshold
        assert "domain" in top_match
        assert "file" in top_match
        assert "fields" in top_match

        # Second symptom should match Chrome cache bug
        second = result["matches"][1]
        assert second["symptom_query"] == "Chrome caching old images"
        assert len(second["lessons"]) > 0
