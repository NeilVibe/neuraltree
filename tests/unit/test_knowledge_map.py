"""Tests for neuraltree_knowledge_map tool."""
import json
from pathlib import Path

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

    def test_semantic_edges_from_viking(self, tmp_project):
        """Semantic edges provided via semantic_edges param are included in the map."""
        reports = _make_explorer_reports()
        viking_edges = [
            {"source": "README.md", "target": "docs/guide.md", "weight": 0.85, "reason": "Viking similarity"},
        ]
        km = _build_map(reports, str(tmp_project), semantic_edges=viking_edges)
        sem_edges = [e for e in km["edges"] if e["type"] == "semantic"]
        assert len(sem_edges) == 1
        assert sem_edges[0]["source"] == "README.md"
        assert sem_edges[0]["target"] == "docs/guide.md"
        assert sem_edges[0]["weight"] == 0.85
        assert sem_edges[0]["reason"] == "Viking similarity"

    def test_semantic_edges_skip_unknown_files(self, tmp_project):
        """Semantic edges referencing files not in explorer reports are dropped."""
        reports = _make_explorer_reports()
        viking_edges = [
            {"source": "README.md", "target": "nonexistent.md", "weight": 0.9, "reason": "test"},
        ]
        km = _build_map(reports, str(tmp_project), semantic_edges=viking_edges)
        sem_edges = [e for e in km["edges"] if e["type"] == "semantic"]
        assert len(sem_edges) == 0

    def test_semantic_edges_skip_self_reference(self, tmp_project):
        """Semantic edges from a file to itself are dropped."""
        reports = _make_explorer_reports()
        viking_edges = [
            {"source": "README.md", "target": "README.md", "weight": 1.0, "reason": "self"},
        ]
        km = _build_map(reports, str(tmp_project), semantic_edges=viking_edges)
        sem_edges = [e for e in km["edges"] if e["type"] == "semantic"]
        assert len(sem_edges) == 0

    def test_semantic_edges_deduplicated_keeps_best_weight(self, tmp_project):
        """Duplicate semantic edges (A→B and B→A) dedup to highest weight."""
        reports = _make_explorer_reports()
        viking_edges = [
            {"source": "README.md", "target": "docs/guide.md", "weight": 0.75, "reason": "test"},
            {"source": "docs/guide.md", "target": "README.md", "weight": 0.85, "reason": "better"},
        ]
        km = _build_map(reports, str(tmp_project), semantic_edges=viking_edges)
        sem_edges = [e for e in km["edges"] if e["type"] == "semantic"]
        assert len(sem_edges) == 1
        assert sem_edges[0]["weight"] == 0.85  # best weight wins

    def test_no_semantic_edges_without_param(self, tmp_project):
        """Without semantic_edges param, no semantic edges are created."""
        reports = _make_explorer_reports()
        km = _build_map(reports, str(tmp_project))
        sem_edges = [e for e in km["edges"] if e["type"] == "semantic"]
        assert len(sem_edges) == 0

    def test_no_semantic_edges_with_empty_list(self, tmp_project):
        """Empty list produces same result as None."""
        reports = _make_explorer_reports()
        km = _build_map(reports, str(tmp_project), semantic_edges=[])
        sem_edges = [e for e in km["edges"] if e["type"] == "semantic"]
        assert len(sem_edges) == 0

    def test_semantic_edges_malformed_non_dict_skipped(self, tmp_project):
        """Non-dict entries in semantic_edges are skipped with a warning."""
        reports = _make_explorer_reports()
        viking_edges = ["not_a_dict", 42, None]
        km = _build_map(reports, str(tmp_project), semantic_edges=viking_edges)
        sem_edges = [e for e in km["edges"] if e["type"] == "semantic"]
        assert len(sem_edges) == 0
        assert len(km["warnings"]) == 3

    def test_semantic_edges_non_numeric_weight_skipped(self, tmp_project):
        """Non-numeric weight is skipped with a warning, not a crash."""
        reports = _make_explorer_reports()
        viking_edges = [
            {"source": "README.md", "target": "docs/guide.md", "weight": "high", "reason": "bad"},
        ]
        km = _build_map(reports, str(tmp_project), semantic_edges=viking_edges)
        sem_edges = [e for e in km["edges"] if e["type"] == "semantic"]
        assert len(sem_edges) == 0
        assert any("not a number" in w for w in km["warnings"])

    def test_colocation_suppressed_by_semantic_edge(self, tmp_project):
        """Semantic edge between co-located files suppresses co-location edge."""
        reports = [{
            "files": [
                {"path": "docs/a.md", "key_concepts": ["x"], "references_to": [], "size_lines": 10},
                {"path": "docs/b.md", "key_concepts": ["y"], "references_to": [], "size_lines": 10},
            ],
        }]
        viking_edges = [
            {"source": "docs/a.md", "target": "docs/b.md", "weight": 0.9, "reason": "test"},
        ]
        km = _build_map(reports, str(tmp_project), semantic_edges=viking_edges)
        coloc = [e for e in km["edges"] if e["type"] == "co-located"]
        assert len(coloc) == 0  # semantic edge suppresses co-location
        sem = [e for e in km["edges"] if e["type"] == "semantic"]
        assert len(sem) == 1

    def test_ensure_list_handles_tuples(self, tmp_project):
        """Tuple key_concepts should be converted to list, not dropped."""
        reports = [{
            "files": [
                {"path": "a.md", "key_concepts": ("setup", "install"), "references_to": [], "size_lines": 10},
            ],
        }]
        km = _build_map(reports, str(tmp_project))
        assert set(km["files"]["a.md"]["key_concepts"]) == {"setup", "install"}

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
