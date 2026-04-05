"""neuraltree_score — Compute structural metrics and Flow Score."""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import FastMCP

from neuraltree_mcp.text_utils import SKIP_DIRS, is_referenced, walk_project_files
from neuraltree_mcp.validation import validate_project_root
FRESHNESS_WINDOW_DAYS = 30

# Flow Score weights (retrieval 50%, structure 35%, maintenance 15%)
WEIGHTS = {
    "hop_efficiency": 0.25,
    "precision_at_3": 0.25,
    "synapse_coverage": 0.20,
    "dead_neuron_ratio": 0.15,
    "freshness": 0.10,
    "trunk_pressure": 0.05,
}


def _find_md_files(root: Path) -> list[Path]:
    """Find all .md files in the project."""
    return walk_project_files(root, {".md"})


def _has_section(content: str, heading: str) -> bool:
    """Check if content has a ## heading section."""
    return bool(re.search(rf'^##\s+{re.escape(heading)}\b', content, re.MULTILINE))


def _extract_related_targets(content: str) -> list[str]:
    """Extract file targets from ## Related section."""
    targets = []
    in_related = False
    for line in content.splitlines():
        if re.match(r'^##\s+Related\b', line):
            in_related = True
            continue
        if in_related:
            if line.startswith("## "):
                break
            for m in re.finditer(r'\[.*?\]\(([^)]+)\)', line):
                targets.append(m.group(1))
    return targets


