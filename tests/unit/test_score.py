"""Tests for neuraltree_score — universal organization metrics."""
import json

from neuraltree_mcp.scoring.score import (
    WEIGHTS,
    _detect_entry_points,
    _bfs_reachable,
    _compute_connectivity,
    _compute_cluster_coherence,
    _compute_size_balance,
)

from tests.conftest import call_tool


class TestWeights:
    def test_weights_sum_to_one(self):
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_five_metrics(self):
        assert len(WEIGHTS) == 5
        for key in ("reachability", "connectivity", "cluster_coherence", "size_balance", "discoverability"):
            assert key in WEIGHTS


class TestDetectEntryPoints:
    def test_finds_readme_and_claude(self):
        files = {"README.md": {}, "CLAUDE.md": {}, "src/main.md": {}}
        entries = _detect_entry_points(files)
        assert "README.md" in entries
        assert "CLAUDE.md" in entries
        assert "src/main.md" not in entries

    def test_case_insensitive_basename(self):
        # Entry point detection uses lowercase basename
        files = {"docs/INDEX.md": {}}
        entries = _detect_entry_points(files)
        assert "docs/INDEX.md" in entries

    def test_no_entry_points(self):
        files = {"src/utils.md": {}, "lib/helpers.md": {}}
        entries = _detect_entry_points(files)
        assert entries == []


class TestBfsReachable:
    def test_basic_reachability(self):
        edges = [
            {"source": "A.md", "target": "B.md"},
            {"source": "B.md", "target": "C.md"},
        ]
        all_files = {"A.md", "B.md", "C.md", "D.md"}
        reachable = _bfs_reachable(["A.md"], edges, all_files, max_hops=3)
        assert reachable == {"A.md", "B.md", "C.md"}
        assert "D.md" not in reachable

    def test_bidirectional(self):
        edges = [{"source": "A.md", "target": "B.md"}]
        all_files = {"A.md", "B.md"}
        # Starting from B should reach A (edges are bidirectional)
        reachable = _bfs_reachable(["B.md"], edges, all_files, max_hops=3)
        assert "A.md" in reachable

    def test_max_hops_limit(self):
        edges = [
            {"source": "A.md", "target": "B.md"},
            {"source": "B.md", "target": "C.md"},
            {"source": "C.md", "target": "D.md"},
            {"source": "D.md", "target": "E.md"},
        ]
        all_files = {"A.md", "B.md", "C.md", "D.md", "E.md"}
        reachable = _bfs_reachable(["A.md"], edges, all_files, max_hops=2)
        assert "A.md" in reachable
        assert "B.md" in reachable
        assert "C.md" in reachable
        assert "D.md" not in reachable

    def test_no_entry_points(self):
        edges = [{"source": "A.md", "target": "B.md"}]
        reachable = _bfs_reachable([], edges, {"A.md", "B.md"}, max_hops=3)
        assert reachable == set()

    def test_ignores_files_not_in_all_files(self):
        edges = [{"source": "A.md", "target": "external.md"}]
        all_files = {"A.md"}
        reachable = _bfs_reachable(["A.md"], edges, all_files, max_hops=3)
        assert reachable == {"A.md"}

    def test_multiple_entry_points(self):
        edges = [
            {"source": "A.md", "target": "B.md"},
            {"source": "C.md", "target": "D.md"},
        ]
        all_files = {"A.md", "B.md", "C.md", "D.md"}
        reachable = _bfs_reachable(["A.md", "C.md"], edges, all_files, max_hops=3)
        assert reachable == {"A.md", "B.md", "C.md", "D.md"}


class TestConnectivity:
    def test_all_connected(self):
        edges = [
            {"source": "A.md", "target": "B.md"},
            {"source": "B.md", "target": "C.md"},
        ]
        ratio, orphans = _compute_connectivity(edges, {"A.md", "B.md", "C.md"})
        assert ratio == 1.0
        assert orphans == []

    def test_one_orphan(self):
        edges = [{"source": "A.md", "target": "B.md"}]
        ratio, orphans = _compute_connectivity(edges, {"A.md", "B.md", "C.md"})
        assert abs(ratio - 2 / 3) < 0.01
        assert orphans == ["C.md"]

    def test_no_edges(self):
        ratio, orphans = _compute_connectivity([], {"A.md", "B.md"})
        assert ratio == 0.0
        assert len(orphans) == 2


class TestClusterCoherence:
    def test_all_same_directory(self):
        clusters = [{"files": ["src/a.md", "src/b.md", "src/c.md"]}]
        assert _compute_cluster_coherence(clusters) == 1.0

    def test_scattered_cluster(self):
        clusters = [{"files": ["src/a.md", "docs/b.md", "lib/c.md"]}]
        coherence = _compute_cluster_coherence(clusters)
        assert coherence == 0.0  # no pairs share a directory

    def test_mixed(self):
        clusters = [{"files": ["src/a.md", "src/b.md", "docs/c.md"]}]
        coherence = _compute_cluster_coherence(clusters)
        # 3 pairs: (a,b)=same, (a,c)=diff, (b,c)=diff → 1/3
        assert abs(coherence - 1 / 3) < 0.01

    def test_singleton_clusters_trivially_coherent(self):
        clusters = [{"files": ["a.md"]}, {"files": ["b.md"]}]
        assert _compute_cluster_coherence(clusters) == 1.0

    def test_empty_clusters(self):
        assert _compute_cluster_coherence([]) == 1.0

    def test_root_directory_files(self):
        clusters = [{"files": ["a.md", "b.md"]}]
        coherence = _compute_cluster_coherence(clusters)
        assert coherence == 1.0  # both in root (dirname=".")


