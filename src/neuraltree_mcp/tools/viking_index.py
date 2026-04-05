"""neuraltree_viking_index — Batch-index files into Viking semantic search.

Handles the two-step Viking upload process:
  1. POST /api/v1/resources/temp_upload (multipart file upload)
  2. POST /api/v1/resources (register with target URI, wait for indexing)

Used by the Skill's Enforce step to re-index modified files after AutoLoop.
"""
from __future__ import annotations

import os
from pathlib import Path

import requests
from fastmcp import FastMCP

from neuraltree_mcp.validation import validate_project_root, validate_within_root

_DEFAULT_VIKING_URL = "http://localhost:1933"
_CONNECT_TIMEOUT = 5
_UPLOAD_TIMEOUT = 30
_INDEX_TIMEOUT = 120  # large files take time to embed


def _check_viking(viking_url: str) -> bool:
    """Return True if Viking is reachable."""
    try:
        r = requests.get(f"{viking_url}/health", timeout=_CONNECT_TIMEOUT)
        return r.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False


def _upload_and_index(
    viking_url: str, file_path: str, target_uri: str
) -> dict:
    """Upload a local file to Viking and index it. Returns status dict."""
    # Step 1: temp upload
    try:
        with open(file_path, "rb") as f:
            r = requests.post(
                f"{viking_url}/api/v1/resources/temp_upload",
                files={"file": (os.path.basename(file_path), f)},
                timeout=_UPLOAD_TIMEOUT,
            )
        if r.status_code != 200:
            return {"status": "error", "error": f"Upload failed: HTTP {r.status_code}"}
        temp_id = r.json().get("result", {}).get("temp_file_id")
        if not temp_id:
            return {"status": "error", "error": "No temp_file_id in upload response"}
    except (requests.ConnectionError, requests.Timeout, ValueError) as e:
        return {"status": "error", "error": f"Upload failed: {e}"}
    except OSError as e:
        return {"status": "error", "error": f"Cannot read file: {e}"}

    # Step 2: register resource
    try:
        r = requests.post(
            f"{viking_url}/api/v1/resources",
            json={
                "temp_file_id": temp_id,
                "to": target_uri,
                "wait": True,
                "timeout": _INDEX_TIMEOUT,
            },
            timeout=_INDEX_TIMEOUT + 10,
        )
        if r.status_code != 200:
            return {"status": "error", "error": f"Index failed: HTTP {r.status_code}"}
        data = r.json()
        if data.get("status") == "ok":
            return {"status": "ok", "uri": target_uri}
        return {"status": "error", "error": data.get("error", {}).get("message", "Unknown error")}
    except (requests.ConnectionError, requests.Timeout, ValueError) as e:
        return {"status": "error", "error": f"Index failed: {e}"}


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def neuraltree_viking_index(
        file_paths: list[str],
        project_root: str = ".",
        viking_url: str = _DEFAULT_VIKING_URL,
        parent_uri: str | None = None,
    ) -> dict:
        """Batch-index local files into Viking semantic search.

        For each file: uploads to Viking temp storage, then registers as a
        resource with wait=True so embeddings are ready immediately.

        Args:
            file_paths: Relative paths to files to index (relative to project_root).
            project_root: Project root directory.
            viking_url: Viking API base URL.
            parent_uri: Base URI for resources (e.g. "viking://resources/myproject").
                        If None, derives from project directory name.

        Returns:
            dict with indexed count, failed count, per-file results,
            and viking_available flag.
        """
        try:
            root = validate_project_root(project_root)
        except ValueError as e:
            return {"error": str(e)}

        if not file_paths:
            return {
                "indexed": 0,
                "failed": 0,
                "total": 0,
                "results": [],
                "viking_available": True,
                "warnings": ["No file_paths provided"],
            }

        if not _check_viking(viking_url):
            return {
                "indexed": 0,
                "failed": 0,
                "total": len(file_paths),
                "results": [],
                "viking_available": False,
                "warnings": ["Viking is not reachable — cannot index files"],
            }

        # Derive parent URI from project name if not provided
        if not parent_uri:
            project_name = root.name
            parent_uri = f"viking://resources/{project_name}"

        results = []
        warnings: list[str] = []
        indexed = 0
        failed = 0

        for rel_path in file_paths:
            # Block absolute paths before pathlib join (which discards root)
            if Path(rel_path).is_absolute():
                warnings.append(f"Skipping {rel_path}: absolute paths not allowed")
                failed += 1
                results.append({"path": rel_path, "status": "error", "error": "Absolute paths not allowed"})
                continue

            # Validate path is within project
            try:
                abs_path = root / rel_path
                validate_within_root(abs_path, root)
            except ValueError as e:
                warnings.append(f"Skipping {rel_path}: {e}")
                failed += 1
                results.append({"path": rel_path, "status": "error", "error": str(e)})
                continue

            if not abs_path.exists():
                warnings.append(f"Skipping {rel_path}: file not found")
                failed += 1
                results.append({"path": rel_path, "status": "error", "error": "File not found"})
                continue

            # Build target URI: parent_uri/relative_path (slashes replaced with underscores for flat namespace)
            uri_name = rel_path.replace("/", "_").replace("\\", "_")
            target_uri = f"{parent_uri}/{uri_name}"

            result = _upload_and_index(viking_url, str(abs_path), target_uri)
            result["path"] = rel_path
            results.append(result)

            if result["status"] == "ok":
                indexed += 1
            else:
                failed += 1
                warnings.append(f"Failed to index {rel_path}: {result.get('error', 'unknown')}")

        return {
            "indexed": indexed,
            "failed": failed,
            "total": len(file_paths),
            "results": results,
            "viking_available": True,
            "warnings": warnings,
        }
