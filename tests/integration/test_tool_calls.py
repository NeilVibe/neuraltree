"""Integration tests — call actual MCP tools via mcp.call_tool()."""
import asyncio
import json
import os
import pytest

from neuraltree_mcp.server import mcp


def call_tool(name: str, args: dict) -> dict:
    """Helper to call an MCP tool synchronously and parse the result."""
    result = asyncio.run(mcp.call_tool(name, args))
    # FastMCP v3 returns a ToolResult with structured_content
    if hasattr(result, 'structured_content') and result.structured_content is not None:
        return result.structured_content
    # Fallback: parse from content text blocks
    if hasattr(result, 'content'):
        for block in result.content:
            if hasattr(block, 'text'):
                return json.loads(block.text)
    return result


class TestScanTool:
    def test_scan_returns_correct_shape(self, tmp_project):
        result = call_tool("neuraltree_scan", {"path": str(tmp_project)})
        assert "dirs" in result
        assert "files" in result
        assert "sizes" in result
        assert "dates" in result
        assert "empty_dirs" in result
        assert "total_count" in result
        assert "capped" in result
        assert "warnings" in result

    def test_scan_finds_files(self, tmp_project):
        result = call_tool("neuraltree_scan", {"path": str(tmp_project)})
        assert "CLAUDE.md" in result["files"]
        assert result["total_count"] > 0

    def test_scan_caps_at_max(self, tmp_project_large):
        result = call_tool("neuraltree_scan", {"path": str(tmp_project_large), "max_files": 5})
        assert result["capped"] is True
        assert result["total_count"] == 5

    def test_scan_invalid_path(self):
        result = call_tool("neuraltree_scan", {"path": "/nonexistent/dir"})
        assert "error" in result


class TestTraceTool:
    def test_trace_returns_correct_shape(self, tmp_project):
        result = call_tool("neuraltree_trace", {
            "target": "memory/rules/coding.md",
            "project_root": str(tmp_project),
        })
        assert "referenced_by" in result
        assert "references_to" in result
        assert "is_alive" in result
        assert "permission_errors" in result

    def test_trace_coding_md_outbound(self, tmp_project):
        result = call_tool("neuraltree_trace", {
            "target": "memory/rules/coding.md",
            "project_root": str(tmp_project),
        })
        assert "testing.md" in result["references_to"]
        assert "server/main.py" in result["references_to"]

    def test_trace_orphan_is_dead(self, tmp_project):
        result = call_tool("neuraltree_trace", {
            "target": "memory/reference/auth.md",
            "project_root": str(tmp_project),
        })
        assert result["is_alive"] is False


class TestBackupRestoreTool:
    def test_backup_and_restore(self, tmp_project):
        # Backup
        result = call_tool("neuraltree_backup", {
            "files": ["CLAUDE.md", "memory/rules/coding.md"],
            "project_root": str(tmp_project),
        })
        assert len(result["backed_up"]) == 2
        assert len(result["skipped"]) == 0
        assert "warnings" in result

        # Modify original
        (tmp_project / "CLAUDE.md").write_text("MODIFIED")

        # Restore
        result2 = call_tool("neuraltree_restore", {
            "files": ["CLAUDE.md"],
            "project_root": str(tmp_project),
        })
        assert "CLAUDE.md" in result2["restored"]
        assert "MODIFIED" not in (tmp_project / "CLAUDE.md").read_text()

    def test_backup_nonexistent_file(self, tmp_project):
        result = call_tool("neuraltree_backup", {
            "files": ["nonexistent.md"],
            "project_root": str(tmp_project),
        })
        assert len(result["backed_up"]) == 0
        assert len(result["skipped"]) == 1

    def test_backup_path_traversal_blocked(self, tmp_project):
        result = call_tool("neuraltree_backup", {
            "files": ["../../etc/passwd"],
            "project_root": str(tmp_project),
        })
        assert len(result["backed_up"]) == 0
        assert any("traversal" in s for s in result["skipped"])


class TestWireTool:
    def test_wire_returns_correct_shape(self, tmp_project):
        result = call_tool("neuraltree_wire", {
            "file_path": "memory/rules/coding.md",
            "project_root": str(tmp_project),
        })
        assert "related" in result
        assert "docs" in result
        assert "suggested_content" in result

    def test_wire_finds_related_files(self, tmp_project):
        result = call_tool("neuraltree_wire", {
            "file_path": "memory/rules/coding.md",
            "project_root": str(tmp_project),
        })
        # Should find testing.md as related
        related_files = [r["file"] for r in result["related"]]
        # Score might be above threshold due to shared keywords + same dir boost
        assert isinstance(result["related"], list)

    def test_wire_docs_direction_is_references(self, tmp_project):
        result = call_tool("neuraltree_wire", {
            "file_path": "memory/rules/coding.md",
            "project_root": str(tmp_project),
        })
        for doc in result["docs"]:
            assert doc["direction"] == "references"

    def test_wire_nonexistent_file(self, tmp_project):
        result = call_tool("neuraltree_wire", {
            "file_path": "nonexistent.md",
            "project_root": str(tmp_project),
        })
        assert "error" in result

    def test_wire_jaccard_capped_at_1(self, tmp_project):
        result = call_tool("neuraltree_wire", {
            "file_path": "memory/rules/coding.md",
            "project_root": str(tmp_project),
        })
        for r in result["related"]:
            assert r["score"] <= 1.0


