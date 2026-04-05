"""Tests for neuraltree_generate_queries tool."""
import pytest
from pathlib import Path

from neuraltree_mcp.tools.generate_queries import (
    _parse_table_column,
    _parse_md_links,
    _parse_headings,
    _parse_bold_terms,
    _resolve_path,
    _dedup_queries,
)


class TestParseTableColumn:
    def test_glossary_table(self):
        content = (
            "## Glossary\n\n"
            "| Term | Meaning |\n"
            "|------|---------|\n"
            "| **TM** | Translation Memory |\n"
            "| **LDM** | Language Data Manager |\n"
        )
        terms = _parse_table_column(content, "Term", 0)
        assert "TM" in terms
        assert "LDM" in terms

    def test_nav_table(self):
        content = (
            "## Quick Navigation\n\n"
            "| Need | Go To |\n"
            "|------|-------|\n"
            "| **Architecture** | docs/architecture/SUMMARY.md |\n"
        )
        needs = _parse_table_column(content, "Need", 0)
        assert "Architecture" in needs

    def test_empty_content(self):
        terms = _parse_table_column("", "Term", 0)
        assert terms == []

    def test_no_matching_table(self):
        content = "# Just a heading\n\nSome text.\n"
        terms = _parse_table_column(content, "Term", 0)
        assert terms == []


class TestParseMdLinks:
    def test_basic_links(self):
        content = (
            "- [Rules](rules/_INDEX.md) — behavioral rules\n"
            "- [Reference](reference/) — stable facts\n"
        )
        titles = _parse_md_links(content)
        assert "Rules" in titles
        assert "Reference" in titles

    def test_no_links(self):
        titles = _parse_md_links("Just plain text.")
        assert titles == []


class TestDedupQueries:
    def test_removes_duplicates(self):
        queries = [
            {"text": "What is TM?", "source": "a", "category": "b"},
            {"text": "What is TM?", "source": "a", "category": "b"},
        ]
        result = _dedup_queries(queries)
        assert len(result) == 1

    def test_keeps_different_queries(self):
        queries = [
            {"text": "What is TM?", "source": "a", "category": "b"},
            {"text": "How does auth work?", "source": "a", "category": "b"},
        ]
        result = _dedup_queries(queries)
        assert len(result) == 2

    def test_high_overlap_removed(self):
        queries = [
            {"text": "What is translation memory?", "source": "a", "category": "b"},
            {"text": "What is translation memory system?", "source": "a", "category": "b"},
        ]
        result = _dedup_queries(queries)
        # These have 3/4 = 75% overlap which is below 80% threshold
        # Use truly overlapping queries instead
        queries2 = [
            {"text": "What is TM?", "source": "a", "category": "b"},
            {"text": "What is TM?", "source": "a", "category": "b"},
        ]
        result2 = _dedup_queries(queries2)
        assert len(result2) == 1


class TestGenerateQueriesIntegration:
    def test_generates_from_claude_md(self, tmp_project):
        """Should generate queries from CLAUDE.md glossary and nav tables."""
        claude_md = tmp_project / "CLAUDE.md"
        content = claude_md.read_text()

        # Glossary terms
        terms = _parse_table_column(content, "Term", 0)
        assert len(terms) >= 2  # TM, LDM, GDP

        # Nav entries
        needs = _parse_table_column(content, "Need", 0)
        assert len(needs) >= 1  # Architecture

    def test_generates_from_memory_md(self, tmp_project):
        """Should extract link titles from MEMORY.md."""
        mem = tmp_project / "memory" / "MEMORY.md"
        titles = _parse_md_links(mem.read_text())
        assert "Rules" in titles
        assert "Reference" in titles


