"""Tests for neuraltree_find_dead — ensures summary_only/top_n keep output bounded."""
import json
from pathlib import Path

import pytest

from neuraltree_mcp.tools.reorganize.find_dead import register


@pytest.fixture
def mcp_with_find_dead():
    from fastmcp import FastMCP
    mcp = FastMCP("test")
    register(mcp)
    return mcp


@pytest.fixture
def project_with_dead_files(tmp_path):
    """Project with one referenced file and several dead files of varying sizes."""
    # Reference index points to ONE file only
    (tmp_path / "README.md").write_text("- [referenced](referenced.md)\n")
    (tmp_path / "referenced.md").write_text("# Referenced\n" + "line\n" * 5)

    # Dead files (no references, varying sizes)
    (tmp_path / "small-dead.md").write_text("# Small\n")
    (tmp_path / "medium-dead.md").write_text("# Medium\n" + "x\n" * 50)
    (tmp_path / "large-dead.md").write_text("# Large\n" + "y\n" * 200)
    (tmp_path / "huge-dead.md").write_text("# Huge\n" + "z\n" * 1000)
    return tmp_path


class TestSummaryAndTopN:
    @pytest.mark.asyncio
    async def test_summary_only_omits_dead_files_list(self, mcp_with_find_dead, project_with_dead_files):
        result = await mcp_with_find_dead.call_tool(
            "neuraltree_find_dead",
            {"project_root": str(project_with_dead_files), "summary_only": True},
        )
        data = json.loads(result.content[0].text)
        assert "dead_files" not in data
        assert data["total_dead"] == 4
        assert "dead_ratio" in data
        assert "likely_programmatic" in data

    @pytest.mark.asyncio
    async def test_top_n_returns_largest_files_first(self, mcp_with_find_dead, project_with_dead_files):
        result = await mcp_with_find_dead.call_tool(
            "neuraltree_find_dead",
            {"project_root": str(project_with_dead_files), "top_n": 2},
        )
        data = json.loads(result.content[0].text)
        assert data["total_dead"] == 4
        assert data["truncated_returned"] == 2
        assert data["truncated"] is True
        # Largest two should be huge + large
        names = [Path(d["path"]).name for d in data["dead_files"]]
        assert "huge-dead.md" in names
        assert "large-dead.md" in names

    @pytest.mark.asyncio
    async def test_default_returns_full_list_unchanged(self, mcp_with_find_dead, project_with_dead_files):
        """Backward compat — no params means same shape as before."""
        result = await mcp_with_find_dead.call_tool(
            "neuraltree_find_dead",
            {"project_root": str(project_with_dead_files)},
        )
        data = json.loads(result.content[0].text)
        assert "dead_files" in data
        assert len(data["dead_files"]) == 4
        assert "truncated" not in data
