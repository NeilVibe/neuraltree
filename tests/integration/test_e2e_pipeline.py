"""End-to-end pipeline tests against a real project (newfin).

Simulates what an agent following SKILL.md would do:
scan the project, generate queries, score it, diagnose failures.
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
        """Query generator should produce queries from a real CLAUDE.md."""
        result = call_tool("neuraltree_generate_queries", {
            "project_root": str(newfin_project),
            "claude_md_path": str(newfin_project / "CLAUDE.md"),
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
        """Score requires a knowledge map — without one, returns error."""
        result = call_tool("neuraltree_score", {"project_root": str(newfin_project)})
        # Without a knowledge map, score returns an error
        if "error" in result:
            assert "knowledge map" in result["error"].lower()
        else:
            # If a map exists from a prior run, check universal metrics
            metrics = result["metrics"]
            for key in ["reachability", "connectivity", "cluster_coherence", "size_balance"]:
                assert key in metrics, f"Missing metric: {key}"
                assert isinstance(metrics[key], (int, float)), f"{key} should be numeric"
                assert 0.0 <= metrics[key] <= 1.0, f"{key}={metrics[key]} out of range"
            assert metrics["discoverability"] is None
            assert "flow_score_partial" in result
            assert 0.0 <= result["flow_score_partial"] <= 1.0
            assert "details" in result
            assert "total_files" in result["details"]

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
        valid_gap_types = {"CONTENT_GAP", "EMBEDDING_GAP", "ISOLATION_GAP", "FOCUS_GAP"}
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


class TestBackupRestore:
    """Backup/restore round-trip and wire read-only verification."""

    def test_backup_and_restore_single_file(self, tmp_project):
        """Backup coding.md, overwrite it, restore it, verify original content."""
        coding_path = tmp_project / "memory" / "rules" / "coding.md"
        original_content = coding_path.read_text()

        # Backup
        result = call_tool("neuraltree_backup", {
            "files": ["memory/rules/coding.md"],
            "project_root": str(tmp_project),
        })
        assert "error" not in result
        assert "memory/rules/coding.md" in result["backed_up"]

        # Overwrite with different content
        coding_path.write_text("# OVERWRITTEN\nThis is not the original.\n")
        assert coding_path.read_text() != original_content

        # Restore
        result = call_tool("neuraltree_restore", {
            "files": ["memory/rules/coding.md"],
            "project_root": str(tmp_project),
        })
        assert "error" not in result
        assert "memory/rules/coding.md" in result["restored"]

        # Verify original content is back
        assert coding_path.read_text() == original_content
        assert len(result.get("not_found", [])) == 0, "Some files were not found in backup"

    def test_backup_multiple_files(self, tmp_project):
        """Backup coding.md + testing.md, modify both, restore both, verify originals."""
        coding_path = tmp_project / "memory" / "rules" / "coding.md"
        testing_path = tmp_project / "memory" / "rules" / "testing.md"
        original_coding = coding_path.read_text()
        original_testing = testing_path.read_text()

        # Backup both
        result = call_tool("neuraltree_backup", {
            "files": ["memory/rules/coding.md", "memory/rules/testing.md"],
            "project_root": str(tmp_project),
        })
        assert "error" not in result
        assert len(result["backed_up"]) == 2

        # Overwrite both
        coding_path.write_text("# DESTROYED coding\n")
        testing_path.write_text("# DESTROYED testing\n")
        assert coding_path.read_text() != original_coding
        assert testing_path.read_text() != original_testing

        # Restore both (pass None to restore all)
        result = call_tool("neuraltree_restore", {
            "project_root": str(tmp_project),
        })
        assert "error" not in result
        assert len(result["restored"]) >= 2

        # Verify both originals are back
        assert coding_path.read_text() == original_coding
        assert testing_path.read_text() == original_testing
        assert len(result.get("not_found", [])) == 0, "Some files were not found in backup"

    def test_wire_preview_is_read_only(self, tmp_project):
        """Wire returns suggestions but does NOT modify the target file."""
        coding_path = tmp_project / "memory" / "rules" / "coding.md"
        original_content = coding_path.read_text()

        # Call wire on coding.md
        result = call_tool("neuraltree_wire", {
            "file_path": "memory/rules/coding.md",
            "project_root": str(tmp_project),
        })
        assert "error" not in result
        # Wire should return suggestions
        assert "suggested_content" in result

        # Verify file content is UNCHANGED
        assert coding_path.read_text() == original_content


class TestScaleLimits:
    """Scale boundary tests — scan caps, large project scoring, query scaling."""

    def test_scan_caps_at_max_files(self, tmp_project_large):
        """Scan with max_files=50 should cap at 50 files on a 150-file project."""
        result = call_tool("neuraltree_scan", {
            "path": str(tmp_project_large),
            "max_files": 50,
        })
        assert "error" not in result
        assert result["capped"] is True
        assert result["total_count"] <= 50

    def test_score_on_large_project(self, tmp_project_large):
        """Score a 150-file project (mostly .py). Should handle gracefully."""
        result = call_tool("neuraltree_score", {
            "project_root": str(tmp_project_large),
        })
        # tmp_project_large has 1 CLAUDE.md + 150 .py files
        assert "flow_score_partial" in result
        assert result["flow_score_partial"] >= 0.0

    def test_query_scaling_formula(self, tmp_project):
        """Query count scales with indexed_doc_count — more docs = more queries.

        Formula: target = max(20, min(50, indexed_doc_count // 3))
        Actual count may be below target if project content is limited,
        but should never EXCEED the target cap.
        """
        # Low doc count → target = max(20, min(50, 9//3=3)) = 20
        result_low = call_tool("neuraltree_generate_queries", {
            "project_root": str(tmp_project),
            "claude_md_path": str(tmp_project / "CLAUDE.md"),
            "indexed_doc_count": 9,
        })
        assert "error" not in result_low
        assert result_low["total"] <= 50  # never exceeds upper cap

        # High doc count → target = max(20, min(50, 150//3=50)) = 50
        result_high = call_tool("neuraltree_generate_queries", {
            "project_root": str(tmp_project),
            "claude_md_path": str(tmp_project / "CLAUDE.md"),
            "indexed_doc_count": 150,
        })
        assert "error" not in result_high
        assert result_high["total"] <= 50  # hard cap at 50
        # More indexed docs should produce >= as many queries (or same)
        assert result_high["total"] >= result_low["total"]


class TestLessonRoundTrip:
    """Lesson add + match round-trip verification."""

    def test_lesson_add_and_match(self, tmp_project):
        """Add a lesson, then match it by symptom."""
        # Add
        add_result = call_tool("neuraltree_lesson_add", {
            "domain": "testing",
            "lesson": {
                "symptom": "Widget crashes on empty input",
                "root_cause": "No null check",
                "fix": "Added guard clause",
            },
            "project_root": str(tmp_project),
        })
        assert add_result["added"] is True
        assert add_result["domain"] == "testing"

        # Match
        match_result = call_tool("neuraltree_lesson_match", {
            "symptoms": ["Widget crashes when input is empty"],
            "project_root": str(tmp_project),
        })
        assert match_result["total_matches"] > 0
        top = match_result["matches"][0]["lessons"]
        assert len(top) > 0
        assert top[0]["score"] > 0.2



class TestTrace:
    """Trace tool tests — reference graph traversal."""

    def test_trace_finds_references(self, tmp_project):
        """Trace a file and find what references it."""
        result = call_tool("neuraltree_trace", {
            "target": "memory/rules/coding.md",
            "project_root": str(tmp_project),
        })
        assert "referenced_by" in result
        assert "references_to" in result
        assert "is_alive" in result
        # coding.md is referenced by testing.md (## Related) and _INDEX.md
        assert result["is_alive"] is True
        assert len(result["referenced_by"]) > 0

    def test_trace_orphan_file(self, tmp_project):
        """Trace an orphan file — should have zero references."""
        result = call_tool("neuraltree_trace", {
            "target": "memory/reference/auth.md",
            "project_root": str(tmp_project),
        })
        # auth.md is intentionally unwired (orphan in conftest)
        assert result["is_alive"] is False or len(result["referenced_by"]) == 0


