"""neuraltree_knowledge_map — Save, load, query, and build a dual-layer knowledge map."""
from __future__ import annotations

import json
import os
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
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


def _ensure_list(value: Any, field_name: str) -> list:
    """Coerce a value to a list. Strings are wrapped, tuples/sets converted, others become empty."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    if isinstance(value, (tuple, set, frozenset)):
        return list(value)
    return []


def _build_map(
    explorer_reports: list[dict],
    project_root: str,
    semantic_edges: list[dict] | None = None,
) -> dict:
    """Build a complete knowledge map from explorer reports.

    Deterministically computes:
    - Merged file inventory from all explorer reports
    - Reference edges (explicit references between known files)
    - Semantic edges (provided by caller via Viking/Model2Vec, or empty)
    - Co-location edges (same directory, only if no stronger edge exists)
    - Greedy concept clusters (seed by most concepts, expand by 2+ shared)
    - Graph-derived issues (orphans, scattered clusters)
    - Summary stats

    Args:
        explorer_reports: List of explorer report dicts, each with "files",
                          "directories", and optionally "observations" keys.
                          Each file entry must have at least "path".
        project_root: Project root directory (for project_name).
        semantic_edges: Optional list of pre-computed semantic edges from
                        Viking/Model2Vec. Each edge: {"source": str, "target": str,
                        "weight": float, "reason": str}. When provided, these
                        replace internal similarity computation.

    Returns:
        Complete knowledge map dict ready for _save_map().
    """
    # Step 1: Merge file reports (union concepts/refs/issues across agents)
    files: dict[str, dict] = {}
    warnings: list[str] = []
    for report in explorer_reports:
        for file_report in report.get("files", []):
            path = file_report.get("path", "")
            if not path:
                continue
            if _has_path_traversal(path):
                warnings.append(f"Skipped path traversal: {path}")
                continue
            # Coerce list fields to prevent character-level iteration on strings
            file_report["key_concepts"] = _ensure_list(file_report.get("key_concepts"), "key_concepts")
            file_report["references_to"] = _ensure_list(file_report.get("references_to"), "references_to")
            file_report["issues"] = _ensure_list(file_report.get("issues"), "issues")
            if path in files:
                # Merge: union concepts, refs, issues from multiple agents
                existing = files[path]
                existing["key_concepts"] = sorted(set(existing.get("key_concepts", []))
                                                  | set(file_report.get("key_concepts", [])))
                existing["references_to"] = sorted(set(existing.get("references_to", []))
                                                   | set(file_report.get("references_to", [])))
                existing["issues"] = list({*existing.get("issues", []), *file_report.get("issues", [])})
                # Keep larger size_lines
                existing["size_lines"] = max(
                    existing.get("size_lines", 0),
                    file_report.get("size_lines", 0),
                )
            else:
                files[path] = file_report

    # Step 2A: Reference edges (only between known files)
    # Reference edges are directional: A→B and B→A are both valid.
    edges: list[dict] = []
    ref_set: set[tuple[str, str]] = set()  # dedup same-direction refs only
    for path, file_data in files.items():
        for ref in file_data.get("references_to", []):
            if ref in files and ref != path:
                pair = (path, ref)
                if pair not in ref_set:
                    edges.append({
                        "source": path,
                        "target": ref,
                        "type": "reference",
                        "weight": 1.0,
                    })
                    ref_set.add(pair)

    # Step 2B: Semantic edges (provided by caller via Viking/Model2Vec)
    # The skill queries Viking for semantic neighbors and passes them here.
    # Only edges between known files are included. Best weight wins on dedup.
    if semantic_edges:
        sem_best: dict[tuple[str, str], dict] = {}
        for se in semantic_edges:
            if not isinstance(se, dict):
                warnings.append(f"Skipped non-dict semantic edge: {type(se).__name__}")
                continue
            src = se.get("source", "")
            tgt = se.get("target", "")
            if src in files and tgt in files and src != tgt:
                weight = se.get("weight", 0.8)
                if not isinstance(weight, (int, float)):
                    warnings.append(f"Skipped semantic edge {src}->{tgt}: weight is not a number")
                    continue
                pair = tuple(sorted((src, tgt)))
                edge_data = {
                    "source": src,
                    "target": tgt,
                    "type": "semantic",
                    "weight": round(weight, 3),
                    "reason": se.get("reason", "Viking similarity"),
                }
                if pair not in sem_best or weight > sem_best[pair]["weight"]:
                    sem_best[pair] = edge_data
        edges.extend(sem_best.values())

    # Step 2C: Co-location edges (same directory, only if no stronger edge exists)
    # "Stronger" means any reference or semantic edge between the pair.
    all_connected: set[tuple[str, str]] = set()
    for e in edges:
        all_connected.add((e["source"], e["target"]))
        all_connected.add((e["target"], e["source"]))

    dir_groups: dict[str, list[str]] = defaultdict(list)
    for path in files:
        dir_groups[os.path.dirname(path) or "."].append(path)

    for members in dir_groups.values():
        if len(members) <= 1:
            continue
        sorted_members = sorted(members)
        for i, a in enumerate(sorted_members):
            for b in sorted_members[i + 1:]:
                if (a, b) not in all_connected:
                    edges.append({
                        "source": a,
                        "target": b,
                        "type": "co-located",
                        "weight": 0.5,
                    })

    # Step 3: Greedy concept clustering
    unclustered = set(files.keys())
    clusters: list[dict] = []

    while unclustered:
        # Seed: file with most concepts (sorted for deterministic tie-breaking)
        seed = max(sorted(unclustered), key=lambda p: len(files[p].get("key_concepts", [])))
        cluster_files = {seed}
        seed_concepts = set(files[seed].get("key_concepts", []))

        # Expand: add files sharing 2+ concepts with the growing cluster
        for other in sorted(unclustered):
            if other == seed:
                continue
            other_concepts = set(files[other].get("key_concepts", []))
            if len(seed_concepts & other_concepts) >= 2:
                cluster_files.add(other)
                seed_concepts |= other_concepts

        # Name from top concepts
        concept_counts: Counter = Counter()
        for f in cluster_files:
            concept_counts.update(files[f].get("key_concepts", []))
        top_concepts = [c for c, _ in concept_counts.most_common(3)]
        cluster_name = "_".join(top_concepts[:2]) if top_concepts else "unnamed"

        clusters.append({
            "name": cluster_name,
            "concept": ", ".join(top_concepts),
            "files": sorted(cluster_files),
        })
        unclustered -= cluster_files

    # Step 4: Graph-derived issues
    issues: list[dict] = []

    # Issues from explorer file reports
    for path, data in files.items():
        for issue_desc in data.get("issues", []):
            issues.append({
                "type": "explorer_finding",
                "file": path,
                "description": issue_desc,
                "severity": "medium",
            })

    # Orphan files (no edges at all)
    connected = {e["source"] for e in edges} | {e["target"] for e in edges}
    for path in sorted(files.keys()):
        if path not in connected:
            issues.append({
                "type": "orphan",
                "file": path,
                "description": f"{path} has no connections to any other file",
                "severity": "high",
            })

    # Scattered clusters (spanning 3+ directories)
    for cluster in clusters:
        dirs_in_cluster = {os.path.dirname(f) or "." for f in cluster["files"]}
        if len(dirs_in_cluster) >= 3:
            issues.append({
                "type": "scattered_cluster",
                "cluster": cluster["name"],
                "description": (
                    f"Cluster '{cluster['name']}' spans {len(dirs_in_cluster)} "
                    f"directories: {sorted(dirs_in_cluster)}"
                ),
                "severity": "medium",
            })

    # Step 5: Stats (only count files that reported size_lines > 0)
    file_sizes = [d.get("size_lines", 0) for d in files.values() if d.get("size_lines", 0) > 0]
    max_depth = max((f.count("/") for f in files), default=0)

    knowledge_map = {
        "version": 2,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project_name": os.path.basename(os.path.abspath(project_root)),
        "files": files,
        "edges": edges,
        "clusters": clusters,
        "issues": issues,
        "warnings": warnings,
        "stats": {
            "total_files": len(files),
            "total_edges": len(edges),
            "total_clusters": len(clusters),
            "total_issues": len(issues),
            "avg_file_size": round(statistics.mean(file_sizes)) if file_sizes else 0,
            "median_file_size": round(statistics.median(file_sizes)) if file_sizes else 0,
            "max_depth": max_depth,
        },
    }
    return knowledge_map


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
        explorer_reports: list[dict] | None = None,
        semantic_edges: list[dict] | None = None,
        file_path: str | None = None,
        cluster: str | None = None,
        neighbors_of: str | None = None,
        issues_only: bool = False,
    ) -> dict:
        """Save, load, query, or build a dual-layer knowledge map (file graph + concept clusters).

        Actions:
          - build: Deterministically compute a knowledge map from explorer reports.
                   Computes edges (reference + Viking semantic + co-location),
                   greedy concept clusters, orphan detection, and stats.
                   Saves the result automatically.
          - save: Persist a knowledge map to .neuraltree/knowledge_map.json
          - load: Load the knowledge map from disk
          - query: Query by file_path, cluster, neighbors_of, or issues_only

        Query filters are mutually exclusive. If multiple are supplied,
        priority: file_path > cluster > neighbors_of > issues_only.

        Args:
            action: One of 'build', 'save', 'load', 'query'.
            project_root: Project root directory.
            knowledge_map: The map dict to save (required for 'save' action).
            explorer_reports: List of explorer report dicts (required for 'build' action).
            semantic_edges: Pre-computed semantic edges from Viking/Model2Vec
                           (optional for 'build' action). Each: {"source", "target",
                           "weight", "reason"}.
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

        if action == "build":
            if explorer_reports is None:
                return {"error": "explorer_reports is required for build action"}
            if not isinstance(explorer_reports, list):
                return {"error": "explorer_reports must be a list of report dicts"}
            if semantic_edges is not None and not isinstance(semantic_edges, list):
                return {"error": "semantic_edges must be a list of edge dicts or None"}
            try:
                km = _build_map(explorer_reports, project_root, semantic_edges=semantic_edges)
                path = _save_map(km, project_root)
                return {
                    "saved": str(path),
                    "knowledge_map": km,
                    "stats": km["stats"],
                    "warnings": km.get("warnings", []),
                }
            except (OSError, ValueError) as e:
                return {"error": f"Failed to build map: {e}"}
            except (TypeError, KeyError, AttributeError) as e:
                return {"error": f"Failed to build map: {type(e).__name__}: {e}"}

        elif action == "save":
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
            return {"error": f"Unknown action: {action}. Use 'build', 'save', 'load', or 'query'."}
