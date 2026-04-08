"""Integration tests for v2 knowledge map pipeline — save → load → query cycle."""
import json
import pytest

from tests.conftest import call_tool


def _make_knowledge_map() -> dict:
    """Build a minimal but complete knowledge map for testing."""
    return {
        "version": 2,
        "timestamp": "2026-04-06T12:00:00Z",
        "project_name": "mock_project",
        "files": {
            "CLAUDE.md": {
                "path": "CLAUDE.md",
                "topic": "Project instructions",
                "key_concepts": ["architecture", "glossary"],
                "references_to": ["memory/MEMORY.md"],
                "referenced_by": [],
                "size_lines": 10,
                "issues": [],
            },
            "memory/MEMORY.md": {
                "path": "memory/MEMORY.md",
                "topic": "Memory trunk",
                "key_concepts": ["rules", "reference"],
                "references_to": [],
                "referenced_by": ["CLAUDE.md"],
                "size_lines": 5,
                "issues": [],
            },
        },
        "edges": [
            {"source": "CLAUDE.md", "target": "memory/MEMORY.md", "type": "reference", "weight": 1.0},
        ],
        "clusters": [
            {"name": "project_docs", "concept": "project documentation", "files": ["CLAUDE.md", "memory/MEMORY.md"]},
        ],
        "issues": [],
        "stats": {
            "total_files": 2,
            "total_edges": 1,
            "total_clusters": 1,
            "total_issues": 0,
            "avg_file_size": 7,
            "max_depth": 1,
        },
    }


