"""neuraltree_score — Universal organization metrics from knowledge map."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastmcp import FastMCP

from neuraltree_mcp.validation import validate_project_root

# Flow Score weights — universal organization quality
WEIGHTS = {
    "reachability": 0.30,
    "connectivity": 0.25,
    "cluster_coherence": 0.20,
    "size_balance": 0.15,
    "discoverability": 0.10,
}

# Common entry-point filenames (case-insensitive matching)
ENTRY_POINT_NAMES = {
    "readme.md", "claude.md", "memory.md", "index.md",
    "overview.md", "getting-started.md", "introduction.md",
}


def _load_knowledge_map(root: Path) -> dict | None:
    """Load .neuraltree/knowledge_map.json if it exists.

    Returns None if the file doesn't exist, or {"error": "..."} if corrupt.
    """
    km_path = root / ".neuraltree" / "knowledge_map.json"
    if not km_path.exists():
        return None
    try:
        return json.loads(km_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"error": f"corrupt: {e}"}
    except OSError as e:
        return {"error": f"unreadable: {e}"}


def _detect_entry_points(files: dict) -> list[str]:
    """Auto-detect entry point files from the knowledge map."""
    entries = []
    for path in files:
        basename = os.path.basename(path).lower()
        if basename in ENTRY_POINT_NAMES:
            entries.append(path)
    return sorted(entries)


def _bfs_reachable(entry_points: list[str], edges: list[dict],
                   all_files: set[str], max_hops: int = 3) -> set[str]:
    """BFS from entry points using all edges (bidirectional). Returns reachable paths."""
    adj: dict[str, set[str]] = {}
    for edge in edges:
        src, tgt = edge.get("source", ""), edge.get("target", "")
        if src and tgt:
            adj.setdefault(src, set()).add(tgt)
            adj.setdefault(tgt, set()).add(src)

    visited: set[str] = set()
    frontier = {ep for ep in entry_points if ep in all_files}
    for _ in range(max_hops + 1):
        if not frontier:
            break
        visited |= frontier
        next_frontier: set[str] = set()
        for node in frontier:
            for neighbor in adj.get(node, set()):
                if neighbor not in visited and neighbor in all_files:
                    next_frontier.add(neighbor)
        frontier = next_frontier
    return visited


def _compute_connectivity(edges: list[dict], all_files: set[str]) -> tuple[float, list[str]]:
    """What % of files have at least 1 edge? Returns (ratio, orphan_list)."""
    connected: set[str] = set()
    for edge in edges:
        src, tgt = edge.get("source", ""), edge.get("target", "")
        if src in all_files:
            connected.add(src)
        if tgt in all_files:
            connected.add(tgt)

    orphans = sorted(all_files - connected)
    ratio = len(connected) / max(len(all_files), 1)
    return ratio, orphans


def _compute_cluster_coherence(clusters: list[dict]) -> float:
    """For multi-file clusters, what fraction of file pairs share a parent directory?"""
    multi = [c for c in clusters if len(c.get("files", [])) >= 2]
    if not multi:
        return 1.0  # all singletons = trivially coherent

    total_pairs = 0
    coherent_pairs = 0
    for cluster in multi:
        files = cluster["files"]
        for i in range(len(files)):
            for j in range(i + 1, len(files)):
                total_pairs += 1
                dir_a = os.path.dirname(files[i]) or "."
                dir_b = os.path.dirname(files[j]) or "."
                if dir_a == dir_b:
                    coherent_pairs += 1

    return coherent_pairs / max(total_pairs, 1)


def _compute_size_balance(files: dict, multiplier: float = 3.0) -> tuple[float, list[str]]:
    """What % of files are within multiplier × median size? Returns (ratio, oversized_list)."""
    sizes = [(path, f.get("size_lines", 0))
             for path, f in files.items()
             if f.get("size_lines", 0) > 0]
    if not sizes:
        return 1.0, []

    sorted_sizes = sorted(s for _, s in sizes)
    median = sorted_sizes[len(sorted_sizes) // 2]
    cap = max(median * multiplier, 50)  # min 50 lines to avoid penalizing tiny projects

    oversized = sorted(path for path, size in sizes if size > cap)
    balanced = (len(sizes) - len(oversized)) / len(sizes)
    return balanced, oversized


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def neuraltree_score(project_root: str = ".", trunk_paths: list[str] | None = None, adaptive: bool = False) -> dict:
        """Compute universal organization metrics from the knowledge map.

        Metrics (0.0 - 1.0 each):
        - reachability: % of files reachable in ≤3 hops from entry points via any edge.
        - connectivity: % of files with at least 1 edge (not orphaned).
        - cluster_coherence: % of related-file pairs that share a parent directory.
        - size_balance: % of files within 3× median size (no mega-files).
        - discoverability: precision@3 from Viking search (computed by Skill, null here).

        Requires a knowledge map (.neuraltree/knowledge_map.json).
        Run explore + map phases first if no map exists.

        Args:
            project_root: Project root directory.
            trunk_paths: Override entry-point detection with explicit paths.
            adaptive: Ignored (kept for API compatibility). Metrics are always
                      derived from the knowledge map.

        Returns:
            dict with metrics, flow_score_partial, details, and warnings.
        """
        try:
            root = validate_project_root(project_root)
        except ValueError as e:
            return {"error": str(e), "flow_score_partial": 0.0}

        km = _load_knowledge_map(root)
        if km is None:
            return {
                "metrics": {k: None for k in WEIGHTS},
                "flow_score_partial": None,
                "flow_score_weights": WEIGHTS,
                "details": {"reason": "No knowledge map yet — run map phase first"},
                "warnings": ["No knowledge map found. Score will be available after Phase 3 (Map)."],
                "no_map": True,
            }
        if "error" in km:
            return {"error": f"Knowledge map {km['error']}",
                    "flow_score_partial": 0.0}

        files = km.get("files", {})
        edges = km.get("edges", [])
        clusters = km.get("clusters", [])
        warnings: list[str] = []

        if not files:
            return {"error": "Knowledge map has no files", "flow_score_partial": 0.0}

        all_file_paths = set(files.keys())

        # --- Entry points ---
        if trunk_paths:
            entry_points = [tp for tp in trunk_paths if tp in all_file_paths]
        else:
            entry_points = _detect_entry_points(files)

        if not entry_points:
            warnings.append("No entry points detected — reachability will be 0")

        # --- Reachability ---
        reachable = _bfs_reachable(entry_points, edges, all_file_paths, max_hops=3)
        reachability = len(reachable) / max(len(all_file_paths), 1)
        unreachable = sorted(all_file_paths - reachable)

        # --- Connectivity ---
        connectivity, orphans = _compute_connectivity(edges, all_file_paths)

        # --- Cluster Coherence ---
        cluster_coherence = _compute_cluster_coherence(clusters)

        # --- Size Balance ---
        size_balance, oversized = _compute_size_balance(files)

        # --- Discoverability (filled by Skill via Viking) ---
        discoverability = None

        # --- Flow Score ---
        metrics = {
            "reachability": round(reachability, 3),
            "connectivity": round(connectivity, 3),
            "cluster_coherence": round(cluster_coherence, 3),
            "size_balance": round(size_balance, 3),
            "discoverability": discoverability,
        }

        partial_flow = sum(
            metrics[k] * WEIGHTS[k]
            for k in WEIGHTS
            if metrics[k] is not None
        )

        return {
            "metrics": metrics,
            "flow_score_partial": round(partial_flow, 3),
            "flow_score_weights": WEIGHTS,
            "details": {
                "total_files": len(all_file_paths),
                "entry_points": entry_points,
                "reachable_in_3_hops": len(reachable),
                "unreachable_files": unreachable,
                "orphan_files": orphans,
                "oversized_files": oversized,
                "cluster_count": len(clusters),
                "multi_file_clusters": len([c for c in clusters if len(c.get("files", [])) >= 2]),
            },
            "warnings": warnings,
        }
