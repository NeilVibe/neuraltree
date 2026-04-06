"""Tests for neuraltree_precision tool (Viking search + content retrieval)."""
import json
from unittest.mock import MagicMock, patch

import pytest

from neuraltree_mcp.tools.precision import (
    _check_viking,
    _source_doc,
    _viking_read,
    _viking_search,
    register,
)


@pytest.fixture
def mcp_with_precision():
    """Register precision tool and return mcp instance."""
    from fastmcp import FastMCP

    mcp = FastMCP("test")
    register(mcp)
    return mcp


# --- Helper function tests ---


class TestCheckViking:
    def test_viking_reachable(self):
        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.get.return_value = MagicMock(status_code=200)
            assert _check_viking("http://localhost:1933") is True

    def test_viking_unreachable(self):
        import requests

        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.get.side_effect = requests.ConnectionError()
            mock_req.ConnectionError = requests.ConnectionError
            mock_req.Timeout = requests.Timeout
            assert _check_viking("http://localhost:9999") is False

    def test_viking_500(self):
        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.get.return_value = MagicMock(status_code=500)
            assert _check_viking("http://localhost:1933") is False


class TestVikingSearch:
    def test_returns_results(self):
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {
            "result": {
                "resources": [
                    {"uri": "viking://resources/a.md", "score": 0.9, "abstract": "test"},
                    {"uri": "viking://resources/b.md", "score": 0.7, "abstract": "other"},
                ]
            }
        }
        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.post.return_value = mock_response
            results = _viking_search("http://localhost:1933", "test query", 3)
            assert len(results) == 2
            assert results[0]["uri"] == "viking://resources/a.md"
            assert results[0]["score"] == 0.9

    def test_returns_empty_on_error(self):
        import requests

        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.post.side_effect = requests.ConnectionError()
            mock_req.ConnectionError = requests.ConnectionError
            mock_req.Timeout = requests.Timeout
            mock_req.ValueError = ValueError
            results = _viking_search("http://localhost:1933", "test", 3)
            assert results == []

    def test_returns_empty_on_http_error(self):
        mock_response = MagicMock(status_code=500)
        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.post.return_value = mock_response
            results = _viking_search("http://localhost:1933", "test", 3)
            assert results == []

    def test_filters_by_project_name(self):
        """With project_name, only URIs matching that project are returned."""
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {
            "result": {
                "resources": [
                    {"uri": "viking://resources/neuraltree/a.md", "score": 0.9, "abstract": ""},
                    {"uri": "viking://resources/newfin/b.md", "score": 0.85, "abstract": ""},
                    {"uri": "viking://resources/neuraltree/c.md", "score": 0.8, "abstract": ""},
                    {"uri": "viking://resources/memory/d.md", "score": 0.7, "abstract": ""},
                    {"uri": "viking://resources/neuraltree/e.md", "score": 0.6, "abstract": ""},
                ]
            }
        }
        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.post.return_value = mock_response
            results = _viking_search("http://localhost:1933", "test", 3, project_name="neuraltree")
            assert len(results) == 3
            assert all("neuraltree" in r["uri"] for r in results)
            assert results[0]["uri"] == "viking://resources/neuraltree/a.md"

    def test_no_filter_without_project_name(self):
        """Without project_name, all results pass through."""
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {
            "result": {
                "resources": [
                    {"uri": "viking://resources/newfin/a.md", "score": 0.9, "abstract": ""},
                    {"uri": "viking://resources/neuraltree/b.md", "score": 0.8, "abstract": ""},
                ]
            }
        }
        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.post.return_value = mock_response
            results = _viking_search("http://localhost:1933", "test", 3, project_name=None)
            assert len(results) == 2

    def test_over_fetches_when_filtering(self):
        """Should request limit*3 from Viking when project_name is set."""
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {"result": {"resources": []}}
        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.post.return_value = mock_response
            _viking_search("http://localhost:1933", "test", 3, project_name="myproject")
            call_args = mock_req.post.call_args
            assert call_args[1]["json"]["limit"] == 30  # 3 * 10


    def test_deduplicates_by_source_doc(self):
        """Multiple chunks from same source doc should be deduped to best one."""
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {
            "result": {
                "resources": [
                    {"uri": "viking://resources/proj/CLAUDE.md/chunk1.md", "score": 0.9, "abstract": ""},
                    {"uri": "viking://resources/proj/CLAUDE.md/chunk2.md", "score": 0.85, "abstract": ""},
                    {"uri": "viking://resources/proj/CLAUDE.md/chunk3.md", "score": 0.8, "abstract": ""},
                    {"uri": "viking://resources/proj/README.md/chunk1.md", "score": 0.7, "abstract": ""},
                    {"uri": "viking://resources/proj/lessons.md/chunk1.md", "score": 0.6, "abstract": ""},
                ]
            }
        }
        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.post.return_value = mock_response
            results = _viking_search("http://localhost:1933", "test", 3, project_name="proj")
            assert len(results) == 3
            # Should be one from each source doc, not 3 from CLAUDE.md
            uris = [r["uri"] for r in results]
            assert "viking://resources/proj/CLAUDE.md/chunk1.md" in uris  # best chunk
            assert "viking://resources/proj/README.md/chunk1.md" in uris
            assert "viking://resources/proj/lessons.md/chunk1.md" in uris

    def test_dedup_keeps_highest_score(self):
        """Dedup should keep the highest-scoring chunk per source doc."""
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {
            "result": {
                "resources": [
                    {"uri": "viking://resources/proj/A.md/chunk2.md", "score": 0.95, "abstract": ""},
                    {"uri": "viking://resources/proj/A.md/chunk1.md", "score": 0.5, "abstract": ""},
                ]
            }
        }
        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.post.return_value = mock_response
            results = _viking_search("http://localhost:1933", "test", 3, project_name="proj")
            assert len(results) == 1
            assert results[0]["score"] == 0.95