class TestSizeBalance:
    def test_all_balanced(self):
        files = {
            "a.md": {"size_lines": 100},
            "b.md": {"size_lines": 120},
            "c.md": {"size_lines": 80},
        }
        ratio, oversized = _compute_size_balance(files)
        assert ratio == 1.0
        assert oversized == []

    def test_one_mega_file(self):
        files = {
            "a.md": {"size_lines": 100},
            "b.md": {"size_lines": 100},
            "c.md": {"size_lines": 1000},  # 10x median
        }
        ratio, oversized = _compute_size_balance(files)
        assert ratio < 1.0
        assert "c.md" in oversized

    def test_empty_files_skipped(self):
        files = {
            "a.md": {"size_lines": 100},
            "b.md": {"size_lines": 0},  # empty
        }
        ratio, oversized = _compute_size_balance(files)
        assert ratio == 1.0

    def test_no_files(self):
        ratio, oversized = _compute_size_balance({})
        assert ratio == 1.0
        assert oversized == []

    def test_min_cap_prevents_tiny_project_penalty(self):
        # Files of 10 lines — 3x median = 30, but min cap is 50
        files = {
            "a.md": {"size_lines": 10},
            "b.md": {"size_lines": 10},
            "c.md": {"size_lines": 45},  # > 3x median but < min cap 50
        }
        ratio, oversized = _compute_size_balance(files)
        assert ratio == 1.0  # 45 < 50 (min cap)


class TestScoreIntegration:
    def test_requires_knowledge_map(self, tmp_project):
        """Score should return no_map flag when no knowledge map exists."""
        result = call_tool("neuraltree_score", {
            "project_root": str(tmp_project),
        })
        assert result.get("no_map") is True
        assert result["flow_score_partial"] is None
        assert all(v is None for v in result["metrics"].values())

    def test_with_knowledge_map(self, tmp_project):
        """Score should return all 5 metrics when knowledge map exists."""
        nt_dir = tmp_project / ".neuraltree"
        nt_dir.mkdir()
        km = {
            "files": {
                "README.md": {"size_lines": 100},
                "CLAUDE.md": {"size_lines": 80},
                "docs/guide.md": {"size_lines": 50},
            },
            "edges": [
                {"source": "README.md", "target": "CLAUDE.md", "type": "reference"},
                {"source": "CLAUDE.md", "target": "docs/guide.md", "type": "reference"},
            ],
            "clusters": [
                {"files": ["README.md", "CLAUDE.md"]},
            ],
        }
        (nt_dir / "knowledge_map.json").write_text(json.dumps(km))

        result = call_tool("neuraltree_score", {"project_root": str(tmp_project)})

        assert "error" not in result
        metrics = result["metrics"]
        assert "reachability" in metrics
        assert "connectivity" in metrics
        assert "cluster_coherence" in metrics
        assert "size_balance" in metrics
        assert "discoverability" in metrics
        assert metrics["discoverability"] is None  # filled by skill
        assert result["flow_score_partial"] > 0

    def test_entry_points_auto_detected(self, tmp_project):
        nt_dir = tmp_project / ".neuraltree"
        nt_dir.mkdir()
        km = {
            "files": {"README.md": {"size_lines": 10}, "other.md": {"size_lines": 10}},
            "edges": [{"source": "README.md", "target": "other.md"}],
            "clusters": [],
        }
        (nt_dir / "knowledge_map.json").write_text(json.dumps(km))

        result = call_tool("neuraltree_score", {"project_root": str(tmp_project)})
        assert "README.md" in result["details"]["entry_points"]

    def test_trunk_paths_override(self, tmp_project):
        nt_dir = tmp_project / ".neuraltree"
        nt_dir.mkdir()
        km = {
            "files": {"custom.md": {"size_lines": 10}, "other.md": {"size_lines": 10}},
            "edges": [{"source": "custom.md", "target": "other.md"}],
            "clusters": [],
        }
        (nt_dir / "knowledge_map.json").write_text(json.dumps(km))

        result = call_tool("neuraltree_score", {
            "project_root": str(tmp_project),
            "trunk_paths": ["custom.md"],
        })
        assert result["details"]["entry_points"] == ["custom.md"]
        assert result["metrics"]["reachability"] == 1.0

    def test_corrupt_knowledge_map(self, tmp_project):
        nt_dir = tmp_project / ".neuraltree"
        nt_dir.mkdir()
        (nt_dir / "knowledge_map.json").write_text("NOT JSON")

        result = call_tool("neuraltree_score", {"project_root": str(tmp_project)})
        assert "error" in result
        assert "corrupt" in result["error"].lower()