class TestKnowledgeMapPipeline:
    """Test the full save -> load -> query cycle via MCP tool."""

    def test_save_returns_path_and_file_count(self, tmp_project):
        km = _make_knowledge_map()
        result = call_tool("neuraltree_knowledge_map", {
            "action": "save",
            "project_root": str(tmp_project),
            "knowledge_map": km,
        })
        assert "saved" in result
        assert result["files"] == 2
        # saved is a path string, not a boolean
        assert result["saved"].endswith("knowledge_map.json")

    def test_save_creates_file_on_disk(self, tmp_project):
        km = _make_knowledge_map()
        call_tool("neuraltree_knowledge_map", {
            "action": "save",
            "project_root": str(tmp_project),
            "knowledge_map": km,
        })
        km_path = tmp_project / ".neuraltree" / "knowledge_map.json"
        assert km_path.exists()
        loaded = json.loads(km_path.read_text())
        assert loaded["version"] == 2
        assert len(loaded["files"]) == 2

    def test_load_returns_knowledge_map(self, tmp_project):
        km = _make_knowledge_map()
        call_tool("neuraltree_knowledge_map", {
            "action": "save",
            "project_root": str(tmp_project),
            "knowledge_map": km,
        })
        result = call_tool("neuraltree_knowledge_map", {
            "action": "load",
            "project_root": str(tmp_project),
        })
        assert "knowledge_map" in result
        assert len(result["knowledge_map"]["files"]) == 2
        assert result["knowledge_map"]["project_name"] == "mock_project"

    def test_load_when_no_map_exists(self, tmp_project):
        result = call_tool("neuraltree_knowledge_map", {
            "action": "load",
            "project_root": str(tmp_project),
        })
        assert "error" in result

    def test_query_file(self, tmp_project):
        km = _make_knowledge_map()
        call_tool("neuraltree_knowledge_map", {
            "action": "save",
            "project_root": str(tmp_project),
            "knowledge_map": km,
        })
        result = call_tool("neuraltree_knowledge_map", {
            "action": "query",
            "project_root": str(tmp_project),
            "file_path": "CLAUDE.md",
        })
        assert result["path"] == "CLAUDE.md"
        assert result["file"]["topic"] == "Project instructions"
        assert "architecture" in result["file"]["key_concepts"]

    def test_query_file_not_in_map(self, tmp_project):
        km = _make_knowledge_map()
        call_tool("neuraltree_knowledge_map", {
            "action": "save",
            "project_root": str(tmp_project),
            "knowledge_map": km,
        })
        result = call_tool("neuraltree_knowledge_map", {
            "action": "query",
            "project_root": str(tmp_project),
            "file_path": "nonexistent.md",
        })
        assert "error" in result

    def test_query_neighbors(self, tmp_project):
        km = _make_knowledge_map()
        call_tool("neuraltree_knowledge_map", {
            "action": "save",
            "project_root": str(tmp_project),
            "knowledge_map": km,
        })
        result = call_tool("neuraltree_knowledge_map", {
            "action": "query",
            "project_root": str(tmp_project),
            "neighbors_of": "CLAUDE.md",
        })
        assert result["file"] == "CLAUDE.md"
        neighbor_files = [n["file"] for n in result["neighbors"]]
        assert "memory/MEMORY.md" in neighbor_files
        # Verify direction is outbound (CLAUDE.md -> memory/MEMORY.md)
        outbound = [n for n in result["neighbors"] if n["direction"] == "outbound"]
        assert len(outbound) >= 1

    def test_query_neighbors_reverse_direction(self, tmp_project):
        km = _make_knowledge_map()
        call_tool("neuraltree_knowledge_map", {
            "action": "save",
            "project_root": str(tmp_project),
            "knowledge_map": km,
        })
        result = call_tool("neuraltree_knowledge_map", {
            "action": "query",
            "project_root": str(tmp_project),
            "neighbors_of": "memory/MEMORY.md",
        })
        neighbor_files = [n["file"] for n in result["neighbors"]]
        assert "CLAUDE.md" in neighbor_files
        # Direction should be inbound (CLAUDE.md -> memory/MEMORY.md, queried from target)
        inbound = [n for n in result["neighbors"] if n["direction"] == "inbound"]
        assert len(inbound) >= 1

    def test_query_cluster(self, tmp_project):
        km = _make_knowledge_map()
        call_tool("neuraltree_knowledge_map", {
            "action": "save",
            "project_root": str(tmp_project),
            "knowledge_map": km,
        })
        result = call_tool("neuraltree_knowledge_map", {
            "action": "query",
            "project_root": str(tmp_project),
            "cluster": "project_docs",
        })
        assert "cluster" in result
        assert "CLAUDE.md" in result["cluster"]["files"]
        assert "memory/MEMORY.md" in result["cluster"]["files"]
        assert result["cluster"]["concept"] == "project documentation"

    def test_query_cluster_not_found(self, tmp_project):
        km = _make_knowledge_map()
        call_tool("neuraltree_knowledge_map", {
            "action": "save",
            "project_root": str(tmp_project),
            "knowledge_map": km,
        })
        result = call_tool("neuraltree_knowledge_map", {
            "action": "query",
            "project_root": str(tmp_project),
            "cluster": "nonexistent_cluster",
        })
        assert "error" in result

    def test_query_issues_only(self, tmp_project):
        km = _make_knowledge_map()
        call_tool("neuraltree_knowledge_map", {
            "action": "save",
            "project_root": str(tmp_project),
            "knowledge_map": km,
        })
        result = call_tool("neuraltree_knowledge_map", {
            "action": "query",
            "project_root": str(tmp_project),
            "issues_only": True,
        })
        assert "issues" in result
        assert result["issues"] == []

    def test_query_default_returns_stats(self, tmp_project):
        km = _make_knowledge_map()
        call_tool("neuraltree_knowledge_map", {
            "action": "save",
            "project_root": str(tmp_project),
            "knowledge_map": km,
        })
        result = call_tool("neuraltree_knowledge_map", {
            "action": "query",
            "project_root": str(tmp_project),
        })
        assert "stats" in result
        assert result["stats"]["total_files"] == 2
        assert result["version"] == 2
        assert result["project_name"] == "mock_project"

    def test_save_without_knowledge_map_errors(self, tmp_project):
        result = call_tool("neuraltree_knowledge_map", {
            "action": "save",
            "project_root": str(tmp_project),
        })
        assert "error" in result

    def test_unknown_action_errors(self, tmp_project):
        result = call_tool("neuraltree_knowledge_map", {
            "action": "explode",
            "project_root": str(tmp_project),
        })
        assert "error" in result
        assert "explode" in result["error"]

    def test_query_no_map_errors(self, tmp_project):
        result = call_tool("neuraltree_knowledge_map", {
            "action": "query",
            "project_root": str(tmp_project),
            "file_path": "CLAUDE.md",
        })
        assert "error" in result