class TestSourceDoc:
    def test_extracts_source_doc(self):
        uri = "viking://resources/neuraltree/CLAUDE.md/CLAUDEmd_NeuralTree/chunk.md"
        assert _source_doc(uri) == "CLAUDE.md"

    def test_extracts_from_deep_path(self):
        uri = "viking://resources/neuraltree/docs_HANDOFF.md/Session/What_Was_Done.md"
        assert _source_doc(uri) == "docs_HANDOFF.md"

    def test_handles_short_uri(self):
        uri = "viking://resources/proj"
        result = _source_doc(uri)
        assert isinstance(result, str)


class TestVikingRead:
    def test_reads_content(self):
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {"result": "hello world"}
        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.get.return_value = mock_response
            content = _viking_read("http://localhost:1933", "viking://resources/a.md")
            assert content == "hello world"

    def test_reads_content_dict_format(self):
        """Handles legacy dict format {result: {content: ...}} too."""
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {"result": {"content": "hello world"}}
        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.get.return_value = mock_response
            content = _viking_read("http://localhost:1933", "viking://resources/a.md")
            assert content == "hello world"

    def test_returns_empty_on_error(self):
        import requests

        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.get.side_effect = requests.Timeout()
            mock_req.ConnectionError = requests.ConnectionError
            mock_req.Timeout = requests.Timeout
            mock_req.ValueError = ValueError
            content = _viking_read("http://localhost:1933", "viking://resources/a.md")
            assert content == ""

    def test_truncates_long_content(self):
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {"result": "x" * 5000}
        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.get.return_value = mock_response
            content = _viking_read("http://localhost:1933", "viking://resources/a.md")
            assert len(content) == 3000


# --- Full tool tests ---