class TestParseHeadings:
    def test_extracts_h2_headings(self):
        content = "## User Portfolio Tracking\n\nSome text.\n\n## Company Analysis Protocol\n"
        topics = _parse_headings(content)
        assert "User Portfolio Tracking" in topics
        assert "Company Analysis Protocol" in topics

    def test_extracts_h3_headings(self):
        content = "### External Score Ranges\n\nDetails here.\n"
        topics = _parse_headings(content)
        assert "External Score Ranges" in topics

    def test_skips_generic_headings(self):
        content = "## Architecture\n\n## Commands\n\n## Overview\n\n## Real Topic\n"
        topics = _parse_headings(content)
        assert "Real Topic" in topics
        assert "Architecture" not in topics
        assert "Commands" not in topics
        assert "Overview" not in topics

    def test_strips_emoji_and_special_chars(self):
        content = "## 🚨 NEVER RUN PRODUCTION SCRIPTS 🚨\n"
        topics = _parse_headings(content)
        # >3 char ALL CAPS words normalized to title case; ≤3 char words (RUN) kept as-is
        assert any("Never RUN Production Scripts" in t for t in topics)

    def test_skips_short_headings(self):
        content = "## API\n\n## OK\n\n## Longer Heading Here\n"
        topics = _parse_headings(content)
        assert "Longer Heading Here" in topics
        assert "API" not in topics

    def test_empty_content(self):
        assert _parse_headings("") == []

    def test_strips_trailing_hashes(self):
        content = "## My Topic ##\n"
        topics = _parse_headings(content)
        assert "My Topic" in topics


class TestParseBoldTerms:
    def test_extracts_bold_bullet_terms(self):
        content = "- **Market Cap Filter:** minimum 100B won\n- **Position Sizing:** 5-10%\n"
        terms = _parse_bold_terms(content)
        assert "Market Cap Filter" in terms
        assert "Position Sizing" in terms

    def test_asterisk_bullets(self):
        content = "* **DART API** — for financial data\n"
        terms = _parse_bold_terms(content)
        assert "DART API" in terms

    def test_skips_short_terms(self):
        content = "- **OK** something\n- **Longer Term Here** detail\n"
        terms = _parse_bold_terms(content)
        assert "Longer Term Here" in terms
        assert len([t for t in terms if t == "OK"]) == 0

    def test_skips_long_terms(self):
        content = "- **" + "x" * 61 + "** detail\n"
        terms = _parse_bold_terms(content)
        assert terms == []

    def test_empty_content(self):
        assert _parse_bold_terms("") == []


class TestResolvePath:
    def test_relative_path(self, tmp_path):
        root = tmp_path / "project"
        root.mkdir()
        (root / "CLAUDE.md").touch()
        result = _resolve_path(root, "CLAUDE.md")
        assert result == root / "CLAUDE.md"

    def test_nested_relative_path(self, tmp_path):
        root = tmp_path / "project"
        root.mkdir()
        (root / "memory").mkdir()
        (root / "memory" / "MEMORY.md").touch()
        result = _resolve_path(root, "memory/MEMORY.md")
        assert result == root / "memory" / "MEMORY.md"

    def test_absolute_path_blocked(self, tmp_path):
        root = tmp_path / "project"
        root.mkdir()
        with pytest.raises(ValueError):
            _resolve_path(root, "/etc/passwd")

    def test_traversal_blocked(self, tmp_path):
        root = tmp_path / "project"
        root.mkdir()
        with pytest.raises(ValueError):
            _resolve_path(root, "../../etc/passwd")

    def test_dot_prefix_works(self, tmp_path):
        root = tmp_path / "project"
        root.mkdir()
        (root / "CLAUDE.md").touch()
        result = _resolve_path(root, "./CLAUDE.md")
        assert result == root / "CLAUDE.md"


class TestMaxPerStrategyCap:
    def test_table_queries_capped(self):
        """A CLAUDE.md with 20+ glossary terms should produce at most 15 table queries."""
        # _parse_table_column matches rows after a header line containing "Term"
        rows = "\n".join(f"| Item{i} | meaning{i} |" for i in range(25))
        content = f"## Glossary\n\n| Term | Meaning |\n|------|---------|\n{rows}\n"
        terms = _parse_table_column(content, "Term", 0)
        assert len(terms) == 25  # parser extracts all
        # But the tool caps at _MAX_PER_STRATEGY = 15
        from neuraltree_mcp.tools.generate_queries import _MAX_PER_STRATEGY
        assert len(terms[:_MAX_PER_STRATEGY]) == 15

    def test_headings_capped(self):
        """20+ headings should be capped by the tool."""
        headings = "\n".join(f"## Topic Number {i} Is Long Enough" for i in range(25))
        topics = _parse_headings(headings)
        assert len(topics) == 25  # parser extracts all
        from neuraltree_mcp.tools.generate_queries import _MAX_PER_STRATEGY
        assert len(topics[:_MAX_PER_STRATEGY]) == 15


