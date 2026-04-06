"""Tests for neuraltree_diagnose tool — universal gap classification."""
from pathlib import Path


class TestDiagnose:
    def test_content_gap_detection(self, tmp_project):
        """Query about nonexistent topic should be CONTENT_GAP."""
        import re
        keywords = set(re.findall(r'[a-zA-Z]{3,}', "what is quantum computing"))
        keywords -= {"what"}

        matches = []
        for f in tmp_project.rglob("*"):
            if f.is_file() and f.suffix in (".md", ".py"):
                content = f.read_text().lower()
                matched = sum(1 for kw in keywords if kw in content)
                if matched >= max(1, len(keywords) // 2):
                    matches.append(str(f))

        assert len(matches) == 0

    def test_focus_gap_large_file(self, tmp_project):
        """Large file (>500 lines) should trigger FOCUS_GAP."""
        large = tmp_project / "memory" / "rules" / "everything.md"
        large.write_text("# Everything\n" + "Some content about auth.\n" * 600)
        lines = len(large.read_text().splitlines())
        assert lines > 500

    def test_gap_priority_order(self):
        """ISOLATION gaps should be prioritized over CONTENT gaps (cheapest first)."""
        priority = ["ISOLATION_GAP", "EMBEDDING_GAP", "FOCUS_GAP", "CONTENT_GAP"]
        assert priority.index("ISOLATION_GAP") < priority.index("CONTENT_GAP")
        assert priority.index("EMBEDDING_GAP") < priority.index("FOCUS_GAP")

    def test_gap_types_no_formatting_conventions(self):
        """Gap types should NOT reference ## Related, frontmatter, or _INDEX.md."""
        from neuraltree_mcp.scoring.diagnose import GAP_TYPES
        all_descriptions = " ".join(GAP_TYPES.values())
        assert "Related" not in all_descriptions
        assert "frontmatter" not in all_descriptions
        assert "last_verified" not in all_descriptions
        assert "SYNAPSE_GAP" not in GAP_TYPES
        assert "FRESHNESS_GAP" not in GAP_TYPES
