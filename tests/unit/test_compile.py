"""Tests for neuraltree_compile and neuraltree_wiki_read tools."""
import json
import os
from pathlib import Path

import pytest

from tests.conftest import call_tool


class TestCompile:
    """Tests for neuraltree_compile tool."""

    def test_compile_basic(self, tmp_project):
        """Compile a basic wiki page."""
        result = call_tool("neuraltree_compile", {
            "topic": "Authentication",
            "content": (
                "---\n"
                "name: Authentication\n"
                "description: How auth works in this project\n"
                "source_count: 2\n"
                "last_compiled: 2026-04-08\n"
                "---\n\n"
                "# Authentication\n\n"
                "LAN auth uses IP-lock admin.\n\n"
                "## Sources\n\n"
                "- `memory/reference/auth.md`\n\n"
                "## Related\n\n"
                "- [Overview](overview.md)\n"
            ),
            "sources": ["memory/reference/auth.md", "server/main.py"],
            "project_root": str(tmp_project),
        })
        assert "error" not in result
        assert result["slug"] == "authentication"
        assert result["sources_count"] == 2
        assert result["index_updated"] is True
        assert result["log_appended"] is True

        # Verify file was written
        page = tmp_project / ".neuraltree" / "wiki" / "authentication.md"
        assert page.exists()
        content = page.read_text()
        assert "LAN auth uses IP-lock admin" in content

    def test_compile_creates_index(self, tmp_project):
        """Compile creates _INDEX.md."""
        call_tool("neuraltree_compile", {
            "topic": "Auth",
            "content": "# Auth\nBasic auth page.",
            "sources": ["auth.md"],
            "project_root": str(tmp_project),
        })
        idx = tmp_project / ".neuraltree" / "wiki" / "_INDEX.md"
        assert idx.exists()
        content = idx.read_text()
        assert "Auth" in content
        assert "1 compiled pages" in content

    def test_compile_creates_log(self, tmp_project):
        """Compile appends to log.md."""
        call_tool("neuraltree_compile", {
            "topic": "Database",
            "content": "# Database\nPG config.",
            "sources": ["config/pg.conf"],
            "project_root": str(tmp_project),
        })
        log = tmp_project / ".neuraltree" / "wiki" / "log.md"
        assert log.exists()
        content = log.read_text()
        assert "Database" in content
        assert "Sources: 1 files" in content

    def test_compile_multiple_pages(self, tmp_project):
        """Compile multiple pages, index tracks all."""
        for topic in ["Auth", "Database", "Testing"]:
            call_tool("neuraltree_compile", {
                "topic": topic,
                "content": f"# {topic}\nContent for {topic}.",
                "sources": [f"{topic.lower()}.md"],
                "project_root": str(tmp_project),
            })
        idx = tmp_project / ".neuraltree" / "wiki" / "_INDEX.md"
        content = idx.read_text()
        assert "3 compiled pages" in content
        assert "Auth" in content
        assert "Database" in content
        assert "Testing" in content

    def test_compile_update_existing(self, tmp_project):
        """update_existing=True overwrites page."""
        call_tool("neuraltree_compile", {
            "topic": "Auth",
            "content": "# Auth\nVersion 1.",
            "sources": ["a.md"],
            "project_root": str(tmp_project),
        })
        result = call_tool("neuraltree_compile", {
            "topic": "Auth",
            "content": "# Auth\nVersion 2.",
            "sources": ["a.md", "b.md"],
            "project_root": str(tmp_project),
            "update_existing": True,
        })
        assert "error" not in result
        page = tmp_project / ".neuraltree" / "wiki" / "auth.md"
        assert "Version 2" in page.read_text()

    def test_compile_no_overwrite(self, tmp_project):
        """update_existing=False errors on conflict."""
        call_tool("neuraltree_compile", {
            "topic": "Auth",
            "content": "# Auth\nV1.",
            "sources": ["a.md"],
            "project_root": str(tmp_project),
        })
        result = call_tool("neuraltree_compile", {
            "topic": "Auth",
            "content": "# Auth\nV2.",
            "sources": ["a.md"],
            "project_root": str(tmp_project),
            "update_existing": False,
        })
        assert "error" in result
        assert "already exists" in result["error"]

    def test_compile_injects_frontmatter(self, tmp_project):
        """Content without frontmatter gets it injected."""
        call_tool("neuraltree_compile", {
            "topic": "Quick Note",
            "content": "# Quick Note\nJust a note.",
            "sources": [],
            "project_root": str(tmp_project),
        })
        page = tmp_project / ".neuraltree" / "wiki" / "quick-note.md"
        content = page.read_text()
        assert content.startswith("---\n")
        assert "name: Quick Note" in content
        assert "source_count: 0" in content

    def test_compile_empty_topic_error(self, tmp_project):
        """Empty topic returns error."""
        result = call_tool("neuraltree_compile", {
            "topic": "",
            "content": "stuff",
            "sources": [],
            "project_root": str(tmp_project),
        })
        assert "error" in result
        assert "topic is required" in result["error"]

    def test_compile_empty_content_error(self, tmp_project):
        """Empty content returns error."""
        result = call_tool("neuraltree_compile", {
            "topic": "Auth",
            "content": "",
            "sources": [],
            "project_root": str(tmp_project),
        })
        assert "error" in result
        assert "content is required" in result["error"]

    def test_compile_slugify(self, tmp_project):
        """Topics with special chars get slugified."""
        result = call_tool("neuraltree_compile", {
            "topic": "CI/CD Pipeline & Deployment",
            "content": "# CI/CD\nPipeline details.",
            "sources": [],
            "project_root": str(tmp_project),
        })
        assert result["slug"] == "ci-cd-pipeline-deployment"

    def test_compile_bad_root(self):
        """Invalid project root returns error."""
        result = call_tool("neuraltree_compile", {
            "topic": "Test",
            "content": "stuff",
            "sources": [],
            "project_root": "/nonexistent/path",
        })
        assert "error" in result

    def test_compile_whitespace_topic_error(self, tmp_project):
        """Whitespace-only topic returns error."""
        result = call_tool("neuraltree_compile", {
            "topic": "   ",
            "content": "stuff",
            "sources": [],
            "project_root": str(tmp_project),
        })
        assert "error" in result
        assert "topic is required" in result["error"]

    def test_compile_whitespace_content_error(self, tmp_project):
        """Whitespace-only content returns error."""
        result = call_tool("neuraltree_compile", {
            "topic": "Auth",
            "content": "   \n  ",
            "sources": [],
            "project_root": str(tmp_project),
        })
        assert "error" in result
        assert "content is required" in result["error"]

    def test_compile_path_traversal_topic(self, tmp_project):
        """Path traversal in topic is neutralized by slugify."""
        result = call_tool("neuraltree_compile", {
            "topic": "../../etc/passwd",
            "content": "# Safe\nContent.",
            "sources": [],
            "project_root": str(tmp_project),
        })
        assert "error" not in result
        assert result["slug"] == "etc-passwd"
        # Must NOT write outside wiki dir
        evil = tmp_project / "etc" / "passwd"
        assert not evil.exists()
        safe = tmp_project / ".neuraltree" / "wiki" / "etc-passwd.md"
        assert safe.exists()

    def test_compile_unicode_topic_falls_back(self, tmp_project):
        """Non-ASCII topic slugifies to 'untitled'."""
        result = call_tool("neuraltree_compile", {
            "topic": "認証システム",
            "content": "# Auth in Japanese\nContent.",
            "sources": [],
            "project_root": str(tmp_project),
        })
        assert "error" not in result
        assert result["slug"] == "untitled"

    def test_compile_log_operation_first_is_compile(self, tmp_project):
        """First compile logs 'compile', not 'update'."""
        call_tool("neuraltree_compile", {
            "topic": "NewPage",
            "content": "# New\nFirst time.",
            "sources": ["a.md"],
            "project_root": str(tmp_project),
        })
        log = tmp_project / ".neuraltree" / "wiki" / "log.md"
        content = log.read_text()
        assert "compile | NewPage" in content

    def test_compile_log_operation_second_is_update(self, tmp_project):
        """Second compile of same topic logs 'update'."""
        call_tool("neuraltree_compile", {
            "topic": "Auth",
            "content": "# Auth\nV1.",
            "sources": [],
            "project_root": str(tmp_project),
        })
        call_tool("neuraltree_compile", {
            "topic": "Auth",
            "content": "# Auth\nV2.",
            "sources": [],
            "project_root": str(tmp_project),
        })
        log = tmp_project / ".neuraltree" / "wiki" / "log.md"
        content = log.read_text()
        assert "compile | Auth" in content
        assert "update | Auth" in content

    def test_compile_update_keeps_single_index_entry(self, tmp_project):
        """Updating a page doesn't duplicate it in the index."""
        call_tool("neuraltree_compile", {
            "topic": "Auth",
            "content": "# Auth\nV1.",
            "sources": [],
            "project_root": str(tmp_project),
        })
        call_tool("neuraltree_compile", {
            "topic": "Auth",
            "content": "# Auth\nV2.",
            "sources": [],
            "project_root": str(tmp_project),
        })
        idx = tmp_project / ".neuraltree" / "wiki" / "_INDEX.md"
        content = idx.read_text()
        assert "1 compiled pages" in content

    def test_compile_log_accumulates(self, tmp_project):
        """Multiple compiles accumulate in log."""
        for topic in ["A", "B", "C"]:
            call_tool("neuraltree_compile", {
                "topic": topic,
                "content": f"# {topic}\nContent.",
                "sources": [],
                "project_root": str(tmp_project),
            })
        log = tmp_project / ".neuraltree" / "wiki" / "log.md"
        content = log.read_text()
        assert content.count("## [") == 3


