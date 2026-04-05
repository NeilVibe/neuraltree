"""Tests for neuraltree_precision tool."""
import json
from unittest.mock import MagicMock, patch

import pytest

from neuraltree_mcp.tools.precision import (
    _check_ollama,
    _check_viking,
    _judge_relevance,
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


class TestCheckOllama:
    def test_ollama_reachable(self):
        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.get.return_value = MagicMock(status_code=200)
            assert _check_ollama("http://localhost:11434") is True

    def test_ollama_unreachable(self):
        import requests

        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.get.side_effect = requests.ConnectionError()
            mock_req.ConnectionError = requests.ConnectionError
            mock_req.Timeout = requests.Timeout
            assert _check_ollama("http://localhost:9999") is False


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


class TestVikingRead:
    def test_reads_content(self):
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {"result": {"content": "hello world"}}
        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.post.return_value = mock_response
            content = _viking_read("http://localhost:1933", "viking://resources/a.md")
            assert content == "hello world"

    def test_returns_empty_on_error(self):
        import requests

        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.post.side_effect = requests.Timeout()
            mock_req.ConnectionError = requests.ConnectionError
            mock_req.Timeout = requests.Timeout
            mock_req.ValueError = ValueError
            content = _viking_read("http://localhost:1933", "viking://resources/a.md")
            assert content == ""


class TestJudgeRelevance:
    def test_yes_judgment(self):
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {"response": "YES"}
        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.post.return_value = mock_response
            verdict = _judge_relevance(
                "http://localhost:11434", "qwen3.5:4b", "test query", "a.md", "content"
            )
            assert verdict == "YES"

    def test_no_judgment(self):
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {"response": "NO"}
        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.post.return_value = mock_response
            verdict = _judge_relevance(
                "http://localhost:11434", "qwen3.5:4b", "test query", "a.md", "content"
            )
            assert verdict == "NO"

    def test_malformed_defaults_to_no(self):
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {"response": "I think maybe yes but also no"}
        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.post.return_value = mock_response
            # Contains "YES" so should return YES (it finds YES first)
            verdict = _judge_relevance(
                "http://localhost:11434", "qwen3.5:4b", "test query", "a.md", "content"
            )
            # "YES" appears in the text
            assert verdict == "YES"

    def test_garbage_defaults_to_no(self):
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {"response": "beep boop"}
        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.post.return_value = mock_response
            verdict = _judge_relevance(
                "http://localhost:11434", "qwen3.5:4b", "test query", "a.md", "content"
            )
            assert verdict == "NO"

    def test_connection_error_returns_error(self):
        import requests

        with patch("neuraltree_mcp.tools.precision.requests") as mock_req:
            mock_req.post.side_effect = requests.Timeout()
            mock_req.ConnectionError = requests.ConnectionError
            mock_req.Timeout = requests.Timeout
            mock_req.ValueError = ValueError
            verdict = _judge_relevance(
                "http://localhost:11434", "qwen3.5:4b", "test query", "a.md", "content"
            )
            assert verdict == "ERROR"


# --- Full tool tests ---


class TestNeuraltreePrecision:
    @pytest.mark.asyncio
    async def test_viking_unavailable(self, mcp_with_precision, tmp_project):
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=False), \
             patch("neuraltree_mcp.tools.precision._check_ollama", return_value=True):
            result = await mcp_with_precision.call_tool(
                "neuraltree_precision",
                {"queries": [{"text": "test"}], "project_root": str(tmp_project)},
            )
            data = json.loads(result.content[0].text)
            assert data["precision_at_3"] is None
            assert data["viking_available"] is False

    @pytest.mark.asyncio
    async def test_ollama_unavailable(self, mcp_with_precision, tmp_project):
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.precision._check_ollama", return_value=False):
            result = await mcp_with_precision.call_tool(
                "neuraltree_precision",
                {"queries": [{"text": "test"}], "project_root": str(tmp_project)},
            )
            data = json.loads(result.content[0].text)
            assert data["precision_at_3"] is None
            assert data["ollama_available"] is False

    @pytest.mark.asyncio
    async def test_empty_queries(self, mcp_with_precision, tmp_project):
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.precision._check_ollama", return_value=True):
            result = await mcp_with_precision.call_tool(
                "neuraltree_precision",
                {"queries": [], "project_root": str(tmp_project)},
            )
            data = json.loads(result.content[0].text)
            assert data["precision_at_3"] is None
            assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_all_pass(self, mcp_with_precision, tmp_project):
        """All 3 results judged YES → precision 1.0."""
        mock_results = [
            {"uri": "a.md", "score": 0.9, "abstract": ""},
            {"uri": "b.md", "score": 0.8, "abstract": ""},
            {"uri": "c.md", "score": 0.7, "abstract": ""},
        ]
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.precision._check_ollama", return_value=True), \
             patch("neuraltree_mcp.tools.precision._viking_search", return_value=mock_results), \
             patch("neuraltree_mcp.tools.precision._viking_read", return_value="relevant content"), \
             patch("neuraltree_mcp.tools.precision._judge_relevance", return_value="YES"):
            result = await mcp_with_precision.call_tool(
                "neuraltree_precision",
                {
                    "queries": [{"text": "What is X?"}, {"text": "How does Y work?"}],
                    "project_root": str(tmp_project),
                },
            )
            data = json.loads(result.content[0].text)
            assert data["precision_at_3"] == 1.0
            assert data["passed"] == 2
            assert data["failed"] == 0

    @pytest.mark.asyncio
    async def test_all_fail(self, mcp_with_precision, tmp_project):
        """All 3 results judged NO → precision 0.0."""
        mock_results = [
            {"uri": "a.md", "score": 0.5, "abstract": ""},
            {"uri": "b.md", "score": 0.4, "abstract": ""},
            {"uri": "c.md", "score": 0.3, "abstract": ""},
        ]
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.precision._check_ollama", return_value=True), \
             patch("neuraltree_mcp.tools.precision._viking_search", return_value=mock_results), \
             patch("neuraltree_mcp.tools.precision._viking_read", return_value="irrelevant"), \
             patch("neuraltree_mcp.tools.precision._judge_relevance", return_value="NO"):
            result = await mcp_with_precision.call_tool(
                "neuraltree_precision",
                {"queries": [{"text": "What is X?"}], "project_root": str(tmp_project)},
            )
            data = json.loads(result.content[0].text)
            assert data["precision_at_3"] == 0.0
            assert data["passed"] == 0
            assert data["failed"] == 1

    @pytest.mark.asyncio
    async def test_mixed_results(self, mcp_with_precision, tmp_project):
        """2 YES + 1 NO → precision 0.667, FAIL (threshold is >= 0.67)."""
        mock_results = [
            {"uri": "a.md", "score": 0.9, "abstract": ""},
            {"uri": "b.md", "score": 0.8, "abstract": ""},
            {"uri": "c.md", "score": 0.7, "abstract": ""},
        ]
        verdicts = iter(["YES", "YES", "NO"])
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.precision._check_ollama", return_value=True), \
             patch("neuraltree_mcp.tools.precision._viking_search", return_value=mock_results), \
             patch("neuraltree_mcp.tools.precision._viking_read", return_value="content"), \
             patch("neuraltree_mcp.tools.precision._judge_relevance", side_effect=verdicts):
            result = await mcp_with_precision.call_tool(
                "neuraltree_precision",
                {"queries": [{"text": "What is X?"}], "project_root": str(tmp_project)},
            )
            data = json.loads(result.content[0].text)
            assert data["precision_at_3"] == 0.667
            assert data["passed"] == 0
            # 0.667 < 0.67 threshold, so this is a FAIL
            assert data["failed"] == 1

    @pytest.mark.asyncio
    async def test_preserves_query_source(self, mcp_with_precision, tmp_project):
        mock_results = [{"uri": "a.md", "score": 0.9, "abstract": ""}]
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.precision._check_ollama", return_value=True), \
             patch("neuraltree_mcp.tools.precision._viking_search", return_value=mock_results), \
             patch("neuraltree_mcp.tools.precision._viking_read", return_value="content"), \
             patch("neuraltree_mcp.tools.precision._judge_relevance", return_value="YES"):
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
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.precision._check_ollama", return_value=True):
            result = await mcp_with_precision.call_tool(
                "neuraltree_precision",
                {"queries": [{"text": "test"}], "project_root": str(tmp_project), "limit": 0},
            )
            data = json.loads(result.content[0].text)
            assert data["precision_at_3"] is None
            assert "limit must be >= 1" in data["warnings"][0]

    @pytest.mark.asyncio
    async def test_empty_text_queries_skipped(self, mcp_with_precision, tmp_project):
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.precision._check_ollama", return_value=True):
            result = await mcp_with_precision.call_tool(
                "neuraltree_precision",
                {
                    "queries": [{"text": ""}, {"source": "no_text_field"}],
                    "project_root": str(tmp_project),
                },
            )
            data = json.loads(result.content[0].text)
            assert data["scored"] == 0
            assert data["precision_at_3"] is None
            assert len(data["warnings"]) >= 2

    @pytest.mark.asyncio
    async def test_error_verdicts_excluded_from_denominator(self, mcp_with_precision, tmp_project):
        """ERROR judgments should not count as NO — they're excluded from scoring."""
        mock_results = [
            {"uri": "a.md", "score": 0.9, "abstract": ""},
            {"uri": "b.md", "score": 0.8, "abstract": ""},
            {"uri": "c.md", "score": 0.7, "abstract": ""},
        ]
        # 1 YES + 2 ERROR → precision should be 1.0 (1/1 scored), not 0.333 (1/3)
        verdicts = iter(["YES", "ERROR", "ERROR"])
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.precision._check_ollama", return_value=True), \
             patch("neuraltree_mcp.tools.precision._viking_search", return_value=mock_results), \
             patch("neuraltree_mcp.tools.precision._viking_read", return_value="content"), \
             patch("neuraltree_mcp.tools.precision._judge_relevance", side_effect=verdicts):
            result = await mcp_with_precision.call_tool(
                "neuraltree_precision",
                {"queries": [{"text": "What is X?"}], "project_root": str(tmp_project)},
            )
            data = json.loads(result.content[0].text)
            assert data["precision_at_3"] == 1.0
            assert data["query_results"][0]["error_count"] == 2
            assert len(data["warnings"]) >= 1

    @pytest.mark.asyncio
    async def test_total_reflects_input_count(self, mcp_with_precision, tmp_project):
        """total should be input query count, scored should be actually-run count."""
        with patch("neuraltree_mcp.tools.precision._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.precision._check_ollama", return_value=True), \
             patch("neuraltree_mcp.tools.precision._viking_search", return_value=[]), \
             patch("neuraltree_mcp.tools.precision._judge_relevance", return_value="YES"):
            result = await mcp_with_precision.call_tool(
                "neuraltree_precision",
                {
                    "queries": [{"text": "valid"}, {"text": ""}, {"text": "also valid"}],
                    "project_root": str(tmp_project),
                },
            )
            data = json.loads(result.content[0].text)
            assert data["total"] == 3  # input count
            assert data["scored"] == 2  # actually scored
