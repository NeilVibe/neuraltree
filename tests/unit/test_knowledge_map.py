"""Tests for neuraltree_knowledge_map tool."""
import json
from pathlib import Path

from neuraltree_mcp.tools.knowledge_map import _save_map, _load_map, _query_map


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