class TestKnowledgeMapBuild:
    """Test the build action — deterministic map construction from explorer reports."""

    def _make_explorer_reports(self):
        return [
            {
                "files": [
                    {
                        "path": "CLAUDE.md",
                        "topic": "Project instructions",
                        "key_concepts": ["architecture", "tools", "pipeline"],
                        "references_to": ["README.md"],
                        "size_lines": 100,
                        "issues": [],
                    },
                    {
                        "path": "README.md",
                        "topic": "Public docs",
                        "key_concepts": ["installation", "tools", "pipeline"],
                        "references_to": ["CLAUDE.md", "LICENSE"],
                        "size_lines": 200,
                        "issues": ["LARGE_FILE: 200 lines"],
                    },
                ],
            },
            {
                "files": [
                    {
                        "path": "LICENSE",
                        "topic": "MIT License",
                        "key_concepts": ["license"],
                        "references_to": [],
                        "size_lines": 21,
                        "issues": [],
                    },
                    {
                        "path": "docs/guide.md",
                        "topic": "User guide",
                        "key_concepts": ["installation", "setup", "quickstart"],
                        "references_to": ["README.md"],
                        "size_lines": 80,
                        "issues": [],
                    },
                ],
            },
        ]

    def test_build_returns_map_and_saves(self, tmp_project):
        result = call_tool("neuraltree_knowledge_map", {
            "action": "build",
            "project_root": str(tmp_project),
            "explorer_reports": self._make_explorer_reports(),
        })
        assert "saved" in result
        assert "knowledge_map" in result
        assert "stats" in result
        assert result["stats"]["total_files"] == 4

    def test_build_creates_file_on_disk(self, tmp_project):
        call_tool("neuraltree_knowledge_map", {
            "action": "build",
            "project_root": str(tmp_project),
            "explorer_reports": self._make_explorer_reports(),
        })
        km_path = tmp_project / ".neuraltree" / "knowledge_map.json"
        assert km_path.exists()
        loaded = json.loads(km_path.read_text())
        assert loaded["version"] == 2
        assert len(loaded["files"]) == 4

    def test_build_computes_reference_edges(self, tmp_project):
        result = call_tool("neuraltree_knowledge_map", {
            "action": "build",
            "project_root": str(tmp_project),
            "explorer_reports": self._make_explorer_reports(),
        })
        km = result["knowledge_map"]
        ref_edges = [e for e in km["edges"] if e["type"] == "reference"]
        pairs = {(e["source"], e["target"]) for e in ref_edges}
        assert ("CLAUDE.md", "README.md") in pairs
        assert ("README.md", "CLAUDE.md") in pairs
        assert ("README.md", "LICENSE") in pairs
        assert ("docs/guide.md", "README.md") in pairs

    def test_build_accepts_viking_semantic_edges(self, tmp_project):
        viking_edges = [
            {"source": "CLAUDE.md", "target": "README.md", "weight": 0.9, "reason": "Viking similarity"},
        ]
        result = call_tool("neuraltree_knowledge_map", {
            "action": "build",
            "project_root": str(tmp_project),
            "explorer_reports": self._make_explorer_reports(),
            "semantic_edges": viking_edges,
        })
        km = result["knowledge_map"]
        sem_edges = [e for e in km["edges"] if e["type"] == "semantic"]
        assert len(sem_edges) == 1
        assert sem_edges[0]["source"] == "CLAUDE.md"
        assert sem_edges[0]["target"] == "README.md"
        assert sem_edges[0]["weight"] == 0.9
        assert sem_edges[0]["reason"] == "Viking similarity"

    def test_build_no_semantic_edges_without_param(self, tmp_project):
        result = call_tool("neuraltree_knowledge_map", {
            "action": "build",
            "project_root": str(tmp_project),
            "explorer_reports": self._make_explorer_reports(),
        })
        km = result["knowledge_map"]
        sem_edges = [e for e in km["edges"] if e["type"] == "semantic"]
        assert len(sem_edges) == 0

    def test_build_computes_clusters(self, tmp_project):
        result = call_tool("neuraltree_knowledge_map", {
            "action": "build",
            "project_root": str(tmp_project),
            "explorer_reports": self._make_explorer_reports(),
        })
        km = result["knowledge_map"]
        clusters = km["clusters"]
        assert len(clusters) >= 1
        # Every file in exactly one cluster
        all_files = set()
        for c in clusters:
            for f in c["files"]:
                assert f not in all_files
                all_files.add(f)
        assert all_files == set(km["files"].keys())

    def test_build_detects_orphans(self, tmp_project):
        # Put orphan in a separate dir so co-location doesn't connect it
        reports = [{
            "files": [
                {"path": "docs/a.md", "key_concepts": ["x"], "references_to": ["docs/b.md"], "size_lines": 10, "issues": []},
                {"path": "docs/b.md", "key_concepts": ["x"], "references_to": [], "size_lines": 10, "issues": []},
                {"path": "isolated/orphan.md", "key_concepts": ["unique_z"], "references_to": [], "size_lines": 10, "issues": []},
            ],
        }]
        result = call_tool("neuraltree_knowledge_map", {
            "action": "build",
            "project_root": str(tmp_project),
            "explorer_reports": reports,
        })
        km = result["knowledge_map"]
        orphans = [i for i in km["issues"] if i["type"] == "orphan"]
        orphan_files = {i["file"] for i in orphans}
        assert "isolated/orphan.md" in orphan_files

    def test_build_propagates_explorer_issues(self, tmp_project):
        result = call_tool("neuraltree_knowledge_map", {
            "action": "build",
            "project_root": str(tmp_project),
            "explorer_reports": self._make_explorer_reports(),
        })
        km = result["knowledge_map"]
        explorer_issues = [i for i in km["issues"] if i["type"] == "explorer_finding"]
        assert len(explorer_issues) == 1
        assert "LARGE_FILE" in explorer_issues[0]["description"]

    def test_build_without_reports_errors(self, tmp_project):
        result = call_tool("neuraltree_knowledge_map", {
            "action": "build",
            "project_root": str(tmp_project),
        })
        assert "error" in result

    def test_build_with_empty_reports(self, tmp_project):
        result = call_tool("neuraltree_knowledge_map", {
            "action": "build",
            "project_root": str(tmp_project),
            "explorer_reports": [],
        })
        assert result["stats"]["total_files"] == 0

    def test_build_loadable_after_save(self, tmp_project):
        call_tool("neuraltree_knowledge_map", {
            "action": "build",
            "project_root": str(tmp_project),
            "explorer_reports": self._make_explorer_reports(),
        })
        result = call_tool("neuraltree_knowledge_map", {
            "action": "load",
            "project_root": str(tmp_project),
        })
        assert "knowledge_map" in result
        assert result["knowledge_map"]["stats"]["total_files"] == 4