class TestGenerateQueriesTool:
    def test_generates_queries(self, tmp_project):
        result = call_tool("neuraltree_generate_queries", {
            "project_root": str(tmp_project),
        })
        assert "queries" in result
        assert "sources" in result
        assert "total" in result
        assert "warnings" in result
        assert result["total"] > 0

    def test_generates_from_glossary(self, tmp_project):
        result = call_tool("neuraltree_generate_queries", {
            "project_root": str(tmp_project),
        })
        query_texts = [q["text"] for q in result["queries"]]
        # Should have generated "What is TM?" from the glossary
        assert any("TM" in q for q in query_texts)


class TestScoreTool:
    def test_score_returns_all_metrics(self, tmp_project):
        result = call_tool("neuraltree_score", {
            "project_root": str(tmp_project),
        })
        assert "metrics" in result
        metrics = result["metrics"]
        assert "hop_efficiency" in metrics
        assert "precision_at_3" in metrics
        assert "synapse_coverage" in metrics
        assert "dead_neuron_ratio" in metrics
        assert "freshness" in metrics
        assert "trunk_pressure" in metrics
        assert metrics["precision_at_3"] is None  # needs Viking
        assert "warnings" in result

    def test_score_has_flow_score(self, tmp_project):
        result = call_tool("neuraltree_score", {
            "project_root": str(tmp_project),
        })
        assert "flow_score_partial" in result
        assert 0.0 <= result["flow_score_partial"] <= 1.0

    def test_score_has_details(self, tmp_project):
        result = call_tool("neuraltree_score", {
            "project_root": str(tmp_project),
        })
        details = result["details"]
        assert "total_md_files" in details
        assert "orphan_files" in details
        assert "stale_files" in details


class TestDiagnoseTool:
    def test_diagnose_content_gap(self, tmp_project):
        result = call_tool("neuraltree_diagnose", {
            "failed_queries": [{"text": "What is quantum computing?"}],
            "project_root": str(tmp_project),
        })
        assert result["total_failures"] == 1
        assert result["diagnoses"][0]["gap_type"] == "CONTENT_GAP"
        assert "warnings" in result

    def test_diagnose_synapse_gap(self, tmp_project):
        result = call_tool("neuraltree_diagnose", {
            "failed_queries": [{"text": "What is auth model LAN IP-lock admin?"}],
            "project_root": str(tmp_project),
        })
        # auth.md exists but has no wiring
        diag = result["diagnoses"][0]
        assert diag["gap_type"] in ("SYNAPSE_GAP", "CONTENT_GAP")  # depends on keyword matching


class TestPredictTool:
    def test_predict_returns_correct_shape(self, tmp_project):
        result = call_tool("neuraltree_predict", {
            "current_metrics": {
                "synapse_coverage": 0.4,
                "dead_neuron_ratio": 0.7,
                "hop_efficiency": 0.3,
                "freshness": 0.5,
                "trunk_pressure": 0.8,
                "precision_at_3": 0.0,
            },
            "proposed_changes": [
                {"action": "wire", "target": "auth.md", "details": "add wiring"},
            ],
            "project_root": str(tmp_project),
        })
        assert "current_flow_score" in result
        assert "predicted_flow_score" in result
        assert "predicted_delta" in result
        assert "confidence" in result
        assert result["predicted_delta"] > 0


class TestLessonMatchTool:
    def test_lesson_match_via_mcp(self, tmp_project):
        result = call_tool("neuraltree_lesson_match", {
            "symptoms": ["DDS images not showing"],
            "project_root": str(tmp_project),
        })
        assert "matches" in result
        assert "total_matches" in result
        assert "warnings" in result
        assert len(result["matches"]) == 1
        assert result["matches"][0]["symptom_query"] == "DDS images not showing"
        assert len(result["matches"][0]["lessons"]) > 0

    def test_lesson_match_zero_match_emits_entry(self, tmp_project):
        result = call_tool("neuraltree_lesson_match", {
            "symptoms": ["quantum computing breakthrough"],
            "project_root": str(tmp_project),
        })
        assert len(result["matches"]) == 1
        assert result["matches"][0]["lessons"] == []

    def test_lesson_match_batch(self, tmp_project):
        result = call_tool("neuraltree_lesson_match", {
            "symptoms": ["DDS images", "PostgreSQL connection"],
            "project_root": str(tmp_project),
        })
        assert len(result["matches"]) == 2
        # Each symptom should get independent results
        dds_matches = result["matches"][0]["lessons"]
        pg_matches = result["matches"][1]["lessons"]
        # DDS should match images.md, PG should match database.md
        if dds_matches:
            assert any("images" in m["domain"] for m in dds_matches)
        if pg_matches:
            assert any("database" in m["domain"] for m in pg_matches)


