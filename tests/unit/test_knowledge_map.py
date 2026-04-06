"""Tests for neuraltree_knowledge_map tool."""
import json
from pathlib import Path

from neuraltree_mcp.text_utils import jaccard
from neuraltree_mcp.tools.knowledge_map import _save_map, _load_map, _query_map, _build_map


def _make_sample_map(project_name="test_project"):
    """Create a sample knowledge map for testing."""
    return {
        "version": 2,
        "timestamp": "2026-04-06T12:00:00Z",
        "project_name": project_name,
        "files": {
            "memory/rules/coding.md": {
                "type": "leaf",
                "size": 120,
                "depth": 2,
                "keywords": ["coding", "rules", "type hints"],
            },
            "memory/rules/testing.md": {
                "type": "leaf",
                "size": 95,
                "depth": 2,
                "keywords": ["testing", "playwright", "api"],
            },
            "docs/architecture/SUMMARY.md": {
                "type": "leaf",
                "size": 40,
                "depth": 2,
                "keywords": ["architecture", "client"],
            },
        },
        "edges": [
            {"source": "memory/rules/coding.md", "target": "memory/rules/testing.md", "type": "related", "weight": 0.8},
            {"source": "memory/rules/coding.md", "target": "docs/architecture/SUMMARY.md", "type": "docs", "weight": 0.4},
        ],
        "clusters": [
            {"name": "rules", "concept": "Behavioral rules and conventions", "files": ["memory/rules/coding.md", "memory/rules/testing.md"]},
            {"name": "architecture", "concept": "System design docs", "files": ["docs/architecture/SUMMARY.md"]},
        ],
        "issues": [
            {"type": "orphan", "file": "memory/reference/auth.md", "description": "No ## Related or ## Docs", "severity": "medium"},
            {"type": "stale", "file": "memory/rules/testing.md", "description": "last_verified > 90 days", "severity": "low"},
        ],
        "stats": {
            "total_files": 3,
            "total_edges": 2,
            "total_clusters": 2,
            "total_issues": 2,
            "avg_file_size": 85.0,
            "max_depth": 2,
        },
    }


class TestKnowledgeMapSave:
    def test_save_creates_file(self, tmp_project):
        km = _make_sample_map()
        path = _save_map(km, str(tmp_project))
        assert path.exists()
        assert path.name == "knowledge_map.json"
        assert path.parent.name == ".neuraltree"

    def test_save_roundtrip(self, tmp_project):
        km = _make_sample_map()
        _save_map(km, str(tmp_project))
        loaded = _load_map(str(tmp_project))
        assert loaded is not None
        assert loaded["version"] == 2
        assert loaded["project_name"] == "test_project"
        assert len(loaded["files"]) == 3
        assert len(loaded["edges"]) == 2
        assert len(loaded["clusters"]) == 2
        assert len(loaded["issues"]) == 2

    def test_save_creates_neuraltree_dir(self, tmp_project):
        km = _make_sample_map()
        nt_dir = tmp_project / ".neuraltree"
        assert not nt_dir.exists()
        _save_map(km, str(tmp_project))
        assert nt_dir.exists()
        assert nt_dir.is_dir()

    def test_save_overwrites_existing(self, tmp_project):
        km1 = _make_sample_map("first")
        km2 = _make_sample_map("second")
        _save_map(km1, str(tmp_project))
        _save_map(km2, str(tmp_project))
        loaded = _load_map(str(tmp_project))
        assert loaded["project_name"] == "second"

    def test_load_returns_none_when_missing(self, tmp_project):
        result = _load_map(str(tmp_project))
        assert result is None


