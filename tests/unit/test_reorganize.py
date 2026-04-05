"""Tests for neuraltree reorganize tools: plan_move, plan_split, find_dead, generate_index."""
import asyncio
import json
from pathlib import Path

import pytest

from neuraltree_mcp.tools.reorganize import (
    _find_all_references,
    _compute_rewrites,
)
from neuraltree_mcp.scoring.diagnose import _viking_uri_matches_file


class TestVikingUriMatching:
    """Test segment-based Viking URI matching (prevents false positives)."""

    def test_exact_basename_match(self):
        uri = "viking://resources/newfin/docs/GUIDE.md/Section/chunk.md"
        assert _viking_uri_matches_file(uri, "docs/GUIDE.md") is True

    def test_basename_substring_no_match(self):
        """GUIDE.md should NOT match DEBUGGING_GUIDE.md."""
        uri = "viking://resources/newfin/docs/DEBUGGING_GUIDE.md/Section/chunk.md"
        assert _viking_uri_matches_file(uri, "docs/GUIDE.md") is False

    def test_full_relative_path_match(self):
        uri = "viking://resources/newfin/docs/guides/ML_GUIDE.md/overview.md"
        assert _viking_uri_matches_file(uri, "docs/guides/ML_GUIDE.md") is True

    def test_no_match(self):
        uri = "viking://resources/newfin/docs/SYSTEM_REVIEW.md/chunk.md"
        assert _viking_uri_matches_file(uri, "README.md") is False

    def test_readme_exact_segment(self):
        """README.md should match if it's an exact segment."""
        uri = "viking://resources/newfin/README.md/section/chunk.md"
        assert _viking_uri_matches_file(uri, "README.md") is True

    def test_readme_no_false_positive(self):
        """README.md should NOT match ML_README.md."""
        uri = "viking://resources/newfin/docs/ML_README.md/chunk.md"
        assert _viking_uri_matches_file(uri, "README.md") is False


class TestFindAllReferences:
    def test_finds_markdown_link_refs(self, tmp_project):
        refs, warnings = _find_all_references(tmp_project, "coding.md")
        ref_files = [r["file"] for r in refs]
        assert any("_INDEX.md" in f for f in ref_files)
        assert any("testing.md" in f for f in ref_files)

    def test_finds_backtick_refs(self, tmp_project):
        refs, warnings = _find_all_references(tmp_project, "server/main.py")
        ref_files = [r["file"] for r in refs]
        assert any("coding.md" in f for f in ref_files)

    def test_no_refs_for_orphan(self, tmp_project):
        refs, warnings = _find_all_references(tmp_project, "memory/reference/auth.md")
        assert isinstance(refs, list)

    def test_no_substring_false_positive(self, tmp_project):
        """auth.md should NOT match oauth.md in text."""
        # Create a file referencing oauth.md but not auth.md
        (tmp_project / "docs" / "oauth_notes.md").write_text(
            "# OAuth Notes\nSee [OAuth](oauth.md) for details.\n"
        )
        refs, warnings = _find_all_references(tmp_project, "auth.md")
        ref_files = [r["file"] for r in refs]
        # oauth_notes.md mentions "oauth.md" not "auth.md" — should not match
        assert not any("oauth_notes.md" in f for f in ref_files)


class TestComputeRewrites:
    def test_full_path_replacement(self):
        refs = [{"file": "index.md", "line": 5, "text": "- [Guide](docs/old.md)"}]
        rewrites = _compute_rewrites(refs, "docs/old.md", "docs/guides/new.md")
        assert len(rewrites) == 1
        assert rewrites[0]["new_text"] == "- [Guide](docs/guides/new.md)"

    def test_basename_replacement(self):
        refs = [{"file": "related.md", "line": 3, "text": "- [Old](old.md) — ref"}]
        rewrites = _compute_rewrites(refs, "memory/old.md", "archive/renamed.md")
        assert len(rewrites) == 1
        assert "renamed.md" in rewrites[0]["new_text"]

    def test_no_change_if_no_match(self):
        refs = [{"file": "other.md", "line": 1, "text": "unrelated content"}]
        rewrites = _compute_rewrites(refs, "docs/old.md", "docs/new.md")
        assert len(rewrites) == 0


class TestPlanMove:
    def test_basic_move_plan(self, tmp_project):
        result = asyncio.run(_call_tool("neuraltree_plan_move", {
            "source": "memory/rules/coding.md",
            "destination": "memory/archive/coding.md",
            "project_root": str(tmp_project),
        }))
        assert "error" not in result
        assert result["source"] == "memory/rules/coding.md"
        assert result["references_found"] > 0

    def test_move_with_rename_produces_rewrites(self, tmp_project):
        """When basename changes, rewrites should be generated."""
        result = asyncio.run(_call_tool("neuraltree_plan_move", {
            "source": "memory/rules/coding.md",
            "destination": "memory/archive/coding_rules_old.md",
            "project_root": str(tmp_project),
        }))
        assert "error" not in result
        assert result["references_found"] > 0
        assert len(result["rewrites"]) > 0  # basename changed so rewrites needed

    def test_nonexistent_source(self, tmp_project):
        result = asyncio.run(_call_tool("neuraltree_plan_move", {
            "source": "nonexistent.md",
            "destination": "archive/nonexistent.md",
            "project_root": str(tmp_project),
        }))
        assert "error" in result

    def test_path_traversal_blocked(self, tmp_project):
        result = asyncio.run(_call_tool("neuraltree_plan_move", {
            "source": "../../etc/passwd",
            "destination": "hacked.md",
            "project_root": str(tmp_project),
        }))
        assert "error" in result


