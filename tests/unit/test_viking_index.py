"""Tests for neuraltree_viking_index tool."""
import json
import os
from unittest.mock import MagicMock, patch

import pytest

from neuraltree_mcp.tools.viking_index import _check_viking, _upload_and_index, register


@pytest.fixture
def mcp_with_viking_index():
    """Register viking_index tool and return mcp instance."""
    from fastmcp import FastMCP

    mcp = FastMCP("test")
    register(mcp)
    return mcp


class TestCheckViking:
    def test_reachable(self):
        with patch("neuraltree_mcp.tools.viking_index.requests") as mock_req:
            mock_req.get.return_value = MagicMock(status_code=200)
            assert _check_viking("http://localhost:1933") is True

    def test_unreachable(self):
        import requests

        with patch("neuraltree_mcp.tools.viking_index.requests") as mock_req:
            mock_req.get.side_effect = requests.ConnectionError()
            mock_req.ConnectionError = requests.ConnectionError
            mock_req.Timeout = requests.Timeout
            assert _check_viking("http://localhost:9999") is False


class TestUploadAndIndex:
    def test_success(self, tmp_path):
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\nContent here")

        upload_resp = MagicMock(status_code=200)
        upload_resp.json.return_value = {"result": {"temp_file_id": "temp_123"}}

        index_resp = MagicMock(status_code=200)
        index_resp.json.return_value = {"status": "ok"}

        with patch("neuraltree_mcp.tools.viking_index.requests") as mock_req:
            mock_req.post.side_effect = [upload_resp, index_resp]
            result = _upload_and_index(
                "http://localhost:1933",
                str(test_file),
                "viking://resources/test/test.md",
            )
            assert result["status"] == "ok"
            assert result["uri"] == "viking://resources/test/test.md"

    def test_upload_fails(self, tmp_path):
        test_file = tmp_path / "test.md"
        test_file.write_text("content")

        upload_resp = MagicMock(status_code=500)
        with patch("neuraltree_mcp.tools.viking_index.requests") as mock_req:
            mock_req.post.return_value = upload_resp
            result = _upload_and_index(
                "http://localhost:1933", str(test_file), "viking://test"
            )
            assert result["status"] == "error"
            assert "Upload failed" in result["error"]

    def test_index_fails(self, tmp_path):
        test_file = tmp_path / "test.md"
        test_file.write_text("content")

        upload_resp = MagicMock(status_code=200)
        upload_resp.json.return_value = {"result": {"temp_file_id": "temp_123"}}

        index_resp = MagicMock(status_code=200)
        index_resp.json.return_value = {
            "status": "error",
            "error": {"message": "Duplicate URI"},
        }

        with patch("neuraltree_mcp.tools.viking_index.requests") as mock_req:
            mock_req.post.side_effect = [upload_resp, index_resp]
            result = _upload_and_index(
                "http://localhost:1933", str(test_file), "viking://test"
            )
            assert result["status"] == "error"
            assert "Duplicate URI" in result["error"]

    def test_upload_missing_temp_id(self, tmp_path):
        test_file = tmp_path / "test.md"
        test_file.write_text("content")

        upload_resp = MagicMock(status_code=200)
        upload_resp.json.return_value = {"result": {}}  # no temp_file_id

        with patch("neuraltree_mcp.tools.viking_index.requests") as mock_req:
            mock_req.post.return_value = upload_resp
            result = _upload_and_index(
                "http://localhost:1933", str(test_file), "viking://test"
            )
            assert result["status"] == "error"
            assert "temp_file_id" in result["error"]

    def test_file_not_found(self):
        result = _upload_and_index(
            "http://localhost:1933",
            "/nonexistent/file.md",
            "viking://test",
        )
        assert result["status"] == "error"
        assert "Cannot read file" in result["error"]

    def test_connection_error(self, tmp_path):
        import requests

        test_file = tmp_path / "test.md"
        test_file.write_text("content")

        with patch("neuraltree_mcp.tools.viking_index.requests") as mock_req:
            mock_req.post.side_effect = requests.ConnectionError("refused")
            mock_req.ConnectionError = requests.ConnectionError
            mock_req.Timeout = requests.Timeout
            result = _upload_and_index(
                "http://localhost:1933", str(test_file), "viking://test"
            )
            assert result["status"] == "error"


