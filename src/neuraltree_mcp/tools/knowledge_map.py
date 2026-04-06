"""neuraltree_knowledge_map — Save, load, and query a dual-layer knowledge map."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from neuraltree_mcp.validation import validate_project_root


KNOWLEDGE_MAP_FILE = ".neuraltree/knowledge_map.json"
REQUIRED_MAP_KEYS = {"files", "edges"}


def _has_path_traversal(path: str) -> bool:
    """Return True if a path contains traversal sequences or is absolute."""
    return Path(path).is_absolute() or ".." in Path(path).parts


def _validate_map_paths(knowledge_map: dict) -> str | None:
    """Validate that file paths in the knowledge map don't contain traversal.

    Returns:
        An error message string if invalid, or None if all paths are safe.
    """
    for fp in knowledge_map.get("files", {}):
        if _has_path_traversal(fp):
            return f"Invalid file path in knowledge map: {fp}"
    for edge in knowledge_map.get("edges", []):
        for key in ("source", "target"):
            val = edge.get(key, "")
            if _has_path_traversal(val):
                return f"Invalid edge {key} path in knowledge map: {val}"
    return None


def _save_map(knowledge_map: dict, project_root: str) -> Path:
    """Save a knowledge map to .neuraltree/knowledge_map.json.

    Args:
        knowledge_map: The knowledge map dict to persist.
        project_root: Project root directory.

    Returns:
        Path to the saved file.

    Raises:
        ValueError: If any file path in the map contains path traversal.
        OSError: If directory creation or file write fails.
    """
    err = _validate_map_paths(knowledge_map)
    if err:
        raise ValueError(err)
    root = validate_project_root(project_root)
    nt_dir = root / ".neuraltree"
    nt_dir.mkdir(parents=True, exist_ok=True)
    target = nt_dir / "knowledge_map.json"
    target.write_text(json.dumps(knowledge_map, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def _load_map(project_root: str) -> dict | None:
    """Load a knowledge map from .neuraltree/knowledge_map.json.

    Args:
        project_root: Project root directory.

    Returns:
        The knowledge map dict, or None if the file does not exist.
        If the file exists but is corrupt, returns ``{"error": "..."}``.
    """
    root = validate_project_root(project_root)
    target = root / ".neuraltree" / "knowledge_map.json"
    if not target.exists():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"error": f"knowledge_map.json exists but is corrupt: {exc}"}
    except OSError as exc:
        return {"error": f"knowledge_map.json exists but cannot be read: {exc}"}
    if not isinstance(data, dict):
        return {"error": "knowledge_map.json has invalid schema: not a dict"}
    if not REQUIRED_MAP_KEYS.issubset(data.keys()):
        missing = REQUIRED_MAP_KEYS - data.keys()
        return {"error": f"knowledge_map.json has invalid schema: missing keys {missing}"}
    return data


def _query_map(
    project_root: str,
    file_path: str | None = None,
    cluster: str | None = None,
    neighbors_of: str | None = None,
    issues_only: bool = False,
) -> dict:
    """Query the knowledge map.

    Args:
        project_root: Project root directory.
        file_path: Return data for a specific file.
        cluster: Return data for a specific cluster by name.
        neighbors_of: Return all files connected to this file (both directions).
        issues_only: If True, return only the issues list.

    Returns:
        dict with query results, or error if map is missing / query fails.
    """
    km = _load_map(project_root)
    if km is None:
        return {"error": "No knowledge map found. Run save first."}
    if "error" in km:
        return km

    # Query by file
    if file_path is not None:
        files = km.get("files", {})
        if file_path not in files:
            return {"error": f"File not in knowledge map: {file_path}"}
        return {"file": files[file_path], "path": file_path}

    # Query by cluster
    if cluster is not None:
        for c in km.get("clusters", []):
            if c["name"] == cluster:
                return {"cluster": c}
        return {"error": f"Cluster not found: {cluster}"}

    # Query neighbors (both directions)
    if neighbors_of is not None:
        edges = km.get("edges", [])
        neighbors: list[dict] = []
        for edge in edges:
            if edge["source"] == neighbors_of:
                neighbors.append({
                    "file": edge["target"],
                    "type": edge["type"],
                    "weight": edge["weight"],
                    "direction": "outbound",
                })
            elif edge["target"] == neighbors_of:
                neighbors.append({
                    "file": edge["source"],
                    "type": edge["type"],
                    "weight": edge["weight"],
                    "direction": "inbound",
                })
        return {"neighbors": neighbors, "file": neighbors_of}

    # Issues only
    if issues_only:
        return {"issues": km.get("issues", [])}

    # Default: return full stats
    return {"stats": km.get("stats", {}), "version": km.get("version"), "project_name": km.get("project_name")}


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def neuraltree_knowledge_map(
        action: str,
        project_root: str = ".",
        knowledge_map: dict | None = None,
        file_path: str | None = None,
        cluster: str | None = None,
        neighbors_of: str | None = None,
        issues_only: bool = False,
    ) -> dict:
        """Save, load, or query a dual-layer knowledge map (file graph + concept clusters).

        Actions:
          - save: Persist a knowledge map to .neuraltree/knowledge_map.json
          - load: Load the knowledge map from disk
          - query: Query by file_path, cluster, neighbors_of, or issues_only

        Query filters are mutually exclusive. If multiple are supplied,
        priority: file_path > cluster > neighbors_of > issues_only.

        Args:
            action: One of 'save', 'load', 'query'.
            project_root: Project root directory.
            knowledge_map: The map dict to save (required for 'save' action).
            file_path: Query filter — return data for a specific file.
            cluster: Query filter — return data for a specific cluster by name.
            neighbors_of: Query filter — return all connected files (both directions).
            issues_only: Query filter — return only issues list.

        Returns:
            dict with action result or error.
        """
        try:
            validate_project_root(project_root)
        except (ValueError, OSError) as e:
            return {"error": str(e)}

        if action == "save":
            if knowledge_map is None:
                return {"error": "knowledge_map is required for save action"}
            try:
                path = _save_map(knowledge_map, project_root)
                return {"saved": str(path), "files": len(knowledge_map.get("files", {}))}
            except (OSError, ValueError) as e:
                return {"error": f"Failed to save: {e}"}

        elif action == "load":
            km = _load_map(project_root)
            if km is None:
                return {"error": "No knowledge map found"}
            if "error" in km:
                return km
            return {"knowledge_map": km}

        elif action == "query":
            return _query_map(
                project_root,
                file_path=file_path,
                cluster=cluster,
                neighbors_of=neighbors_of,
                issues_only=issues_only,
            )

        else:
            return {"error": f"Unknown action: {action}. Use 'save', 'load', or 'query'."}