class TestPlanSplit:
    def test_small_file_no_split(self, tmp_project):
        result = asyncio.run(_call_tool("neuraltree_plan_split", {
            "target": "memory/rules/coding.md",
            "project_root": str(tmp_project),
        }))
        assert result["needs_split"] is False

    def test_large_file_suggests_splits(self, tmp_project):
        # Create a large file with multiple sections
        large = tmp_project / "docs" / "MEGA.md"
        sections = []
        for i in range(10):
            sections.append(f"## Section {i}\n\n" + "Content line.\n" * 15)
        large.write_text("# Mega Guide\n\n" + "\n".join(sections))

        result = asyncio.run(_call_tool("neuraltree_plan_split", {
            "target": "docs/MEGA.md",
            "project_root": str(tmp_project),
            "max_lines": 80,
        }))
        assert result["needs_split"] is True
        assert result["section_count"] == 10
        assert len(result["splits"]) == 11  # 10 sections + 1 preamble
        assert all("filename" in s for s in result["splits"])
        assert "index_file" in result

    def test_nonexistent_file(self, tmp_project):
        result = asyncio.run(_call_tool("neuraltree_plan_split", {
            "target": "nonexistent.md",
            "project_root": str(tmp_project),
        }))
        assert "error" in result

    def test_no_headings_file(self, tmp_project):
        noheadings = tmp_project / "docs" / "flat.md"
        noheadings.write_text("Just a lot of text.\n" * 100)
        result = asyncio.run(_call_tool("neuraltree_plan_split", {
            "target": "docs/flat.md",
            "project_root": str(tmp_project),
        }))
        assert result["needs_split"] is True
        assert len(result["splits"]) == 0  # can't auto-split without headings


class TestFindDead:
    def test_finds_orphan_files(self, tmp_project):
        result = asyncio.run(_call_tool("neuraltree_find_dead", {
            "project_root": str(tmp_project),
        }))
        assert result["total_dead"] > 0
        dead_paths = [d["path"] for d in result["dead_files"]]
        # auth.md is orphaned (nothing references it)
        assert any("auth.md" in p for p in dead_paths)

    def test_wired_files_not_dead(self, tmp_project):
        result = asyncio.run(_call_tool("neuraltree_find_dead", {
            "project_root": str(tmp_project),
        }))
        dead_paths = [d["path"] for d in result["dead_files"]]
        # coding.md is referenced by _INDEX.md and testing.md — should NOT be dead
        assert not any(p.endswith("coding.md") for p in dead_paths)

    def test_trunk_files_never_dead(self, tmp_project):
        result = asyncio.run(_call_tool("neuraltree_find_dead", {
            "project_root": str(tmp_project),
        }))
        dead_paths = [d["path"] for d in result["dead_files"]]
        # Trunk files are always alive
        assert not any(p == "CLAUDE.md" for p in dead_paths)
        assert not any(p.endswith("MEMORY.md") for p in dead_paths)
        assert not any(p.endswith("_INDEX.md") for p in dead_paths)

    def test_dead_ratio(self, tmp_project):
        result = asyncio.run(_call_tool("neuraltree_find_dead", {
            "project_root": str(tmp_project),
        }))
        assert 0 <= result["dead_ratio"] <= 1.0
        assert result["total_dead"] <= result["total_knowledge"]


class TestGenerateIndex:
    def test_generates_for_rules_dir(self, tmp_project):
        result = asyncio.run(_call_tool("neuraltree_generate_index", {
            "directory": "memory/rules",
            "project_root": str(tmp_project),
        }))
        assert result["file_count"] == 2  # coding.md, testing.md (not _INDEX.md)
        assert "index_content" in result
        assert "coding" in result["index_content"].lower()
        assert "testing" in result["index_content"].lower()

    def test_entries_have_names(self, tmp_project):
        result = asyncio.run(_call_tool("neuraltree_generate_index", {
            "directory": "memory/rules",
            "project_root": str(tmp_project),
        }))
        for entry in result["entries"]:
            assert "name" in entry
            assert "file" in entry
            assert "description" in entry

    def test_extracts_frontmatter_name(self, tmp_project):
        result = asyncio.run(_call_tool("neuraltree_generate_index", {
            "directory": "memory/rules",
            "project_root": str(tmp_project),
        }))
        names = [e["name"] for e in result["entries"]]
        assert "Coding Rules" in names
        assert "Testing Rules" in names

    def test_nonexistent_dir(self, tmp_project):
        result = asyncio.run(_call_tool("neuraltree_generate_index", {
            "directory": "nonexistent",
            "project_root": str(tmp_project),
        }))
        assert "error" in result

    def test_empty_dir(self, tmp_project):
        (tmp_project / "empty_dir").mkdir()
        result = asyncio.run(_call_tool("neuraltree_generate_index", {
            "directory": "empty_dir",
            "project_root": str(tmp_project),
        }))
        assert result["file_count"] == 0


# Helper to call MCP tools in tests
async def _call_tool(name, args):
    from neuraltree_mcp.server import mcp
    result = await mcp.call_tool(name, args)
    return json.loads(result.content[0].text)