class TestNeuraltreeVikingIndex:
    @pytest.mark.asyncio
    async def test_viking_unavailable(self, mcp_with_viking_index, tmp_project):
        with patch("neuraltree_mcp.tools.viking_index._check_viking", return_value=False):
            result = await mcp_with_viking_index.call_tool(
                "neuraltree_viking_index",
                {"file_paths": ["CLAUDE.md"], "project_root": str(tmp_project)},
            )
            data = json.loads(result.content[0].text)
            assert data["viking_available"] is False
            assert data["indexed"] == 0

    @pytest.mark.asyncio
    async def test_index_single_file(self, mcp_with_viking_index, tmp_project):
        with patch("neuraltree_mcp.tools.viking_index._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.viking_index._upload_and_index") as mock_upload:
            mock_upload.return_value = {
                "status": "ok",
                "uri": "viking://resources/mock_project/CLAUDE.md",
            }
            result = await mcp_with_viking_index.call_tool(
                "neuraltree_viking_index",
                {"file_paths": ["CLAUDE.md"], "project_root": str(tmp_project)},
            )
            data = json.loads(result.content[0].text)
            assert data["indexed"] == 1
            assert data["failed"] == 0
            assert data["viking_available"] is True

    @pytest.mark.asyncio
    async def test_index_multiple_files(self, mcp_with_viking_index, tmp_project):
        with patch("neuraltree_mcp.tools.viking_index._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.viking_index._upload_and_index") as mock_upload:
            mock_upload.return_value = {"status": "ok", "uri": "viking://test"}
            result = await mcp_with_viking_index.call_tool(
                "neuraltree_viking_index",
                {
                    "file_paths": ["CLAUDE.md", "memory/MEMORY.md"],
                    "project_root": str(tmp_project),
                },
            )
            data = json.loads(result.content[0].text)
            assert data["indexed"] == 2
            assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_file_not_found(self, mcp_with_viking_index, tmp_project):
        with patch("neuraltree_mcp.tools.viking_index._check_viking", return_value=True):
            result = await mcp_with_viking_index.call_tool(
                "neuraltree_viking_index",
                {
                    "file_paths": ["nonexistent.md"],
                    "project_root": str(tmp_project),
                },
            )
            data = json.loads(result.content[0].text)
            assert data["indexed"] == 0
            assert data["failed"] == 1

    @pytest.mark.asyncio
    async def test_custom_parent_uri(self, mcp_with_viking_index, tmp_project):
        with patch("neuraltree_mcp.tools.viking_index._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.viking_index._upload_and_index") as mock_upload:
            mock_upload.return_value = {"status": "ok", "uri": "viking://custom/CLAUDE.md"}
            result = await mcp_with_viking_index.call_tool(
                "neuraltree_viking_index",
                {
                    "file_paths": ["CLAUDE.md"],
                    "project_root": str(tmp_project),
                    "parent_uri": "viking://custom",
                },
            )
            data = json.loads(result.content[0].text)
            assert data["indexed"] == 1
            # Verify the upload was called with the custom URI
            call_args = mock_upload.call_args
            assert "viking://custom/" in call_args[0][2]

    @pytest.mark.asyncio
    async def test_partial_failure(self, mcp_with_viking_index, tmp_project):
        """One file succeeds, one fails."""
        def mock_upload_fn(url, path, uri):
            if "CLAUDE" in path:
                return {"status": "ok", "uri": uri}
            return {"status": "error", "error": "Upload failed"}

        with patch("neuraltree_mcp.tools.viking_index._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.viking_index._upload_and_index", side_effect=mock_upload_fn):
            result = await mcp_with_viking_index.call_tool(
                "neuraltree_viking_index",
                {
                    "file_paths": ["CLAUDE.md", "memory/reference/auth.md"],
                    "project_root": str(tmp_project),
                },
            )
            data = json.loads(result.content[0].text)
            assert data["indexed"] == 1
            assert data["failed"] == 1
            assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_derives_project_name(self, mcp_with_viking_index, tmp_project):
        """When no parent_uri, should use project dir name."""
        with patch("neuraltree_mcp.tools.viking_index._check_viking", return_value=True), \
             patch("neuraltree_mcp.tools.viking_index._upload_and_index") as mock_upload:
            mock_upload.return_value = {"status": "ok", "uri": "viking://test"}
            await mcp_with_viking_index.call_tool(
                "neuraltree_viking_index",
                {"file_paths": ["CLAUDE.md"], "project_root": str(tmp_project)},
            )
            call_args = mock_upload.call_args
            target_uri = call_args[0][2]
            # Should contain the project dir name "mock_project"
            assert "mock_project" in target_uri

    @pytest.mark.asyncio
    async def test_path_traversal_rejected(self, mcp_with_viking_index, tmp_project):
        with patch("neuraltree_mcp.tools.viking_index._check_viking", return_value=True):
            result = await mcp_with_viking_index.call_tool(
                "neuraltree_viking_index",
                {
                    "file_paths": ["../../etc/passwd"],
                    "project_root": str(tmp_project),
                },
            )
            data = json.loads(result.content[0].text)
            assert data["failed"] == 1
            assert data["indexed"] == 0

    @pytest.mark.asyncio
    async def test_absolute_path_rejected(self, mcp_with_viking_index, tmp_project):
        with patch("neuraltree_mcp.tools.viking_index._check_viking", return_value=True):
            result = await mcp_with_viking_index.call_tool(
                "neuraltree_viking_index",
                {
                    "file_paths": ["/etc/passwd"],
                    "project_root": str(tmp_project),
                },
            )
            data = json.loads(result.content[0].text)
            assert data["failed"] == 1
            assert data["indexed"] == 0
            assert "absolute" in data["results"][0]["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_project_root(self, mcp_with_viking_index):
        result = await mcp_with_viking_index.call_tool(
            "neuraltree_viking_index",
            {"file_paths": ["test.md"], "project_root": "/nonexistent/path/xyz"},
        )
        data = json.loads(result.content[0].text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_empty_file_paths(self, mcp_with_viking_index, tmp_project):
        result = await mcp_with_viking_index.call_tool(
            "neuraltree_viking_index",
            {"file_paths": [], "project_root": str(tmp_project)},
        )
        data = json.loads(result.content[0].text)
        assert data["total"] == 0
        assert data["viking_available"] is True
        assert "No file_paths" in data["warnings"][0]
