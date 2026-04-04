"""Tests for neuraltree_score tool."""
from neuraltree_mcp.scoring.score import (
    _find_md_files,
    _has_section,
    _extract_related_targets,
    _parse_last_verified,
    WEIGHTS,
)


class TestHasSection:
    def test_finds_related(self):
        content = "## Content\nstuff\n\n## Related\n- link\n"
        assert _has_section(content, "Related") is True

    def test_no_related(self):
        content = "## Content\nstuff\n"
        assert _has_section(content, "Related") is False

    def test_inline_mention_not_counted(self):
        content = "Stuff about Related topics\n"
        assert _has_section(content, "Related") is False


class TestExtractRelatedTargets:
    def test_basic_targets(self):
        content = (
            "## Related\n"
            "- [testing.md](testing.md) — test patterns\n"
            "- [auth.md](../reference/auth.md) — auth model\n"
        )
        targets = _extract_related_targets(content)
        assert "testing.md" in targets
        assert "../reference/auth.md" in targets

    def test_stops_at_next_section(self):
        content = (
            "## Related\n"
            "- [a.md](a.md)\n"
            "## Docs\n"
            "- [b.md](b.md)\n"
        )
        targets = _extract_related_targets(content)
        assert "a.md" in targets
        assert "b.md" not in targets

    def test_no_related_section(self):
        content = "## Content\nstuff\n"
        targets = _extract_related_targets(content)
        assert targets == []


class TestParseLastVerified:
    def test_basic_date(self):
        content = "---\nlast_verified: 2026-04-04\n---\n"
        assert _parse_last_verified(content) == "2026-04-04"

    def test_no_date(self):
        content = "---\nname: Test\n---\n"
        assert _parse_last_verified(content) is None

    def test_date_in_body(self):
        content = "last_verified: 2026-01-01\n"
        assert _parse_last_verified(content) == "2026-01-01"


class TestWeights:
    def test_weights_sum_to_one(self):
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.001


class TestScoreIntegration:
    def test_find_md_files(self, tmp_project):
        files = _find_md_files(tmp_project)
        names = [f.name for f in files]
        assert "CLAUDE.md" in names
        assert "MEMORY.md" in names
        assert "coding.md" in names

    def test_synapse_coverage_partial(self, tmp_project):
        """coding.md and testing.md have ## Related, auth.md doesn't."""
        files = _find_md_files(tmp_project)
        wired = 0
        total = 0
        for f in files:
            content = f.read_text()
            if _has_section(content, "Related"):
                targets = _extract_related_targets(content)
                # Check if targets are alive
                alive = [t for t in targets if (f.parent / t).exists()]
                if alive:
                    wired += 1
            total += 1

        # At least coding.md and testing.md should be wired
        assert wired >= 2
        # Not all files are wired (auth.md, CLAUDE.md etc. aren't)
        assert wired < total

    def test_freshness_partial(self, tmp_project):
        """Some files have recent last_verified, some don't."""
        files = _find_md_files(tmp_project)
        fresh = 0
        for f in files:
            date = _parse_last_verified(f.read_text())
            if date and date >= "2026-03-05":  # within ~30 days of fixture
                fresh += 1

        # coding.md has 2026-04-04 (fresh), testing.md has 2026-03-01 (borderline)
        assert fresh >= 1
