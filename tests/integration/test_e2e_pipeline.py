"""End-to-end pipeline tests against a real project (newfin).

Simulates what an agent following SKILL.md Section 4 would do:
scan the project, generate queries, score it, diagnose failures, predict improvements.
"""
import asyncio
import json
import pytest

from neuraltree_mcp.server import mcp


def call_tool(name: str, args: dict) -> dict:
    """Helper to call an MCP tool synchronously and parse the result."""
    result = asyncio.run(mcp.call_tool(name, args))
    # FastMCP v3 returns a ToolResult with structured_content
    if hasattr(result, "structured_content") and result.structured_content is not None:
        return result.structured_content
    # Fallback: parse from content text blocks
    if hasattr(result, "content"):
        for block in result.content:
            if hasattr(block, "text"):
                return json.loads(block.text)
    return result


class TestBenchmarkPipeline:
    """Pipeline tests against /home/neil1988/newfin — read-only."""

    def test_scan_newfin(self, newfin_project):
        """Scan should enumerate real project files without error."""
        result = call_tool("neuraltree_scan", {"path": str(newfin_project)})
        assert "error" not in result
        assert result["total_count"] > 0
        assert len(result["files"]) > 0
        assert isinstance(result["files"][0], str)
        # Real project should have multiple dirs
        assert len(result["dirs"]) > 0
        # Should find CLAUDE.md
        assert "CLAUDE.md" in result["files"]

    def test_generate_queries_newfin(self, newfin_project):
        """Query generator should produce queries from a real CLAUDE.md + git log."""
        result = call_tool("neuraltree_generate_queries", {
            "project_root": str(newfin_project),
            "claude_md_path": str(newfin_project / "CLAUDE.md"),
            "git_log_lines": 50,
            "indexed_doc_count": 30,
        })
        assert "error" not in result
        assert result["total"] > 0
        assert len(result["queries"]) > 0
        q = result["queries"][0]
        assert "text" in q and "source" in q and "category" in q
        # Sources dict should be present
        assert isinstance(result["sources"], dict)

    def test_score_newfin(self, newfin_project):
        """Score should compute all structural metrics on a real project."""
        result = call_tool("neuraltree_score", {"project_root": str(newfin_project)})
        assert "error" not in result
        metrics = result["metrics"]
        # All metric keys must be present
        for key in ["hop_efficiency", "synapse_coverage", "dead_neuron_ratio", "freshness", "trunk_pressure"]:
            assert key in metrics, f"Missing metric: {key}"
            assert isinstance(metrics[key], (int, float)), f"{key} should be numeric"
            assert 0.0 <= metrics[key] <= 1.0, f"{key}={metrics[key]} out of range"
        # precision_at_3 is always None (needs Viking)
        assert metrics["precision_at_3"] is None
        # Partial flow score present and bounded
        assert "flow_score_partial" in result
        assert 0.0 <= result["flow_score_partial"] <= 1.0
        # Details should have orphan/stale info
        assert "details" in result
        assert "total_md_files" in result["details"]

    def test_diagnose_with_failures(self, newfin_project):
        """Diagnose should classify each failed query into a gap type."""
        failed_queries = [
            {"text": "How does the backtesting system work?", "expected_topic": "backtest"},
            {"text": "What is the scoring algorithm?", "expected_topic": "scoring"},
            {"text": "Where is the Discord integration?", "expected_topic": "discord"},
        ]
        result = call_tool("neuraltree_diagnose", {
            "failed_queries": failed_queries,
            "project_root": str(newfin_project),
        })
        assert result["total_failures"] == 3
        assert len(result["diagnoses"]) == 3
        valid_gap_types = {"CONTENT_GAP", "EMBEDDING_GAP", "SYNAPSE_GAP", "FRESHNESS_GAP", "FOCUS_GAP"}
        for d in result["diagnoses"]:
            assert d["gap_type"] in valid_gap_types, f"Unknown gap type: {d['gap_type']}"
            assert "query" in d
            assert "fix" in d
            assert "matching_files" in d
        # gap_counts summary should be present
        assert "gap_counts" in result
        # fix_priority should list all diagnoses sorted by priority
        assert "fix_priority" in result
        assert len(result["fix_priority"]) == 3

    def test_predict_impact(self, newfin_project):
        """Predict should estimate improvement from proposed changes."""
        # First get the real score
        score = call_tool("neuraltree_score", {"project_root": str(newfin_project)})
        assert "error" not in score

        result = call_tool("neuraltree_predict", {
            "current_metrics": score["metrics"],
            "proposed_changes": [
                {"action": "wire", "target": "memory/reference/auth.md", "details": "Add ## Related"},
                {"action": "update_freshness", "target": "memory/rules/coding.md", "details": "Update date"},
            ],
            "project_root": str(newfin_project),
        })
        assert "error" not in result
        assert result["predicted_delta"] >= 0
        assert 0.0 <= result["confidence"] <= 1.0
        # Should have per-change impacts
        assert len(result["change_impacts"]) == 2
        assert "current_flow_score" in result
        assert "predicted_flow_score" in result
        assert result["predicted_flow_score"] >= result["current_flow_score"]
