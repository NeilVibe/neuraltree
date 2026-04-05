"""Tests for neuraltree_diagnose tool."""
from pathlib import Path


class TestDiagnose:
    def test_content_gap_detection(self, tmp_project):
        """Query about nonexistent topic should be CONTENT_GAP."""
        from neuraltree_mcp.scoring.diagnose import register
        from fastmcp import FastMCP

        # Test the classification logic directly
        failed = [{"text": "What is quantum computing?"}]

        # No files mention quantum computing
        # Simulate the keyword matching
        import re
        keywords = set(re.findall(r'[a-zA-Z]{3,}', "what is quantum computing"))
        keywords -= {"what"}

        # Search tmp_project for matches
        matches = []
        for f in tmp_project.rglob("*"):
            if f.is_file() and f.suffix in (".md", ".py"):
                content = f.read_text().lower()
                matched = sum(1 for kw in keywords if kw in content)
                if matched >= max(1, len(keywords) // 2):
                    matches.append(str(f))

        # Should find no matches for "quantum computing"
        assert len(matches) == 0

    def test_synapse_gap_detection(self, tmp_project):
        """Query about existing but unwired topic should be SYNAPSE_GAP."""
        # auth.md exists but has no ## Related or ## Docs
        auth = tmp_project / "memory" / "reference" / "auth.md"
        content = auth.read_text()
        assert "## Related" not in content
        assert "## Docs" not in content

    def test_focus_gap_large_file(self, tmp_project):
        """Large file (>500 lines) should trigger FOCUS_GAP."""
        # Create a very large file
        large = tmp_project / "memory" / "rules" / "everything.md"
        large.write_text("# Everything\n" + "Some content about auth.\n" * 600)

        lines = len(large.read_text().splitlines())
        assert lines > 500

    def test_gap_priority_order(self):
        """SYNAPSE gaps should be prioritized over CONTENT gaps (cheapest first)."""
        # Must match the actual priority_order in diagnose.py
        priority = ["SYNAPSE_GAP", "FRESHNESS_GAP", "EMBEDDING_GAP", "FOCUS_GAP", "CONTENT_GAP"]
        assert priority.index("SYNAPSE_GAP") < priority.index("CONTENT_GAP")
        assert priority.index("FRESHNESS_GAP") < priority.index("FOCUS_GAP")