def _parse_last_verified(content: str) -> str | None:
    """Extract last_verified date from frontmatter."""
    m = re.search(r'last_verified:\s*(\d{4}-\d{2}-\d{2})', content)
    return m.group(1) if m else None


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def neuraltree_score(project_root: str = ".", trunk_paths: list[str] | None = None) -> dict:
        """Compute 4 structural metrics + trunk pressure for the neural tree.

        Metrics computed (0.0 - 1.0 each):
        - hop_efficiency: How efficiently trunk->index->leaf navigation works.
        - synapse_coverage: % of .md files with ## Related pointing to alive targets.
        - dead_neuron_ratio: 1 - (orphans / total). Higher = fewer dead files.
        - freshness: % of files with last_verified within 30 days.
        - trunk_pressure: Trunk line count vs 100-line cap.

        Note: precision_at_3 requires Viking (computed by the Skill, not here).
        It's included in the output as null for the Skill to fill in.

        Args:
            project_root: Project root directory.
            trunk_paths: Paths to trunk files (MEMORY.md, CLAUDE.md). Auto-detected if None.

        Returns:
            dict with individual metrics, flow_score (partial, without precision_at_3),
            and details for each metric.
        """
        try:
            root = validate_project_root(project_root)
        except ValueError as e:
            return {"error": str(e), "flow_score": 0.0}
        md_files = _find_md_files(root)

        if not md_files:
            return {"error": "No .md files found", "flow_score": 0.0}

        # --- Single-pass file content cache ---
        # Read all .md files once; reuse across all metric computations
        file_contents: dict[Path, str] = {}
        warnings: list[str] = []
        for md_file in md_files:
            try:
                file_contents[md_file] = md_file.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                warnings.append(f"Could not read {os.path.relpath(md_file, root)}: {e}")

        # --- Hop Efficiency ---
        # Check: trunk exists, trunk links to indexes, indexes link to leaves
        trunks = trunk_paths or []
        if not trunks:
            for candidate in ["memory/MEMORY.md", "MEMORY.md", "CLAUDE.md"]:
                if (root / candidate).exists():
                    trunks.append(candidate)

        # Count how many .md files are reachable in 0-2 hops from trunks
        # Only count RESOLVED, EXISTING .md files (not raw link strings)
        hop_0_files: set[str] = set()  # resolved paths relative to root
        hop_1_files: set[str] = set()
        hop_2_files: set[str] = set()

        for tp in trunks:
            trunk_file = root / tp
            if not trunk_file.exists():
                continue
            hop_0_files.add(str(trunk_file.resolve()))
            try:
                content = trunk_file.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                warnings.append(f"Could not read trunk {tp}: {e}")
                continue
            for m in re.finditer(r'\[.*?\]\(([^)]+)\)', content):
                linked = m.group(1)
                # Skip external links and anchors
                if linked.startswith("http") or linked.startswith("#"):
                    continue
                linked_path = (trunk_file.parent / linked).resolve()
                if linked_path.exists() and linked_path.suffix == ".md":
                    hop_1_files.add(str(linked_path))
                    # Follow one more hop
                    try:
                        linked_content = linked_path.read_text(encoding="utf-8", errors="replace")
                        for m2 in re.finditer(r'\[.*?\]\(([^)]+)\)', linked_content):
                            linked2 = m2.group(1)
                            if linked2.startswith("http") or linked2.startswith("#"):
                                continue
                            linked2_path = (linked_path.parent / linked2).resolve()
                            if linked2_path.exists() and linked2_path.suffix == ".md":
                                hop_2_files.add(str(linked2_path))
                    except OSError as e:
                        warnings.append(f"Could not read {linked_path}: {e}")

        total_md = len(md_files)
        all_reachable = hop_0_files | hop_1_files | hop_2_files
        reachable = len(all_reachable)
        hop_efficiency = min(1.0, reachable / max(total_md, 1))

        # --- Synapse Coverage ---
        wired_count = 0
        total_leaves = 0
        synapse_details = []

        for md_file in md_files:
            content = file_contents.get(md_file)
            if content is None:
                continue

            if _has_section(content, "Related"):
                targets = _extract_related_targets(content)
                alive_targets = []
                for t in targets:
                    target_path = md_file.parent / t
                    if target_path.exists():
                        alive_targets.append(t)

                if alive_targets:
                    wired_count += 1
                else:
                    synapse_details.append(f"{os.path.relpath(md_file, root)}: ## Related has dead targets")
            total_leaves += 1

        synapse_coverage = wired_count / max(total_leaves, 1)

        # --- Dead Neuron Ratio ---
        # For each .md file, check if ANY other file references it
        orphans = []
        all_contents: dict[str, str] = {
            os.path.relpath(md_file, root): content
            for md_file, content in file_contents.items()
        }

        for rel_path in all_contents:
            basename = Path(rel_path).name
            found = False
            for other_path, other_content in all_contents.items():
                if other_path == rel_path:
                    continue
                if is_referenced(basename, rel_path, other_content):
                    found = True
                    break
            if not found:
                orphans.append(rel_path)

        dead_neuron_ratio = 1.0 - (len(orphans) / max(len(all_contents), 1))

        # --- Freshness ---
        now = datetime.now(tz=timezone.utc)
        fresh_count = 0
        stale_files = []

        for md_file in md_files:
            content = file_contents.get(md_file)
            if content is None:
                continue
            date_str = _parse_last_verified(content)
            if date_str:
                try:
                    verified = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    if (now - verified).days <= FRESHNESS_WINDOW_DAYS:
                        fresh_count += 1
                    else:
                        stale_files.append(os.path.relpath(md_file, root))
                except ValueError:
                    stale_files.append(os.path.relpath(md_file, root))
            # Files without last_verified are not counted as fresh

        freshness = fresh_count / max(total_md, 1)

        # --- Trunk Pressure ---
        trunk_lines = 0
        for tp in trunks:
            trunk_file = root / tp
            if trunk_file.exists():
                try:
                    trunk_lines += len(trunk_file.read_text(encoding="utf-8", errors="replace").splitlines())
                except OSError as e:
                    warnings.append(f"Could not read trunk {tp}: {e}")

        if trunk_lines < 80:
            trunk_pressure = 1.0
        elif trunk_lines < 100:
            trunk_pressure = 0.8
        else:
            trunk_pressure = 0.3

        # --- Flow Score (partial — without precision_at_3) ---
        metrics = {
            "hop_efficiency": round(hop_efficiency, 3),
            "precision_at_3": None,  # Filled by Skill via Viking
            "synapse_coverage": round(synapse_coverage, 3),
            "dead_neuron_ratio": round(dead_neuron_ratio, 3),
            "freshness": round(freshness, 3),
            "trunk_pressure": round(trunk_pressure, 3),
        }

        # Partial flow score (precision_at_3 treated as 0 until Skill fills it)
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
                "total_md_files": total_md,
                "reachable_in_2_hops": reachable,
                "wired_files": wired_count,
                "orphan_files": orphans,
                "stale_files": stale_files,
                "trunk_lines": trunk_lines,
            },
            "warnings": warnings,
        }