class TestKnowledgeMapQuery:
    def _setup_map(self, tmp_project):
        km = _make_sample_map()
        _save_map(km, str(tmp_project))

    def test_query_by_file(self, tmp_project):
        self._setup_map(tmp_project)
        result = _query_map(str(tmp_project), file_path="memory/rules/coding.md")
        assert "file" in result
        assert result["file"]["type"] == "leaf"
        assert result["file"]["size"] == 120

    def test_query_by_file_not_found(self, tmp_project):
        self._setup_map(tmp_project)
        result = _query_map(str(tmp_project), file_path="nonexistent.md")
        assert "error" in result

    def test_query_by_cluster(self, tmp_project):
        self._setup_map(tmp_project)
        result = _query_map(str(tmp_project), cluster="rules")
        assert "cluster" in result
        assert result["cluster"]["name"] == "rules"
        assert len(result["cluster"]["files"]) == 2

    def test_query_by_cluster_not_found(self, tmp_project):
        self._setup_map(tmp_project)
        result = _query_map(str(tmp_project), cluster="nonexistent")
        assert "error" in result

    def test_query_neighbors(self, tmp_project):
        self._setup_map(tmp_project)
        result = _query_map(str(tmp_project), neighbors_of="memory/rules/coding.md")
        assert "neighbors" in result
        neighbors = result["neighbors"]
        assert len(neighbors) == 2
        targets = {n["file"] for n in neighbors}
        assert "memory/rules/testing.md" in targets
        assert "docs/architecture/SUMMARY.md" in targets

    def test_query_neighbors_no_edges(self, tmp_project):
        self._setup_map(tmp_project)
        result = _query_map(str(tmp_project), neighbors_of="docs/architecture/SUMMARY.md")
        assert "neighbors" in result
        # SUMMARY.md is only a target, not a source — but we check both directions
        neighbors = result["neighbors"]
        targets = {n["file"] for n in neighbors}
        assert "memory/rules/coding.md" in targets

    def test_query_issues_only(self, tmp_project):
        self._setup_map(tmp_project)
        result = _query_map(str(tmp_project), issues_only=True)
        assert "issues" in result
        assert len(result["issues"]) == 2

    def test_query_no_map(self, tmp_project):
        result = _query_map(str(tmp_project))
        assert "error" in result

    def test_query_full_map(self, tmp_project):
        self._setup_map(tmp_project)
        result = _query_map(str(tmp_project))
        assert "stats" in result
        assert result["stats"]["total_files"] == 3


# ─── _jaccard tests ──────────────────────────────────────────────────