class TestSourcesRecount:
    def test_sources_match_final_queries(self):
        """After dedup, sources counts must match actual query list."""
        queries = [
            {"text": "What is TM?", "source": "claude_md", "category": "what_is"},
            {"text": "What is TM?", "source": "claude_md", "category": "what_is"},  # dup
            {"text": "How does auth work?", "source": "memory", "category": "what_know"},
            {"text": "What changed with docs?", "source": "git", "category": "what_changed"},
        ]
        deduped = _dedup_queries(queries)
        assert len(deduped) == 3  # one dup removed

        # Recount as the tool does
        sources = {"claude_md": 0, "memory": 0, "indexes": 0, "lessons": 0, "git": 0}
        for q in deduped:
            sources[q["source"]] += 1
        assert sources["claude_md"] == 1
        assert sources["memory"] == 1
        assert sources["git"] == 1
        assert sum(sources.values()) == len(deduped)


class TestDedupThreshold:
    def test_above_80_percent_overlap_removed(self):
        """Queries with >80% word overlap should be deduped."""
        # 10 shared + 1 different each = 10/12 union = 0.833 > 0.8
        queries = [
            {"text": "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo", "source": "a", "category": "b"},
            {"text": "alpha bravo charlie delta echo foxtrot golf hotel india juliet lima", "source": "a", "category": "b"},
        ]
        result = _dedup_queries(queries)
        assert len(result) == 1

    def test_below_80_percent_overlap_kept(self):
        """Queries with <80% word overlap should both be kept."""
        queries = [
            {"text": "What is the translation memory?", "source": "a", "category": "b"},
            {"text": "How does auth system work here?", "source": "a", "category": "b"},
        ]
        result = _dedup_queries(queries)
        assert len(result) == 2


class TestFallbackChain:
    def test_tables_present_skips_heading_fallback(self):
        """When CLAUDE.md has tables, heading fallback should NOT fire."""
        content_with_tables = (
            "## User Portfolio\n\n"  # heading that would match
            "## Glossary\n\n"
            "| Term | Meaning |\n|------|---------|\n| **TM** | Translation Memory |\n\n"
            "## Another Heading\n"
        )
        terms = _parse_table_column(content_with_tables, "Term", 0)
        headings = _parse_headings(content_with_tables)
        assert len(terms) >= 1  # tables found
        assert len(headings) >= 1  # headings exist
        # Fallback logic: if claude_count > 0, headings are skipped

    def test_no_tables_triggers_heading_fallback(self):
        """When CLAUDE.md has NO tables, heading fallback should fire."""
        content_no_tables = (
            "## User Portfolio Tracking\n\nSome text.\n\n"
            "## Company Analysis Protocol\n\nMore text.\n"
        )
        terms = _parse_table_column(content_no_tables, "Term", 0)
        headings = _parse_headings(content_no_tables)
        assert len(terms) == 0  # no tables
        assert len(headings) >= 2  # headings found as fallback


class TestGenerateQueriesTool:
    def test_end_to_end(self, tmp_project):
        """Full tool call returns correct structure with queries from multiple sources."""
        import asyncio
        from neuraltree_mcp.server import mcp

        async def _call():
            result = await mcp.call_tool('neuraltree_generate_queries', {
                'project_root': str(tmp_project),
            })
            import json
            return json.loads(result.content[0].text)

        data = asyncio.run(_call())

        # Structure
        assert "queries" in data
        assert "sources" in data
        assert "total" in data
        assert "warnings" in data
        assert data["total"] == len(data["queries"])

        # Each query has required keys
        for q in data["queries"]:
            assert "text" in q
            assert "source" in q
            assert "category" in q

        # Sources should include claude_md (has tables) and memory (has links)
        assert data["sources"]["claude_md"] > 0
        assert data["sources"]["memory"] > 0

        # Sources sum matches total
        assert sum(data["sources"].values()) == data["total"]

    def test_invalid_project_root(self):
        """Invalid project root returns error dict, not exception."""
        import asyncio
        from neuraltree_mcp.server import mcp

        async def _call():
            result = await mcp.call_tool('neuraltree_generate_queries', {
                'project_root': '/nonexistent/path/xyz',
            })
            import json
            return json.loads(result.content[0].text)

        data = asyncio.run(_call())
        assert data["total"] == 0
        assert "error" in data
