"""Tests for neuraltree_wiki_lint tool — wiki health checker."""
import json
import time
from pathlib import Path

import pytest

from neuraltree_mcp.tools.wiki_lint import (
    _check_broken_links,
    _check_freshness,
    _check_inbound_links,
    _collect_md_files,
    _extract_links,
    _is_entry_point,
    _is_in_archive,
    _resolve_link,
    register,
)


@pytest.fixture
def mcp_with_lint():
    from fastmcp import FastMCP

    mcp = FastMCP("test")
    register(mcp)
    return mcp


@pytest.fixture
def wiki_project(tmp_path):
    """Create a mini wiki project for testing."""
    # Index page linking to two concepts
    index = tmp_path / "_INDEX.md"
    index.write_text(
        "# Index\n\n"
        "- [Concept A](concept-a.md)\n"
        "- [Concept B](concept-b.md)\n"
        "- [Broken Link](nonexistent.md)\n"
    )

    # Concept A links to B
    a = tmp_path / "concept-a.md"
    a.write_text(
        "---\nproject: test\n---\n\n"
        "# Concept A\n\n"
        "Related: [Concept B](concept-b.md)\n"
    )

    # Concept B links back to A
    b = tmp_path / "concept-b.md"
    b.write_text(
        "---\nproject: test\n---\n\n"
        "# Concept B\n\n"
        "See also [Concept A](concept-a.md)\n"
    )

    # Orphan page (nothing links to it)
    orphan = tmp_path / "orphan.md"
    orphan.write_text("# Orphan Page\n\nNobody links here.\n")

    return tmp_path


# --- Link extraction tests ---