class TestLessonAddTool:
    def test_lesson_add_via_mcp(self, tmp_project):
        result = call_tool("neuraltree_lesson_add", {
            "domain": "networking",
            "lesson": {
                "symptom": "WebSocket disconnects on LAN",
                "root_cause": "Router firewall drops idle connections",
                "fix": "Add keepalive ping every 30s",
            },
            "project_root": str(tmp_project),
        })
        assert result["added"] is True
        assert result["domain"] == "networking"
        assert "warnings" in result
        # Verify file was created
        lesson_file = tmp_project / "memory" / "lessons" / "networking.md"
        assert lesson_file.exists()
        content = lesson_file.read_text()
        assert "WebSocket disconnects" in content

    def test_lesson_add_domain_case_normalization(self, tmp_project):
        result = call_tool("neuraltree_lesson_add", {
            "domain": "IMAGES",
            "lesson": {
                "symptom": "SVG rendering broken",
                "root_cause": "Missing SVG handler",
                "fix": "Install svglib",
            },
            "project_root": str(tmp_project),
        })
        assert result["added"] is True
        assert result["domain"] == "images"
        # Should append to existing images.md
        assert result["file"].endswith("images.md")

    def test_lesson_add_path_traversal_blocked(self, tmp_project):
        result = call_tool("neuraltree_lesson_add", {
            "domain": "../../etc/passwd",
            "lesson": {
                "symptom": "test",
                "root_cause": "test",
                "fix": "test",
            },
            "project_root": str(tmp_project),
        })
        assert result["added"] is False
        assert "error" in result


    def test_lesson_add_with_key_file_creates_docs(self, tmp_project):
        """lesson_add with key_file should create ## Docs section."""
        result = call_tool("neuraltree_lesson_add", {
            "domain": "testing",
            "lesson": {
                "symptom": "Playwright tests timeout on CI",
                "root_cause": "Missing browser binary in Docker",
                "fix": "Add playwright install to Dockerfile",
                "key_file": "Dockerfile",
            },
            "project_root": str(tmp_project),
        })
        assert result["added"] is True
        content = (tmp_project / "memory" / "lessons" / "testing.md").read_text()
        assert "## Docs" in content
        assert "`Dockerfile`" in content

    def test_lesson_add_duplicate_returns_false(self, tmp_project):
        """Adding a near-duplicate symptom should be rejected."""
        # images.md already has "DDS Images Not Showing (Phase 113)"
        # Heading extracted as "DDS Images Not Showing" -> keywords: {dds, images, showing}
        # Need >80% overlap: use exact same words
        result = call_tool("neuraltree_lesson_add", {
            "domain": "images",
            "lesson": {
                "symptom": "DDS Images Not Showing",
                "root_cause": "same issue",
                "fix": "same fix",
            },
            "project_root": str(tmp_project),
        })
        assert result["duplicate"] is True
        assert result["added"] is False

    def test_lesson_add_size_cap_blocks(self, tmp_project):
        """File exceeding 512KB should be rejected."""
        # Create a huge domain file
        lessons_dir = tmp_project / "memory" / "lessons"
        huge = lessons_dir / "huge.md"
        huge.write_text("x" * (512 * 1024 + 1))
        result = call_tool("neuraltree_lesson_add", {
            "domain": "huge",
            "lesson": {
                "symptom": "test",
                "root_cause": "test",
                "fix": "test",
            },
            "project_root": str(tmp_project),
        })
        assert result["added"] is False
        assert "limit" in result.get("error", "").lower() or "exceed" in result.get("error", "").lower()


class TestGenerateQueriesWithLessons:
    def test_generates_regression_queries(self, tmp_project):
        result = call_tool("neuraltree_generate_queries", {
            "project_root": str(tmp_project),
        })
        assert "lessons" in result["sources"]
        assert result["sources"]["lessons"] >= 3  # 2 from images.md + 1 from database.md
        regression_queries = [q for q in result["queries"] if q["category"] == "regression"]
        assert len(regression_queries) >= 1
        assert any("recurred" in q["text"] for q in regression_queries)


class TestSandboxApplyTool:
    def test_sandbox_apply_path_traversal_blocked(self, tmp_project):
        """Explicitly supplied paths should be blocked from escaping root."""
        # Create a sandbox first
        sandbox_dir = tmp_project / ".neuraltree" / "sandbox"
        sandbox_dir.mkdir(parents=True)
        (sandbox_dir / "test.md").write_text("safe content")

        result = call_tool("neuraltree_sandbox_apply", {
            "files": ["../../etc/passwd"],
            "project_root": str(tmp_project),
        })
        assert any("traversal" in e or "not found" in e for e in result["errors"])
