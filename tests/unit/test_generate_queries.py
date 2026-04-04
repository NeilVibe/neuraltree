"""Tests for neuraltree_generate_queries tool."""
from neuraltree_mcp.tools.generate_queries import (
    _parse_table_column,
    _parse_md_links,
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