class TestNeuraltreePrecision:
    @pytest.mark.asyncio
    async def test_viking_unavailable(self, mcp_with_precision, tmp_project):
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=False):
            result = await mcp_with_precision.call_tool(
                "neuraltree_precision",
                {"queries": [{"text": "test"}], "project_root": str(tmp_project)},
            )
            data = json.loads(result.content[0].text)
            assert data["precision_at_3"] is None
            assert data["viking_available"] is False

    @pytest.mark.asyncio
    async def test_empty_queries(self, mcp_with_precision, tmp_project):
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=True):
            result = await mcp_with_precision.call_tool(
                "neuraltree_precision",
                {"queries": [], "project_root": str(tmp_project)},
            )
            data = json.loads(result.content[0].text)
            assert data["precision_at_3"] is None
            assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_returns_pending_verdicts(self, mcp_with_precision, tmp_project):
        """Results should have verdict=PENDING and include content for Claude to judge."""
        mock_results = [
            {"uri": "a.md", "score": 0.9, "abstract": ""},
            {"uri": "b.md", "score": 0.8, "abstract": ""},
            {"uri": "c.md", "score": 0.7, "abstract": ""},
        ]
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.precision._viking_search", return_value=mock_results), \
             patch("neuraltree_mcp.tools.precision._viking_read", return_value="relevant content"):
            result = await mcp_with_precision.call_tool(
                "neuraltree_precision",
                {
                    "queries": [{"text": "What is X?"}, {"text": "How does Y work?"}],
                    "project_root": str(tmp_project),
                },
            )
            data = json.loads(result.content[0].text)
            # precision_at_3 is None — Claude computes after judging
            assert data["precision_at_3"] is None
            assert data["total"] == 2
            assert len(data["query_results"]) == 2
            # Each judgment has verdict=PENDING and content
            for qr in data["query_results"]:
                assert len(qr["judgments"]) == 3
                for j in qr["judgments"]:
                    assert j["verdict"] == "PENDING"
                    assert j["content"] == "relevant content"
                    assert "uri" in j
                    assert "score" in j

    @pytest.mark.asyncio
    async def test_no_viking_results(self, mcp_with_precision, tmp_project):
        """Queries with no Viking results should return empty judgments."""
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.precision._viking_search", return_value=[]):
            result = await mcp_with_precision.call_tool(
                "neuraltree_precision",
                {"queries": [{"text": "obscure query"}], "project_root": str(tmp_project)},
            )
            data = json.loads(result.content[0].text)
            assert len(data["query_results"]) == 1
            assert data["query_results"][0]["judgments"] == []

    @pytest.mark.asyncio
    async def test_preserves_query_source(self, mcp_with_precision, tmp_project):
        mock_results = [{"uri": "a.md", "score": 0.9, "abstract": ""}]
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.precision._viking_search", return_value=mock_results), \
             patch("neuraltree_mcp.tools.precision._viking_read", return_value="content"):
            result = await mcp_with_precision.call_tool(
                "neuraltree_precision",
                {
                    "queries": [{"text": "test", "source": "claude_md"}],
                    "project_root": str(tmp_project),
                },
            )
            data = json.loads(result.content[0].text)
            assert data["query_results"][0]["source"] == "claude_md"

    @pytest.mark.asyncio
    async def test_invalid_project_root(self, mcp_with_precision):
        result = await mcp_with_precision.call_tool(
            "neuraltree_precision",
            {"queries": [{"text": "test"}], "project_root": "/nonexistent/path/xyz"},
        )
        data = json.loads(result.content[0].text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_limit_zero_returns_error(self, mcp_with_precision, tmp_project):
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=True):
            result = await mcp_with_precision.call_tool(
                "neuraltree_precision",
                {"queries": [{"text": "test"}], "project_root": str(tmp_project), "limit": 0},
            )
            data = json.loads(result.content[0].text)
            assert data["precision_at_3"] is None
            assert "limit must be >= 1" in data["warnings"][0]

    @pytest.mark.asyncio
    async def test_empty_text_queries_skipped(self, mcp_with_precision, tmp_project):
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=True):
            result = await mcp_with_precision.call_tool(
                "neuraltree_precision",
                {
                    "queries": [{"text": ""}, {"source": "no_text_field"}],
                    "project_root": str(tmp_project),
                },
            )
            data = json.loads(result.content[0].text)
            assert len(data["query_results"]) == 0
            assert data["precision_at_3"] is None
            assert len(data["warnings"]) >= 2

    @pytest.mark.asyncio
    async def test_content_included_for_judging(self, mcp_with_precision, tmp_project):
        """Content must be included so Claude can judge relevance."""
        mock_results = [{"uri": "doc.md", "score": 0.85, "abstract": ""}]
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.precision._viking_search", return_value=mock_results), \
             patch("neuraltree_mcp.tools.precision._viking_read", return_value="This is the architecture doc"):
            result = await mcp_with_precision.call_tool(
                "neuraltree_precision",
                {"queries": [{"text": "architecture"}], "project_root": str(tmp_project)},
            )
            data = json.loads(result.content[0].text)
            judgment = data["query_results"][0]["judgments"][0]
            assert judgment["content"] == "This is the architecture doc"
            assert judgment["verdict"] == "PENDING"

    @pytest.mark.asyncio
    async def test_total_reflects_input_count(self, mcp_with_precision, tmp_project):
        """total should be input query count."""
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.precision._viking_search", return_value=[]):
            result = await mcp_with_precision.call_tool(
                "neuraltree_precision",
                {
                    "queries": [{"text": "valid"}, {"text": ""}, {"text": "also valid"}],
                    "project_root": str(tmp_project),
                },
            )
            data = json.loads(result.content[0].text)
            assert data["total"] == 3  # input count