class TestWikiRead:
    """Tests for neuraltree_wiki_read tool."""

    def test_read_empty(self, tmp_project):
        """No wiki returns empty state."""
        result = call_tool("neuraltree_wiki_read", {
            "project_root": str(tmp_project),
        })
        assert result["page_count"] == 0
        assert result["exists"] is False

    def test_read_after_compile(self, tmp_project):
        """Read after compile shows pages."""
        call_tool("neuraltree_compile", {
            "topic": "Auth",
            "content": "---\nname: Auth\ndescription: Auth system\nsource_count: 1\n---\n# Auth\nStuff.",
            "sources": ["auth.md"],
            "project_root": str(tmp_project),
        })
        call_tool("neuraltree_compile", {
            "topic": "Database",
            "content": "---\nname: Database\ndescription: DB layer\nsource_count: 2\n---\n# DB\nStuff.",
            "sources": ["db.md", "schema.md"],
            "project_root": str(tmp_project),
        })
        result = call_tool("neuraltree_wiki_read", {
            "project_root": str(tmp_project),
        })
        assert result["exists"] is True
        assert result["page_count"] == 2
        assert len(result["pages"]) == 2
        names = {p["name"] for p in result["pages"]}
        assert "Auth" in names
        assert "Database" in names
        assert "Wiki Index" in result["index_content"]

    def test_read_shows_log(self, tmp_project):
        """Read shows recent log entries."""
        call_tool("neuraltree_compile", {
            "topic": "Test Page",
            "content": "# Test\nContent.",
            "sources": ["test.md"],
            "project_root": str(tmp_project),
        })
        result = call_tool("neuraltree_wiki_read", {
            "project_root": str(tmp_project),
        })
        assert "Test Page" in result["recent_log"]

    def test_read_bad_root(self):
        """Invalid root returns error."""
        result = call_tool("neuraltree_wiki_read", {
            "project_root": "/nonexistent",
        })
        assert "error" in result