class TestScoreWithKnowledgeMap:
    """Score reads the knowledge map for universal organization metrics."""

    def test_score_uses_knowledge_map(self, tmp_project):
        from neuraltree_mcp.tools.knowledge_map import _save_map

        km = {
            "version": 2,
            "files": {f"file_{i}.md": {"size_lines": 50} for i in range(50)},
            "edges": [{"source": "file_0.md", "target": "file_1.md", "type": "reference"}],
            "clusters": [{"files": ["file_0.md", "file_1.md"]}],
            "stats": {"total_files": 50, "total_edges": 1, "avg_file_size": 50, "max_depth": 1},
        }
        _save_map(km, str(tmp_project))

        result = call_tool("neuraltree_score", {
            "project_root": str(tmp_project),
        })
        assert "error" not in result
        assert "metrics" in result
        assert "reachability" in result["metrics"]
        assert "connectivity" in result["metrics"]
        assert result["details"]["total_files"] == 50

    def test_score_without_map_returns_no_map(self, tmp_project):
        result = call_tool("neuraltree_score", {
            "project_root": str(tmp_project),
        })
        assert result.get("no_map") is True
        assert result["flow_score_partial"] is None


class TestKnowledgeMapRoundTrip:
    """Verify data integrity through save → load round-trips."""

    def test_round_trip_preserves_all_fields(self, tmp_project):
        km = _make_knowledge_map()
        call_tool("neuraltree_knowledge_map", {
            "action": "save",
            "project_root": str(tmp_project),
            "knowledge_map": km,
        })
        result = call_tool("neuraltree_knowledge_map", {
            "action": "load",
            "project_root": str(tmp_project),
        })
        loaded = result["knowledge_map"]
        assert loaded["version"] == km["version"]
        assert loaded["timestamp"] == km["timestamp"]
        assert loaded["project_name"] == km["project_name"]
        assert loaded["files"] == km["files"]
        assert loaded["edges"] == km["edges"]
        assert loaded["clusters"] == km["clusters"]
        assert loaded["issues"] == km["issues"]
        assert loaded["stats"] == km["stats"]

    def test_overwrite_replaces_previous_map(self, tmp_project):
        km1 = _make_knowledge_map()
        call_tool("neuraltree_knowledge_map", {
            "action": "save",
            "project_root": str(tmp_project),
            "knowledge_map": km1,
        })

        km2 = _make_knowledge_map()
        km2["project_name"] = "updated_project"
        km2["files"]["new_file.md"] = {
            "path": "new_file.md",
            "topic": "New content",
            "key_concepts": [],
            "references_to": [],
            "referenced_by": [],
            "size_lines": 3,
            "issues": [],
        }
        call_tool("neuraltree_knowledge_map", {
            "action": "save",
            "project_root": str(tmp_project),
            "knowledge_map": km2,
        })

        result = call_tool("neuraltree_knowledge_map", {
            "action": "load",
            "project_root": str(tmp_project),
        })
        loaded = result["knowledge_map"]
        assert loaded["project_name"] == "updated_project"
        assert len(loaded["files"]) == 3
