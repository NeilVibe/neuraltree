"""Tests for neuraltree_score tool."""
import asyncio
import json

from neuraltree_mcp.scoring.score import (
    _find_md_files,
    _has_section,
    _extract_related_targets,
    _parse_last_verified,
    WEIGHTS,
)
from neuraltree_mcp.server import mcp


def call_tool(name: str, args: dict) -> dict:
    """Helper to call an MCP tool synchronously and parse the result."""
    result = asyncio.run(mcp.call_tool(name, args))
    if hasattr(result, "structured_content") and result.structured_content is not None:
        return result.structured_content
    if hasattr(result, "content"):
        for block in result.content:
            if hasattr(block, "text"):
                return json.loads(block.text)
    return result


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


class TestAdaptiveScoring:
    """Tests for adaptive=True scoring mode."""

    def test_adaptive_without_map_falls_back_to_static(self, tmp_project):
        """When adaptive=True but no knowledge_map.json exists, uses static thresholds."""
        result = call_tool("neuraltree_score", {
            "project_root": str(tmp_project),
            "adaptive": True,
        })

        assert "error" not in result
        assert "adaptive_context" in result
        assert result["adaptive_context"]["source"] == "static"
        assert result["adaptive_context"]["reason"] == "no knowledge_map"
        # Metrics should still be present and valid
        for key in ("hop_efficiency", "synapse_coverage", "dead_neuron_ratio", "freshness", "trunk_pressure"):
            assert isinstance(result["metrics"][key], (int, float))

    def test_adaptive_with_map_uses_project_stats(self, tmp_project):
        """When knowledge_map.json exists, adaptive_context.source == 'knowledge_map'."""
        nt_dir = tmp_project / ".neuraltree"
        nt_dir.mkdir()
        km = {
            "stats": {
                "total_files": 50,
                "avg_file_size": 150,
                "max_depth": 3,
            }
        }
        (nt_dir / "knowledge_map.json").write_text(json.dumps(km))

        result = call_tool("neuraltree_score", {
            "project_root": str(tmp_project),
            "adaptive": True,
        })

        assert "error" not in result
        assert "adaptive_context" in result
        ctx = result["adaptive_context"]
        assert ctx["source"] == "knowledge_map"
        assert "thresholds" in ctx
        assert ctx["thresholds"]["trunk_cap"] == 100  # 50 files < 100 threshold
        assert ctx["thresholds"]["file_size_cap"] == 300  # 2 * 150
        assert ctx["thresholds"]["freshness_days"] == 40  # base 30 + 10*(3-2)

    def test_adaptive_trunk_pressure_scales_with_project_size(self, tmp_project):
        """A 500-file project should have trunk_cap > 100."""
        nt_dir = tmp_project / ".neuraltree"
        nt_dir.mkdir()
        km = {
            "stats": {
                "total_files": 500,
                "avg_file_size": 200,
                "max_depth": 4,
            }
        }
        (nt_dir / "knowledge_map.json").write_text(json.dumps(km))

        result = call_tool("neuraltree_score", {
            "project_root": str(tmp_project),
            "adaptive": True,
        })

        ctx = result["adaptive_context"]
        assert ctx["source"] == "knowledge_map"
        # 500 files: 100 + 25 * (500 // 100) = 100 + 125 = 225
        assert ctx["thresholds"]["trunk_cap"] == 225
        assert ctx["thresholds"]["trunk_cap"] > 100
        # With trunk_cap=225, small trunk lines (~5) should get 1.0 pressure
        assert result["metrics"]["trunk_pressure"] == 1.0

    def test_default_mode_unchanged(self, tmp_project):
        """Calling without adaptive=True returns same result as before — no adaptive_context."""
        result = call_tool("neuraltree_score", {
            "project_root": str(tmp_project),
        })

        assert "error" not in result
        assert "adaptive_context" not in result
        assert "metrics" in result
        assert "flow_score_partial" in result
        assert result["metrics"]["precision_at_3"] is None