class TestJaccard:
    def test_identical_sets(self):
        assert jaccard({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint_sets(self):
        assert jaccard({"a"}, {"b"}) == 0.0

    def test_partial_overlap(self):
        assert jaccard({"a", "b", "c"}, {"b", "c", "d"}) == 0.5

    def test_empty_sets(self):
        assert jaccard(set(), set()) == 0.0

    def test_one_empty(self):
        assert jaccard({"a"}, set()) == 0.0


# ─── _build_map tests ────────────────────────────────────────────────


def _make_explorer_reports():
    """Two explorer reports simulating parallel exploration."""
    return [
        {
            "files": [
                {
                    "path": "docs/guide.md",
                    "topic": "User guide",
                    "key_concepts": ["setup", "installation", "quickstart"],
                    "references_to": ["README.md"],
                    "size_lines": 80,
                    "has_frontmatter": True,
                    "has_related_section": False,
                    "has_docs_section": False,
                    "staleness": None,
                    "issues": [],
                },
                {
                    "path": "docs/api.md",
                    "topic": "API reference",
                    "key_concepts": ["endpoints", "authentication", "errors"],
                    "references_to": ["docs/guide.md"],
                    "size_lines": 150,
                    "has_frontmatter": False,
                    "has_related_section": False,
                    "has_docs_section": False,
                    "staleness": None,
                    "issues": ["LARGE_FILE: 150 lines"],
                },
            ],
            "directories": [
                {"path": "docs/", "purpose": "Documentation", "cohesion": "high", "issues": []},
            ],
            "observations": {},
        },
        {
            "files": [
                {
                    "path": "README.md",
                    "topic": "Project overview",
                    "key_concepts": ["setup", "installation", "overview"],
                    "references_to": ["docs/guide.md", "LICENSE"],
                    "size_lines": 40,
                    "has_frontmatter": False,
                    "has_related_section": False,
                    "has_docs_section": False,
                    "staleness": None,
                    "issues": [],
                },
                {
                    "path": "LICENSE",
                    "topic": "MIT License",
                    "key_concepts": ["license"],
                    "references_to": [],
                    "size_lines": 21,
                    "has_frontmatter": False,
                    "has_related_section": False,
                    "has_docs_section": False,
                    "staleness": None,
                    "issues": [],
                },
                {
                    "path": "src/config.md",
                    "topic": "Configuration reference",
                    "key_concepts": ["setup", "configuration", "environment"],
                    "references_to": [],
                    "size_lines": 60,
                    "has_frontmatter": False,
                    "has_related_section": False,
                    "has_docs_section": False,
                    "staleness": None,
                    "issues": [],
                },
            ],
            "directories": [
                {"path": ".", "purpose": "Project root", "cohesion": "medium", "issues": []},
                {"path": "src/", "purpose": "Source code", "cohesion": "high", "issues": []},
            ],
            "observations": {},
        },
    ]


class TestBuildMap:
    def test_merges_files_from_all_reports(self, tmp_project):
        reports = _make_explorer_reports()
        km = _build_map(reports, str(tmp_project))
        assert len(km["files"]) == 5
        assert "docs/guide.md" in km["files"]
        assert "README.md" in km["files"]
        assert "LICENSE" in km["files"]

    def test_reference_edges_only_between_known_files(self, tmp_project):
        reports = _make_explorer_reports()
        km = _build_map(reports, str(tmp_project))
        ref_edges = [e for e in km["edges"] if e["type"] == "reference"]
        # docs/guide.md -> README.md, docs/api.md -> docs/guide.md, README.md -> docs/guide.md
        # README.md -> LICENSE is also valid
        sources_targets = {(e["source"], e["target"]) for e in ref_edges}
        assert ("docs/guide.md", "README.md") in sources_targets
        assert ("docs/api.md", "docs/guide.md") in sources_targets
        assert ("README.md", "docs/guide.md") in sources_targets
        assert ("README.md", "LICENSE") in sources_targets

    def test_no_self_referencing_edges(self, tmp_project):
        reports = [{
            "files": [{
                "path": "a.md",
                "key_concepts": ["x"],
                "references_to": ["a.md"],
                "size_lines": 10,
            }],
        }]
        km = _build_map(reports, str(tmp_project))
        for e in km["edges"]:
            assert e["source"] != e["target"]

    def test_semantic_edges_computed(self, tmp_project):
        reports = _make_explorer_reports()
        km = _build_map(reports, str(tmp_project))
        sem_edges = [e for e in km["edges"] if e["type"] == "semantic"]
        # README.md and docs/guide.md share {"setup", "installation"} (2 concepts)
        # Jaccard: {setup,installation,overview} & {setup,installation,quickstart}
        # overlap=2, union=4, jaccard=0.5 > 0.3
        pairs = {(e["source"], e["target"]) for e in sem_edges}
        assert any(
            ("README.md" in pair and "docs/guide.md" in pair)
            for pair in pairs
        )

    def test_semantic_edges_have_shared_concepts(self, tmp_project):
        reports = _make_explorer_reports()
        km = _build_map(reports, str(tmp_project))
        sem_edges = [e for e in km["edges"] if e["type"] == "semantic"]
        for e in sem_edges:
            assert "shared_concepts" in e
            assert len(e["shared_concepts"]) >= 2

    def test_semantic_edges_skip_low_jaccard(self, tmp_project):
        """Files with only 2 shared concepts out of 20 total should not get an edge."""
        reports = [{
            "files": [
                {
                    "path": "a.md",
                    "key_concepts": ["a", "b", "c", "d", "e", "f", "g", "h", "i", "shared1", "shared2"],
                    "references_to": [],
                    "size_lines": 10,
                },
                {
                    "path": "b.md",
                    "key_concepts": ["x", "y", "z", "w", "v", "u", "t", "s", "r", "shared1", "shared2"],
                    "references_to": [],
                    "size_lines": 10,
                },
            ],
        }]
        km = _build_map(reports, str(tmp_project))
        sem_edges = [e for e in km["edges"] if e["type"] == "semantic"]
        # overlap=2, union=20, jaccard=0.1 < 0.3 → no edge
        assert len(sem_edges) == 0

    def test_colocation_edges_created_when_no_other_edge(self, tmp_project):
        """Two files in same dir with no ref/semantic edges get a co-location edge."""
        reports = [{
            "files": [
                {"path": "docs/a.md", "key_concepts": ["x"], "references_to": [], "size_lines": 10},
                {"path": "docs/b.md", "key_concepts": ["y"], "references_to": [], "size_lines": 10},
            ],
        }]
        km = _build_map(reports, str(tmp_project))
        coloc = [e for e in km["edges"] if e["type"] == "co-located"]
        assert len(coloc) == 1
        assert coloc[0]["source"] == "docs/a.md"
        assert coloc[0]["target"] == "docs/b.md"
        assert coloc[0]["weight"] == 0.5

    def test_colocation_skips_already_connected(self, tmp_project):
        """Files already connected by reference or semantic edges should not get co-location edges."""
        reports = [{
            "files": [
                {"path": "docs/a.md", "key_concepts": ["x"], "references_to": ["docs/b.md"], "size_lines": 10},
                {"path": "docs/b.md", "key_concepts": ["y"], "references_to": [], "size_lines": 10},
            ],
        }]
        km = _build_map(reports, str(tmp_project))
        coloc = [e for e in km["edges"] if e["type"] == "co-located"]
        assert len(coloc) == 0  # reference edge already exists

    def test_greedy_clustering(self, tmp_project):
        reports = _make_explorer_reports()
        km = _build_map(reports, str(tmp_project))
        clusters = km["clusters"]
        assert len(clusters) >= 1
        # All files must be in exactly one cluster
        all_clustered = set()
        for c in clusters:
            for f in c["files"]:
                assert f not in all_clustered, f"{f} in multiple clusters"
                all_clustered.add(f)
        assert all_clustered == set(km["files"].keys())

    def test_cluster_names_from_concepts(self, tmp_project):
        reports = _make_explorer_reports()
        km = _build_map(reports, str(tmp_project))
        for c in km["clusters"]:
            assert c["name"]  # not empty
            assert c["concept"]  # not empty

    def test_orphan_detection(self, tmp_project):
        """A file in a separate dir with no references and unique concepts should be orphan."""
        reports = [{
            "files": [
                {"path": "docs/connected.md", "key_concepts": ["a", "b"], "references_to": ["docs/other.md"], "size_lines": 10},
                {"path": "docs/other.md", "key_concepts": ["a", "b"], "references_to": [], "size_lines": 10},
                {"path": "isolated/orphan.md", "key_concepts": ["z"], "references_to": [], "size_lines": 10},
            ],
        }]
        km = _build_map(reports, str(tmp_project))
        orphan_issues = [i for i in km["issues"] if i["type"] == "orphan"]
        orphan_files = {i["file"] for i in orphan_issues}
        assert "isolated/orphan.md" in orphan_files

    def test_scattered_cluster_detection(self, tmp_project):
        """Cluster spanning 3+ dirs should be flagged."""
        reports = [{
            "files": [
                {"path": "a/f1.md", "key_concepts": ["shared1", "shared2", "x"], "references_to": [], "size_lines": 10},
                {"path": "b/f2.md", "key_concepts": ["shared1", "shared2", "y"], "references_to": [], "size_lines": 10},
                {"path": "c/f3.md", "key_concepts": ["shared1", "shared2", "z"], "references_to": [], "size_lines": 10},
            ],
        }]
        km = _build_map(reports, str(tmp_project))
        scattered = [i for i in km["issues"] if i["type"] == "scattered_cluster"]
        assert len(scattered) >= 1

    def test_explorer_issues_propagated(self, tmp_project):
        reports = _make_explorer_reports()
        km = _build_map(reports, str(tmp_project))
        explorer_issues = [i for i in km["issues"] if i["type"] == "explorer_finding"]
        assert len(explorer_issues) == 1
        assert "LARGE_FILE" in explorer_issues[0]["description"]

    def test_stats_computed(self, tmp_project):
        reports = _make_explorer_reports()
        km = _build_map(reports, str(tmp_project))
        stats = km["stats"]
        assert stats["total_files"] == 5
        assert stats["total_edges"] > 0
        assert stats["total_clusters"] >= 1
        assert stats["avg_file_size"] > 0
        assert stats["median_file_size"] > 0
        assert stats["max_depth"] >= 1

    def test_empty_reports(self, tmp_project):
        km = _build_map([], str(tmp_project))
        assert km["stats"]["total_files"] == 0
        assert km["stats"]["total_edges"] == 0
        assert km["edges"] == []
        assert km["clusters"] == []

    def test_build_and_save_roundtrip(self, tmp_project):
        reports = _make_explorer_reports()
        km = _build_map(reports, str(tmp_project))
        _save_map(km, str(tmp_project))
        loaded = _load_map(str(tmp_project))
        assert loaded is not None
        assert loaded["stats"]["total_files"] == km["stats"]["total_files"]
        assert len(loaded["edges"]) == len(km["edges"])

    def test_no_duplicate_edges(self, tmp_project):
        """Ensure no exact duplicate edges are created (same source, target, type)."""
        reports = _make_explorer_reports()
        km = _build_map(reports, str(tmp_project))
        # No exact (source, target, type) duplicates
        edge_keys = [(e["source"], e["target"], e["type"]) for e in km["edges"]]
        assert len(edge_keys) == len(set(edge_keys))

    # ── Review round 1 fixes: boundary & edge-case tests ──────────────

    def test_jaccard_exactly_0_3_produces_no_edge(self, tmp_project):
        """Jaccard exactly 0.3 should NOT create a semantic edge (strict > 0.3)."""
        # overlap=3, union=10, jaccard=0.3 exactly
        reports = [{
            "files": [
                {"path": "a.md", "key_concepts": ["a", "b", "c", "d", "e", "f", "g"],
                 "references_to": [], "size_lines": 10},
                {"path": "b.md", "key_concepts": ["a", "b", "c", "h", "i", "j"],
                 "references_to": [], "size_lines": 10},
            ],
        }]
        km = _build_map(reports, str(tmp_project))
        sem = [e for e in km["edges"] if e["type"] == "semantic"]
        assert len(sem) == 0

    def test_overlap_1_high_jaccard_produces_no_edge(self, tmp_project):
        """1 shared concept should NOT create a semantic edge even if Jaccard > 0.3."""
        reports = [{
            "files": [
                {"path": "a.md", "key_concepts": ["shared", "x"],
                 "references_to": [], "size_lines": 10},
                {"path": "b.md", "key_concepts": ["shared", "y"],
                 "references_to": [], "size_lines": 10},
            ],
        }]
        km = _build_map(reports, str(tmp_project))
        sem = [e for e in km["edges"] if e["type"] == "semantic"]
        assert len(sem) == 0

    def test_clustering_deterministic_with_ties(self, tmp_project):
        """Files with equal concept counts should produce the same clusters every time."""
        reports = [{
            "files": [
                {"path": "a.md", "key_concepts": ["x", "y"], "references_to": [], "size_lines": 10},
                {"path": "b.md", "key_concepts": ["x", "y"], "references_to": [], "size_lines": 10},
                {"path": "c.md", "key_concepts": ["p", "q"], "references_to": [], "size_lines": 10},
            ],
        }]
        results = [_build_map(reports, str(tmp_project)) for _ in range(5)]
        cluster_signatures = [
            tuple(tuple(c["files"]) for c in r["clusters"])
            for r in results
        ]
        assert len(set(cluster_signatures)) == 1, "Clustering is non-deterministic"

    def test_duplicate_file_across_reports_merges(self, tmp_project):
        """Same file in two reports should merge concepts and references."""
        reports = [
            {"files": [{"path": "shared.md", "key_concepts": ["a", "b"],
                         "references_to": ["x.md"], "size_lines": 50}]},
            {"files": [{"path": "shared.md", "key_concepts": ["b", "c"],
                         "references_to": ["y.md"], "size_lines": 80}]},
        ]
        km = _build_map(reports, str(tmp_project))
        f = km["files"]["shared.md"]
        assert set(f["key_concepts"]) == {"a", "b", "c"}
        assert set(f["references_to"]) == {"x.md", "y.md"}
        assert f["size_lines"] == 80  # max wins

    def test_string_key_concepts_coerced_to_list(self, tmp_project):
        """String key_concepts should be wrapped in a list, not iterated as chars."""
        reports = [{
            "files": [
                {"path": "a.md", "key_concepts": "setup", "references_to": [], "size_lines": 10},
            ],
        }]
        km = _build_map(reports, str(tmp_project))
        assert km["files"]["a.md"]["key_concepts"] == ["setup"]

    def test_path_traversal_skipped_with_warning(self, tmp_project):
        """File paths with traversal should be skipped and warned about."""
        reports = [{
            "files": [
                {"path": "../../etc/passwd", "key_concepts": ["bad"], "references_to": [], "size_lines": 10},
                {"path": "safe.md", "key_concepts": ["good"], "references_to": [], "size_lines": 10},
            ],
        }]
        km = _build_map(reports, str(tmp_project))
        assert "../../etc/passwd" not in km["files"]
        assert "safe.md" in km["files"]
        assert len(km["warnings"]) == 1
        assert "traversal" in km["warnings"][0]

    def test_single_file_input(self, tmp_project):
        """Single file should produce 1 cluster, 0 edges, 1 orphan."""
        reports = [{
            "files": [{"path": "only.md", "key_concepts": ["x"], "references_to": [], "size_lines": 10}],
        }]
        km = _build_map(reports, str(tmp_project))
        assert km["stats"]["total_files"] == 1
        assert km["stats"]["total_edges"] == 0
        assert len(km["clusters"]) == 1
        orphans = [i for i in km["issues"] if i["type"] == "orphan"]
        assert len(orphans) == 1