class TestExtractLinks:
    def test_markdown_links(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("[foo](bar.md)\n[baz](sub/qux.md)\n")
        links = _extract_links(f)
        assert len(links) == 2
        assert links[0]["target"] == "bar.md"
        assert links[0]["type"] == "markdown"
        assert links[1]["target"] == "sub/qux.md"

    def test_wikilinks(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("See [[Concept A]] and [[Concept B|alias]]\n")
        links = _extract_links(f)
        assert len(links) == 2
        assert links[0]["target"] == "Concept A"
        assert links[1]["target"] == "Concept B"

    def test_skips_external_urls(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text(
            "[ext](https://example.com)\n"
            "[local](file.md)\n"
            "[anchor](#section)\n"
            "[mail](mailto:x@y.com)\n"
        )
        links = _extract_links(f)
        assert len(links) == 1
        assert links[0]["target"] == "file.md"

    def test_strips_anchors(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("[link](file.md#section)\n")
        links = _extract_links(f)
        assert links[0]["target"] == "file.md"

    def test_line_numbers(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("line 1\n[link](a.md)\nline 3\n[link2](b.md)\n")
        links = _extract_links(f)
        assert links[0]["line"] == 2
        assert links[1]["line"] == 4

    def test_empty_file(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("")
        assert _extract_links(f) == []


# --- Link resolution tests ---


class TestResolveLink:
    def test_relative_to_source(self, tmp_path):
        target_file = tmp_path / "sub" / "target.md"
        target_file.parent.mkdir()
        target_file.write_text("x")
        source = tmp_path / "sub" / "source.md"
        result = _resolve_link(source, "target.md", tmp_path)
        assert result == target_file.resolve()

    def test_adds_md_extension(self, tmp_path):
        target_file = tmp_path / "target.md"
        target_file.write_text("x")
        source = tmp_path / "source.md"
        result = _resolve_link(source, "target", tmp_path)
        assert result == target_file.resolve()

    def test_relative_to_root(self, tmp_path):
        target_file = tmp_path / "docs" / "target.md"
        target_file.parent.mkdir()
        target_file.write_text("x")
        source = tmp_path / "other" / "source.md"
        source.parent.mkdir()
        result = _resolve_link(source, "docs/target.md", tmp_path)
        assert result == target_file.resolve()

    def test_returns_none_for_missing(self, tmp_path):
        source = tmp_path / "source.md"
        result = _resolve_link(source, "nonexistent.md", tmp_path)
        assert result is None


# --- Broken links tests ---


class TestBrokenLinks:
    def test_finds_broken_link(self, wiki_project):
        files = _collect_md_files(wiki_project)
        broken = _check_broken_links(files, wiki_project)
        assert len(broken) == 1
        assert broken[0]["target"] == "nonexistent.md"
        assert broken[0]["file"] == "_INDEX.md"

    def test_no_broken_links(self, tmp_path):
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("[b](b.md)\n")
        b.write_text("[a](a.md)\n")
        files = _collect_md_files(tmp_path)
        broken = _check_broken_links(files, tmp_path)
        assert broken == []


# --- Inbound links tests ---


class TestInboundLinks:
    def test_counts_inbound(self, wiki_project):
        files = _collect_md_files(wiki_project)
        inbound = _check_inbound_links(files, wiki_project)
        # concept-a.md is linked from _INDEX.md and concept-b.md
        assert len(inbound["concept-a.md"]) == 2
        # concept-b.md is linked from _INDEX.md and concept-a.md
        assert len(inbound["concept-b.md"]) == 2
        # orphan.md has zero inbound
        assert len(inbound["orphan.md"]) == 0

    def test_no_self_links(self, tmp_path):
        f = tmp_path / "self.md"
        f.write_text("[me](self.md)\n")
        files = _collect_md_files(tmp_path)
        inbound = _check_inbound_links(files, tmp_path)
        assert len(inbound["self.md"]) == 0


# --- Freshness tests ---


class TestFreshness:
    def test_finds_stale_files(self, wiki_project):
        # Make orphan.md appear old
        old_time = time.time() - (60 * 86400)  # 60 days ago
        import os

        os.utime(wiki_project / "orphan.md", (old_time, old_time))
        files = _collect_md_files(wiki_project)
        stale = _check_freshness(files, wiki_project, max_age_days=30)
        stale_files = [s["file"] for s in stale]
        assert "orphan.md" in stale_files

    def test_fresh_files_not_flagged(self, wiki_project):
        files = _collect_md_files(wiki_project)
        stale = _check_freshness(files, wiki_project, max_age_days=30)
        # All files just created, should be fresh
        # (orphan.md was just created too, so all fresh)
        assert len(stale) == 0


# --- Full tool tests ---


class TestWikiLintTool:
    @pytest.mark.asyncio
    async def test_basic_lint(self, mcp_with_lint, wiki_project):
        result = await mcp_with_lint.call_tool(
            "neuraltree_wiki_lint",
            {"project_root": str(wiki_project)},
        )
        data = json.loads(result.content[0].text)
        assert data["total_pages"] == 4
        assert data["total_broken"] == 1  # nonexistent.md
        assert data["total_orphans"] == 1  # orphan.md only (_INDEX.md auto-excluded as entry point)
        assert "health_score" in data
        assert 0 <= data["health_score"] <= 100

    @pytest.mark.asyncio
    async def test_healthy_wiki(self, mcp_with_lint, tmp_path):
        # All files linked to each other, no broken links
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("[b](b.md)\n")
        b.write_text("[a](a.md)\n")
        result = await mcp_with_lint.call_tool(
            "neuraltree_wiki_lint",
            {"project_root": str(tmp_path)},
        )
        data = json.loads(result.content[0].text)
        assert data["total_broken"] == 0
        assert data["total_orphans"] == 0
        assert data["health_score"] >= 80

    @pytest.mark.asyncio
    async def test_empty_project(self, mcp_with_lint, tmp_path):
        result = await mcp_with_lint.call_tool(
            "neuraltree_wiki_lint",
            {"project_root": str(tmp_path)},
        )
        data = json.loads(result.content[0].text)
        assert data["total_pages"] == 0
        assert "No markdown files found" in data["warnings"]

    @pytest.mark.asyncio
    async def test_invalid_root(self, mcp_with_lint):
        result = await mcp_with_lint.call_tool(
            "neuraltree_wiki_lint",
            {"project_root": "/nonexistent/xyz"},
        )
        data = json.loads(result.content[0].text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_cross_ref_density(self, mcp_with_lint, wiki_project):
        result = await mcp_with_lint.call_tool(
            "neuraltree_wiki_lint",
            {"project_root": str(wiki_project)},
        )
        data = json.loads(result.content[0].text)
        # 4 pages, concept-a has 2 inbound, concept-b has 2, index has 2 (from a and b), orphan has 0
        # Total inbound = 6, density = 6/4 = 1.5
        assert data["cross_ref_density"] > 0

    @pytest.mark.asyncio
    async def test_trunk_auto_detection(self, mcp_with_lint, wiki_project):
        """Entry points like _INDEX.md are auto-excluded from orphans."""
        result = await mcp_with_lint.call_tool(
            "neuraltree_wiki_lint",
            {"project_root": str(wiki_project)},
        )
        data = json.loads(result.content[0].text)
        assert "_INDEX.md" in data["trunk_files"]
        orphan_files = [o["file"] for o in data["orphan_pages"]]
        assert "_INDEX.md" not in orphan_files
        assert "orphan.md" in orphan_files

    @pytest.mark.asyncio
    async def test_trunk_paths_override(self, mcp_with_lint, wiki_project):
        """Explicit trunk_paths excludes specified files from orphan detection."""
        result = await mcp_with_lint.call_tool(
            "neuraltree_wiki_lint",
            {
                "project_root": str(wiki_project),
                "trunk_paths": ["_INDEX.md", "orphan.md"],
            },
        )
        data = json.loads(result.content[0].text)
        assert data["total_orphans"] == 0
        assert "orphan.md" in data["trunk_files"]

    @pytest.mark.asyncio
    async def test_archive_auto_exclusion(self, mcp_with_lint, tmp_path):
        """Files in archive/ directories are auto-excluded from orphans."""
        # Create a normal file and an archived file
        normal = tmp_path / "normal.md"
        normal.write_text("# Normal\nNo links here.\n")

        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()
        archived = archive_dir / "old-doc.md"
        archived.write_text("# Old Doc\nArchived content.\n")

        result = await mcp_with_lint.call_tool(
            "neuraltree_wiki_lint",
            {"project_root": str(tmp_path)},
        )
        data = json.loads(result.content[0].text)
        orphan_files = [o["file"] for o in data["orphan_pages"]]
        assert "normal.md" in orphan_files
        assert "archive/old-doc.md" not in orphan_files

    @pytest.mark.asyncio
    async def test_exclude_dirs_param(self, mcp_with_lint, tmp_path):
        """Custom exclude_dirs skips those directories from orphan detection."""
        custom_dir = tmp_path / "legacy"
        custom_dir.mkdir()
        legacy = custom_dir / "old.md"
        legacy.write_text("# Legacy\n")

        result = await mcp_with_lint.call_tool(
            "neuraltree_wiki_lint",
            {
                "project_root": str(tmp_path),
                "exclude_dirs": ["legacy"],
            },
        )
        data = json.loads(result.content[0].text)
        orphan_files = [o["file"] for o in data["orphan_pages"]]
        assert "legacy/old.md" not in orphan_files


# --- Helper function tests ---


class TestHelpers:
    def test_is_entry_point(self):
        assert _is_entry_point("README.md") is True
        assert _is_entry_point("CLAUDE.md") is True
        assert _is_entry_point("_INDEX.md") is True
        assert _is_entry_point("docs/README.md") is True
        assert _is_entry_point("random-file.md") is False

    def test_is_in_archive(self):
        assert _is_in_archive("archive/old.md") is True
        assert _is_in_archive("docs/archive/session5.md") is True
        assert _is_in_archive("old/stuff.md") is True
        assert _is_in_archive("deprecated/legacy.md") is True
        assert _is_in_archive("docs/concepts/foo.md") is False
        assert _is_in_archive("active/current.md") is False
