"""Integration tests — verify MCP server loads all tools."""
import asyncio
import pytest


class TestServerLoads:
    def test_import_server(self):
        """Server module should import without error."""
        from neuraltree_mcp.server import mcp
        assert mcp is not None

    def test_all_tools_registered(self):
        """All 20 tools should be registered."""
        from neuraltree_mcp.server import mcp
        tools = asyncio.run(mcp.list_tools())
        tool_names = [t.name for t in tools]

        expected = [
            "neuraltree_scan",
            "neuraltree_trace",
            "neuraltree_backup",
            "neuraltree_restore",
            "neuraltree_wire",
            "neuraltree_generate_queries",
            "neuraltree_plan_move",
            "neuraltree_plan_split",
            "neuraltree_find_dead",
            "neuraltree_generate_index",
            "neuraltree_lesson_match",
            "neuraltree_lesson_add",
            "neuraltree_score",
            "neuraltree_diagnose",
            "neuraltree_predict",
            "neuraltree_update_calibration",
            "neuraltree_sandbox_create",
            "neuraltree_sandbox_diff",
            "neuraltree_sandbox_apply",
            "neuraltree_sandbox_destroy",
        ]

        for name in expected:
            assert name in tool_names, f"Missing tool: {name}"

        assert len(tools) >= len(expected)

    def test_tool_count(self):
        """Should have exactly 20 tools."""
        from neuraltree_mcp.server import mcp
        tools = asyncio.run(mcp.list_tools())
        assert len(tools) == 20


class TestToolSchemas:
    def test_scan_has_description(self):
        """neuraltree_scan should have a description."""
        from neuraltree_mcp.server import mcp
        tools = asyncio.run(mcp.list_tools())
        scan = [t for t in tools if t.name == "neuraltree_scan"][0]
        assert scan.description is not None
        assert "filesystem" in scan.description.lower() or "inventory" in scan.description.lower()

    def test_trace_has_description(self):
        """neuraltree_trace should have a description."""
        from neuraltree_mcp.server import mcp
        tools = asyncio.run(mcp.list_tools())
        trace = [t for t in tools if t.name == "neuraltree_trace"][0]
        assert trace.description is not None
        assert "trace" in trace.description.lower() or "reference" in trace.description.lower()
