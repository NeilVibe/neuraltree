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


class TestCalibration:
    """Calibration update and accumulation tests."""

    def test_update_calibration(self, tmp_project):
        """Update calibration and verify accuracy changes."""
        # First update — predicted 0.10, actual 0.08 (close)
        result = call_tool("neuraltree_update_calibration", {
            "predicted_delta": 0.10,
            "actual_delta": 0.08,
            "project_root": str(tmp_project),
        })
        assert result["old_accuracy"] == 0.5  # default start
        assert result["new_accuracy"] != 0.5  # should have changed
        assert result["total_runs"] == 1

        # Second update — verify it accumulates
        result2 = call_tool("neuraltree_update_calibration", {
            "predicted_delta": 0.05,
            "actual_delta": 0.04,
            "project_root": str(tmp_project),
        })
        assert result2["total_runs"] == 2
        assert result2["old_accuracy"] == result["new_accuracy"]

        # Verify file was written
        cal_file = tmp_project / ".neuraltree" / "calibration.json"
        assert cal_file.exists()


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


class TestAutoLoopCycle:
    """Simulate one autoloop iteration: predict -> backup -> modify -> score -> restore."""

    def test_predict_backup_execute_restore_cycle(self, tmp_project):
        """Simulate one autoloop iteration: predict -> backup -> modify -> score -> restore."""
        target_rel = "memory/rules/coding.md"
        original = (tmp_project / target_rel).read_text()

        # 1. Score before
        before = call_tool("neuraltree_score", {"project_root": str(tmp_project)})

        # 2. Predict
        prediction = call_tool("neuraltree_predict", {
            "current_metrics": before["metrics"],
            "proposed_changes": [
                {"action": "wire", "target": target_rel, "details": "test"},
            ],
            "project_root": str(tmp_project),
        })
        assert prediction["predicted_delta"] >= 0

        # 3. Backup
        backup = call_tool("neuraltree_backup", {
            "files": [target_rel],
            "project_root": str(tmp_project),
        })
        assert len(backup["backed_up"]) == 1

        # 4. Execute (simulate wire by modifying file)
        (tmp_project / target_rel).write_text(
            original + "\n## Related\n- [testing.md](testing.md) — patterns\n"
            "- [auth.md](../reference/auth.md) — auth rules\n"
        )

        # 5. Score after
        after = call_tool("neuraltree_score", {"project_root": str(tmp_project)})

        # 6. Decide — if worse, restore
        actual_delta = after["flow_score_partial"] - before["flow_score_partial"]
        if actual_delta < 0:
            call_tool("neuraltree_restore", {
                "files": [target_rel],
                "project_root": str(tmp_project),
            })
            assert (tmp_project / target_rel).read_text() == original

        # 7. Update calibration
        cal = call_tool("neuraltree_update_calibration", {
            "predicted_delta": prediction["predicted_delta"],
            "actual_delta": actual_delta,
            "project_root": str(tmp_project),
        })
        assert cal["total_runs"] == 1
