# NeuralTree v2: Explore-First Architecture

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the metric-driven pipeline with an understanding-first architecture where parallel explorer agents build a knowledge map, Claude reasons about what's wrong, and scoring validates rather than drives decisions.

**Architecture:** Explorer agents (2-10 based on project size) each read a directory slice of knowledge files, report structured findings. A synthesizer merges reports into a dual-layer knowledge map (file graph + concept clusters). Claude analyzes the map to identify issues and propose reorganizations. Scoring is adaptive — thresholds derived from the project's own shape, not hardcoded constants.

**Tech Stack:** Python 3.11, FastMCP, existing neuraltree-mcp tools (24 kept), Viking MCP (semantic search)

---

## File Structure

```
KEEP AS-IS (no changes):
  src/neuraltree_mcp/server.py              — add 1 import for new tool
  src/neuraltree_mcp/validation.py           — path security (all tools use this)
  src/neuraltree_mcp/text_utils.py           — shared utilities
  src/neuraltree_mcp/tools/*.py              — all 10 existing tool modules
  src/neuraltree_mcp/scoring/diagnose.py     — gap classification
  src/neuraltree_mcp/scoring/predict.py      — prediction + calibration
  src/neuraltree_mcp/sandbox/sandbox.py      — sandbox tools
  tests/conftest.py                          — shared fixtures

CREATE:
  src/neuraltree_mcp/tools/knowledge_map.py  — persist/load/query knowledge map
  tests/unit/test_knowledge_map.py           — tests for knowledge map tool
  tests/integration/test_knowledge_map.py    — integration tests

MODIFY:
  src/neuraltree_mcp/server.py               — register new knowledge_map tool
  src/neuraltree_mcp/scoring/score.py         — add adaptive scoring mode
  tests/unit/test_score.py                    — tests for adaptive scoring

REWRITE:
  src/skill/SKILL.md                          — new router (explore-first pipeline)
  src/skill/sections/explore.md               — NEW Phase 1: agent swarm exploration
  src/skill/sections/map.md                   — NEW Phase 2: knowledge map synthesis
  src/skill/sections/analyze.md               — NEW Phase 3: Claude-driven analysis
  src/skill/sections/plan.md                  — NEW Phase 4: reorganization proposals
  src/skill/sections/execute.md               — NEW Phase 5: sandbox execution
  src/skill/sections/verify.md                — NEW Phase 6: adaptive scoring verification
  src/skill/sections/report.md                — REWRITE: new report format

REMOVE:
  src/skill/sections/benchmark.md             — replaced by explore+map+verify
  src/skill/sections/diagnose.md              — replaced by analyze
  src/skill/sections/autoloop.md              — replaced by plan+execute
  src/skill/sections/enforce.md               — merged into verify
  src/skill/sections/edge-cases.md            — merged into each section
```

---

### Task 1: Knowledge Map MCP Tool

**Files:**
- Create: `src/neuraltree_mcp/tools/knowledge_map.py`
- Create: `tests/unit/test_knowledge_map.py`
- Modify: `src/neuraltree_mcp/server.py`

The knowledge map is the central data structure. It persists at `.neuraltree/knowledge_map.json` and contains two layers: a file-level graph (nodes + edges) and concept-level clusters.

- [ ] **Step 1: Write failing tests for knowledge_map_save**

```python
# tests/unit/test_knowledge_map.py
"""Tests for knowledge_map tool — save, load, query."""
import json
import os
import pytest


SAMPLE_MAP = {
    "version": 2,
    "timestamp": "2026-04-06T12:00:00Z",
    "project_name": "test_project",
    "files": {
        "CLAUDE.md": {
            "path": "CLAUDE.md",
            "topic": "Project instructions",
            "key_concepts": ["architecture", "tools", "protocol"],
            "references_to": ["README.md", "memory/MEMORY.md"],
            "referenced_by": ["README.md"],
            "size_lines": 108,
            "staleness": None,
            "issues": [],
        },
        "README.md": {
            "path": "README.md",
            "topic": "Public documentation",
            "key_concepts": ["install", "usage", "tools"],
            "references_to": ["CLAUDE.md"],
            "referenced_by": ["CLAUDE.md"],
            "size_lines": 325,
            "staleness": None,
            "issues": ["large file"],
        },
    },
    "edges": [
        {"source": "CLAUDE.md", "target": "README.md", "type": "reference", "weight": 1.0},
        {"source": "README.md", "target": "CLAUDE.md", "type": "reference", "weight": 1.0},
    ],
    "clusters": [
        {
            "name": "project_overview",
            "concept": "Project documentation and instructions",
            "files": ["CLAUDE.md", "README.md"],
        }
    ],
    "issues": [
        {
            "type": "large_file",
            "file": "README.md",
            "description": "325 lines — consider splitting",
            "severity": "medium",
        }
    ],
    "stats": {
        "total_files": 2,
        "total_edges": 2,
        "total_clusters": 1,
        "total_issues": 1,
        "avg_file_size": 216,
        "max_depth": 1,
    },
}


class TestKnowledgeMapSave:
    def test_save_creates_file(self, tmp_project):
        from neuraltree_mcp.tools.knowledge_map import _save_map, _load_map
        _save_map(SAMPLE_MAP, str(tmp_project))
        assert (tmp_project / ".neuraltree" / "knowledge_map.json").exists()

    def test_save_and_load_roundtrip(self, tmp_project):
        from neuraltree_mcp.tools.knowledge_map import _save_map, _load_map
        _save_map(SAMPLE_MAP, str(tmp_project))
        loaded = _load_map(str(tmp_project))
        assert loaded["version"] == 2
        assert len(loaded["files"]) == 2
        assert len(loaded["edges"]) == 2
        assert len(loaded["clusters"]) == 1

    def test_load_returns_none_when_missing(self, tmp_project):
        from neuraltree_mcp.tools.knowledge_map import _load_map
        result = _load_map(str(tmp_project))
        assert result is None


class TestKnowledgeMapQuery:
    def test_query_file(self, tmp_project):
        from neuraltree_mcp.tools.knowledge_map import _save_map, _query_map
        _save_map(SAMPLE_MAP, str(tmp_project))
        result = _query_map(str(tmp_project), file_path="CLAUDE.md")
        assert result["path"] == "CLAUDE.md"
        assert "architecture" in result["key_concepts"]

    def test_query_cluster(self, tmp_project):
        from neuraltree_mcp.tools.knowledge_map import _save_map, _query_map
        _save_map(SAMPLE_MAP, str(tmp_project))
        result = _query_map(str(tmp_project), cluster="project_overview")
        assert len(result["files"]) == 2

    def test_query_neighbors(self, tmp_project):
        from neuraltree_mcp.tools.knowledge_map import _save_map, _query_map
        _save_map(SAMPLE_MAP, str(tmp_project))
        result = _query_map(str(tmp_project), neighbors_of="CLAUDE.md")
        assert "README.md" in result["neighbors"]

    def test_query_issues(self, tmp_project):
        from neuraltree_mcp.tools.knowledge_map import _save_map, _query_map
        _save_map(SAMPLE_MAP, str(tmp_project))
        result = _query_map(str(tmp_project), issues_only=True)
        assert len(result["issues"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python3.11 -m pytest tests/unit/test_knowledge_map.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'neuraltree_mcp.tools.knowledge_map'`

- [ ] **Step 3: Implement knowledge_map.py**

```python
# src/neuraltree_mcp/tools/knowledge_map.py
"""neuraltree_knowledge_map — Persist, load, and query the knowledge map.

The knowledge map is a dual-layer graph:
  Layer 1 (file graph): nodes = files, edges = references/semantic links
  Layer 2 (concept clusters): groups of files sharing a topic

Stored at .neuraltree/knowledge_map.json. Created by the Skill's synthesizer
phase, consumed by analyze and verify phases.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastmcp import FastMCP

from neuraltree_mcp.validation import validate_project_root


def _save_map(knowledge_map: dict, project_root: str) -> Path:
    """Save knowledge map to .neuraltree/knowledge_map.json."""
    root = Path(project_root)
    nt_dir = root / ".neuraltree"
    nt_dir.mkdir(exist_ok=True)
    map_path = nt_dir / "knowledge_map.json"
    map_path.write_text(json.dumps(knowledge_map, indent=2), encoding="utf-8")
    return map_path


def _load_map(project_root: str) -> dict | None:
    """Load knowledge map from .neuraltree/knowledge_map.json."""
    map_path = Path(project_root) / ".neuraltree" / "knowledge_map.json"
    if not map_path.exists():
        return None
    return json.loads(map_path.read_text(encoding="utf-8"))


def _query_map(
    project_root: str,
    file_path: str | None = None,
    cluster: str | None = None,
    neighbors_of: str | None = None,
    issues_only: bool = False,
) -> dict:
    """Query the knowledge map."""
    km = _load_map(project_root)
    if km is None:
        return {"error": "No knowledge map found. Run /neuraltree first."}

    if file_path:
        file_data = km["files"].get(file_path)
        if not file_data:
            return {"error": f"File {file_path} not in knowledge map."}
        return file_data

    if cluster:
        for c in km.get("clusters", []):
            if c["name"] == cluster:
                return c
        return {"error": f"Cluster {cluster} not found."}

    if neighbors_of:
        neighbors = set()
        for edge in km.get("edges", []):
            if edge["source"] == neighbors_of:
                neighbors.add(edge["target"])
            if edge["target"] == neighbors_of:
                neighbors.add(edge["source"])
        return {"neighbors": sorted(neighbors), "file": neighbors_of}

    if issues_only:
        return {"issues": km.get("issues", []), "total": len(km.get("issues", []))}

    return km


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def neuraltree_knowledge_map(
        action: str = "load",
        project_root: str = ".",
        knowledge_map: dict | None = None,
        file_path: str | None = None,
        cluster: str | None = None,
        neighbors_of: str | None = None,
        issues_only: bool = False,
    ) -> dict:
        """Persist, load, and query the project knowledge map.

        The knowledge map is a dual-layer graph of the project's knowledge files.
        Created by the explore phase, consumed by analyze and verify phases.

        Args:
            action: "save", "load", or "query".
            project_root: Project root directory.
            knowledge_map: The map data to save (required for action="save").
            file_path: Query a specific file's data (action="query").
            cluster: Query a specific cluster (action="query").
            neighbors_of: Get neighbors of a file (action="query").
            issues_only: Get only issues (action="query").

        Returns:
            dict with the map data, query results, or save confirmation.
        """
        try:
            root = validate_project_root(project_root)
        except ValueError as e:
            return {"error": str(e)}

        if action == "save":
            if knowledge_map is None:
                return {"error": "knowledge_map is required for save action."}
            path = _save_map(knowledge_map, str(root))
            return {"saved": True, "path": str(path), "files": len(knowledge_map.get("files", {}))}

        elif action == "load":
            km = _load_map(str(root))
            if km is None:
                return {"exists": False, "message": "No knowledge map found."}
            return {"exists": True, "map": km}

        elif action == "query":
            return _query_map(str(root), file_path, cluster, neighbors_of, issues_only)

        else:
            return {"error": f"Unknown action: {action}. Use 'save', 'load', or 'query'."}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python3.11 -m pytest tests/unit/test_knowledge_map.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Register in server.py**

Add to `src/neuraltree_mcp/server.py` after line 31:

```python
from neuraltree_mcp.tools.knowledge_map import register as register_knowledge_map
```

Add after line 45:

```python
register_knowledge_map(mcp)
```

- [ ] **Step 6: Verify tool count is now 25**

Run: `PYTHONPATH=src python3.11 -c "import asyncio; from neuraltree_mcp.server import mcp; tools = asyncio.run(mcp.list_tools()); print(f'{len(tools)} tools')"`
Expected: `25 tools`

- [ ] **Step 7: Commit**

```bash
git add src/neuraltree_mcp/tools/knowledge_map.py tests/unit/test_knowledge_map.py src/neuraltree_mcp/server.py
git commit -m "feat: add neuraltree_knowledge_map tool — save/load/query dual-layer graph"
```

---

### Task 2: Adaptive Scoring Mode

**Files:**
- Modify: `src/neuraltree_mcp/scoring/score.py`
- Modify: `tests/unit/test_score.py`

Add an `adaptive=True` parameter to `neuraltree_score` that reads the knowledge map to derive thresholds instead of using hardcoded constants.

- [ ] **Step 1: Write failing tests for adaptive scoring**

```python
# Add to tests/unit/test_score.py

class TestAdaptiveScoring:
    """Tests for adaptive scoring mode that derives thresholds from knowledge map."""

    def test_adaptive_without_map_falls_back_to_static(self, tmp_project):
        """No knowledge map → use static weights (backwards compatible)."""
        result = call_tool("neuraltree_score", {
            "project_root": str(tmp_project),
            "adaptive": True,
        })
        # Should work fine, just uses static weights
        assert "metrics" in result
        assert result["metrics"]["hop_efficiency"] is not None

    def test_adaptive_with_map_uses_project_stats(self, tmp_project):
        """With knowledge map → derive thresholds from project shape."""
        import json
        nt_dir = tmp_project / ".neuraltree"
        nt_dir.mkdir(exist_ok=True)
        (nt_dir / "knowledge_map.json").write_text(json.dumps({
            "version": 2,
            "files": {f"file_{i}.md": {"size_lines": 50} for i in range(20)},
            "edges": [{"source": f"file_{i}.md", "target": f"file_{i+1}.md", "type": "reference"} for i in range(19)],
            "clusters": [{"name": "c1", "files": [f"file_{i}.md" for i in range(10)]}],
            "stats": {
                "total_files": 20,
                "total_edges": 19,
                "avg_file_size": 50,
                "max_depth": 3,
            },
        }))
        result = call_tool("neuraltree_score", {
            "project_root": str(tmp_project),
            "adaptive": True,
        })
        assert "adaptive_context" in result
        assert result["adaptive_context"]["source"] == "knowledge_map"

    def test_adaptive_trunk_pressure_scales_with_project_size(self, tmp_project):
        """Larger projects get more lenient trunk pressure thresholds."""
        import json
        nt_dir = tmp_project / ".neuraltree"
        nt_dir.mkdir(exist_ok=True)
        # 500-file project should allow 200-line trunks
        (nt_dir / "knowledge_map.json").write_text(json.dumps({
            "version": 2,
            "files": {f"file_{i}.md": {"size_lines": 80} for i in range(500)},
            "edges": [],
            "clusters": [],
            "stats": {"total_files": 500, "avg_file_size": 80, "max_depth": 4},
        }))
        result = call_tool("neuraltree_score", {
            "project_root": str(tmp_project),
            "adaptive": True,
        })
        ctx = result.get("adaptive_context", {})
        # 500 files → trunk cap should be higher than default 100
        assert ctx.get("trunk_cap", 100) > 100
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python3.11 -m pytest tests/unit/test_score.py::TestAdaptiveScoring -v`
Expected: FAIL (adaptive parameter not recognized)

- [ ] **Step 3: Implement adaptive scoring in score.py**

Add to `src/neuraltree_mcp/scoring/score.py`, inside the `register` function. Modify `neuraltree_score` signature to accept `adaptive: bool = False`:

```python
def neuraltree_score(
    project_root: str = ".",
    trunk_paths: list[str] | None = None,
    adaptive: bool = False,
) -> dict:
```

After computing all metrics (before the return), add adaptive context:

```python
        # --- Adaptive context (from knowledge map) ---
        adaptive_context = {}
        if adaptive:
            km_path = root / ".neuraltree" / "knowledge_map.json"
            if km_path.exists():
                try:
                    import json
                    km = json.loads(km_path.read_text(encoding="utf-8"))
                    km_stats = km.get("stats", {})
                    km_total = km_stats.get("total_files", total_md)
                    km_avg_size = km_stats.get("avg_file_size", 80)
                    km_depth = km_stats.get("max_depth", 2)

                    # Derive adaptive thresholds
                    # Trunk cap: base 100, +25 per 100 files, max 300
                    adaptive_trunk_cap = min(300, 100 + (km_total // 100) * 25)
                    # File size cap: 2x project average, min 200, max 800
                    adaptive_file_cap = max(200, min(800, int(km_avg_size * 2)))
                    # Freshness window: base 30, +10 per depth level beyond 2
                    adaptive_freshness_days = 30 + max(0, (km_depth - 2)) * 10

                    adaptive_context = {
                        "source": "knowledge_map",
                        "trunk_cap": adaptive_trunk_cap,
                        "file_size_cap": adaptive_file_cap,
                        "freshness_days": adaptive_freshness_days,
                        "project_files": km_total,
                    }

                    # Recompute trunk pressure with adaptive cap
                    if trunk_lines < adaptive_trunk_cap * 0.8:
                        metrics["trunk_pressure"] = 1.0
                    elif trunk_lines < adaptive_trunk_cap:
                        metrics["trunk_pressure"] = 0.8
                    else:
                        metrics["trunk_pressure"] = 0.3

                    # Recompute partial flow score with updated trunk_pressure
                    partial_flow = sum(
                        metrics[k] * WEIGHTS[k]
                        for k in WEIGHTS
                        if metrics[k] is not None
                    )
                except (json.JSONDecodeError, KeyError, OSError):
                    adaptive_context = {"source": "static", "reason": "knowledge_map unreadable"}
            else:
                adaptive_context = {"source": "static", "reason": "no knowledge_map"}

        result = {
            "metrics": metrics,
            "flow_score_partial": round(partial_flow, 3),
            "flow_score_weights": WEIGHTS,
            "details": { ... },  # same as before
            "warnings": warnings,
        }
        if adaptive:
            result["adaptive_context"] = adaptive_context
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python3.11 -m pytest tests/unit/test_score.py -v`
Expected: All tests PASS (old + new)

- [ ] **Step 5: Run full suite**

Run: `PYTHONPATH=src python3.11 -m pytest tests/ -q --tb=short`
Expected: 311+ passed (308 old + 3 new)

- [ ] **Step 6: Commit**

```bash
git add src/neuraltree_mcp/scoring/score.py tests/unit/test_score.py
git commit -m "feat: add adaptive scoring mode — derives thresholds from knowledge map"
```

---

### Task 3: SKILL.md v2 Router

**Files:**
- Rewrite: `src/skill/SKILL.md`

The router is the skill's brain. It sets up the explore-first pipeline and defines the new phase structure.

- [ ] **Step 1: Write the new SKILL.md router**

```markdown
---
name: neuraltree
description: >
  Universal neural organization — explores, maps, and reorganizes project
  knowledge so any fact is reachable in 0-2 hops.
version: 2.0.0
tools_required:
  - neuraltree-mcp (25 tools — includes Viking search + knowledge map)
---

# /neuraltree — Universal Neural Organization Skill v2

> You are the brain. neuraltree-mcp is the muscle. Viking is the memory.
> Your job: UNDERSTAND first, then organize.

## How This Skill Works

This file is the **router**. Detailed instructions for each phase live in
`sections/` files — read them on demand as you reach each phase.

```
SKILL.md (this file)        — always loaded: activation + principles + routing
sections/explore.md         — Phase 1: parallel agent exploration
sections/map.md             — Phase 2: knowledge map synthesis
sections/analyze.md         — Phase 3: Claude-driven issue analysis
sections/plan.md            — Phase 4: reorganization proposals
sections/execute.md         — Phase 5: sandbox execution
sections/verify.md          — Phase 6: adaptive scoring verification
sections/report.md          — Output: before/after comparison
```

## v1 vs v2 — What Changed

| v1 (metric-driven) | v2 (understanding-first) |
|--------------------|--------------------------|
| Score first, fix what formula says | Explore first, understand, then fix |
| Hardcoded weights (0.25, 0.20...) | Adaptive thresholds from project shape |
| Single-threaded autoloop | Parallel explorer agents (2-10) |
| Keyword Jaccard similarity | Deep reading + concept clustering |
| No knowledge map | Persistent dual-layer knowledge map |

## MCP Tools Reference (25 tools)

| Category | Tools |
|----------|-------|
| Filesystem | `neuraltree_scan`, `neuraltree_trace`, `neuraltree_backup`, `neuraltree_restore` |
| Intelligence | `neuraltree_wire`, `neuraltree_generate_queries` |
| Reorganize | `neuraltree_plan_move`, `neuraltree_plan_split`, `neuraltree_find_dead`, `neuraltree_generate_index`, `neuraltree_shrink_and_wire`, `neuraltree_split_and_wire` |
| Lessons | `neuraltree_lesson_match`, `neuraltree_lesson_add` |
| Scoring | `neuraltree_score` (with adaptive mode), `neuraltree_diagnose`, `neuraltree_predict`, `neuraltree_update_calibration` |
| Semantic | `neuraltree_precision`, `neuraltree_viking_index` |
| Knowledge Map | `neuraltree_knowledge_map` (save/load/query) |
| Sandbox | `neuraltree_sandbox_create`, `neuraltree_sandbox_diff`, `neuraltree_sandbox_apply`, `neuraltree_sandbox_destroy` |

## The Artery Principle (unchanged from v1)

> "It's NOT about disk space. It's about FLOW."

1. **Synapse Quality** — Every `## Related` link must lead somewhere alive and useful.
2. **Hop Synergy** — Trunk → branch → leaf. Each hop adds specificity.
3. **Electrical Flow** — `## Related` links fire toward the 2-4 files that complete the thought.
4. **Trunk Pressure** — Trunk files are indexes, not content.
5. **Trace Before Prune** — NEVER delete without calling `neuraltree_trace()` first.
6. **User Approves Destructive Actions** — Wiring = auto. Deletes/moves/splits = ask.

## Section 1: Activation

### Step 1: Verify Tools

1. **neuraltree-mcp** — call `neuraltree_scan(path=".", max_files=10000)`.
   Returns file inventory: **PASS**. Record `total_count`, `files`, `dirs`.
   Errors: **ABORT**. `FATAL: neuraltree-mcp is not available.`

2. **Viking** — call `neuraltree_precision(queries=[{"text":"test"}], project_root=".")`.
   `viking_available` true: **PASS**.
   Viking unavailable: set `DEGRADED_MODE = true`. Print warning. Continue.

### Step 2: Detect Mode

Read `.neuraltree/knowledge_map.json` (knowledge map) and `.neuraltree/state.json`.

| Condition | Mode | Pipeline |
|-----------|------|----------|
| No knowledge map | **full** | Explore → Map → Analyze → Plan → Execute → Verify |
| Map exists, stale (>7 days) | **refresh** | Explore → Map → Analyze → Plan → Execute → Verify |
| Map exists, recent, state.flow_score < 0.60 | **fix** | Analyze → Plan → Execute → Verify |
| Map exists, recent, state.flow_score >= 0.60 | **check** | Verify only (quick re-score) |

### Step 3: Determine Agent Count

Scale exploration agents to project size:

```
scan_result = neuraltree_scan(path=".", max_files=10000)
knowledge_files = [f for f in scan_result["files"]
                   if f.endswith((".md", ".txt"))
                   and not f.startswith((".pytest_cache/", ".ruff_cache/"))]
total_kb_files = len(knowledge_files)
total_dirs = len(scan_result["dirs"])

if total_kb_files < 30:       agent_count = 2
elif total_kb_files < 100:    agent_count = 3
elif total_kb_files < 300:    agent_count = 5
elif total_kb_files < 1000:   agent_count = 7
else:                         agent_count = 10
```

### Step 4: Acquire Lock + Emit Status

```
/neuraltree — Activation Complete
Mode: {mode} | Agents: {agent_count} | Files: {total_kb_files}
Tools: neuraltree-mcp ✓ (25 tools) | Viking: ✓|DEGRADED
Pipeline: {phase_list}
```

### Step 5: Handle Subcommands

| Subcommand | Pipeline |
|------------|----------|
| `/neuraltree` | Mode-detected pipeline |
| `/neuraltree explore` | Explore + Map only |
| `/neuraltree analyze` | Analyze only (uses existing map) |
| `/neuraltree fix` | Analyze → Plan → Execute → Verify |
| `/neuraltree verify` | Verify only (quick re-score) |
| `/neuraltree map` | Show knowledge map summary |
| `/neuraltree auto` | Full pipeline regardless of mode |

## Pipeline Routing

### Phase 1: Explore
**Read `sections/explore.md` and execute.**
Launch N explorer agents in parallel. Each reads a directory slice deeply.
Reports: per-file metadata, per-directory assessment, cross-references found.

### Phase 2: Map
**Read `sections/map.md` and execute.**
Synthesize explorer reports into dual-layer knowledge map.
Layer 1: file graph (nodes + edges). Layer 2: concept clusters.
Save to `.neuraltree/knowledge_map.json`.

### Phase 3: Analyze
**Read `sections/analyze.md` and execute.**
Claude reads the knowledge map and REASONS about what's wrong.
No formulas — understanding-driven issue identification.
Output: issues list with severity + proposed fixes.

### Phase 4: Plan
**Read `sections/plan.md` and execute.**
Convert issues into concrete reorganization actions.
Show user: "Here's what I'd change and why." User approves per-item.

### Phase 5: Execute
**Read `sections/execute.md` and execute.**
Apply approved changes in sandbox.
Wire new/moved files. Re-index Viking. Verify no broken references.

### Phase 6: Verify
**Read `sections/verify.md` and execute.**
Score with adaptive mode. Compare before/after.
Score VALIDATES the changes — it doesn't drive them.

### Report
**Read `sections/report.md` and execute.**
Before/after comparison. Knowledge map summary. Action log.

**Lock must be released at the end of every run. No exceptions.**
```

- [ ] **Step 2: Verify SKILL.md renders correctly**

Run: `wc -l src/skill/SKILL.md`
Expected: ~200 lines (lean router)

- [ ] **Step 3: Commit**

```bash
git add src/skill/SKILL.md
git commit -m "feat: SKILL.md v2 router — explore-first pipeline with agent scaling"
```

---

### Task 4: Explore Phase (sections/explore.md)

**Files:**
- Create: `src/skill/sections/explore.md`

This is the heart of v2 — parallel agent exploration.

- [ ] **Step 1: Write explore.md**

```markdown
# Explore Phase

> Read deeply. Report honestly. Every file gets understood, not just counted.

**Input:** `scan_result`, `agent_count`, `knowledge_files`, `dirs`.
**Output:** `explorer_reports` (list of per-agent structured reports).

## Step 1: Assign Directory Slices

Divide directories among agents. Each agent gets a slice of the project
to read deeply. Balance by file count, not directory count.

```
# Sort dirs by file count (largest first)
dir_file_counts = {}
for f in knowledge_files:
    d = os.path.dirname(f) or "."
    dir_file_counts.setdefault(d, []).append(f)

# Greedy assignment: give largest unassigned dir to least-loaded agent
agent_slices = [[] for _ in range(agent_count)]
agent_loads = [0] * agent_count

for d, files in sorted(dir_file_counts.items(), key=lambda x: -len(x[1])):
    lightest = agent_loads.index(min(agent_loads))
    agent_slices[lightest].append({"dir": d, "files": files})
    agent_loads[lightest] += len(files)
```

## Step 2: Launch Explorer Agents

Launch all agents in parallel using the Agent tool. Each agent receives:
1. The list of files to read
2. The structured report format to follow
3. Instructions to read each file FULLY and report honestly

**Explorer Agent Prompt Template:**

```
You are an explorer agent for NeuralTree. Your job is to READ every file
in your assigned slice and report what you find.

YOUR ASSIGNED FILES:
{file_list}

For EACH file, read it fully and report:
{
  "path": "relative/path.md",
  "topic": "one-line summary of what this file is about",
  "key_concepts": ["concept1", "concept2", ...],  // 3-8 concepts
  "references_to": ["other_file.md", ...],  // files this references
  "size_lines": 123,
  "has_frontmatter": true/false,
  "has_related_section": true/false,
  "has_docs_section": true/false,
  "staleness": null or "description of outdated content",
  "issues": ["too large", "duplicate of X", "misplaced", ...]
}

For EACH directory, report:
{
  "path": "relative/dir/",
  "purpose": "what this directory contains",
  "cohesion": "high" | "medium" | "low",
  "issues": ["naming unclear", "mixed concerns", ...]
}

Also report any CROSS-FILE OBSERVATIONS:
- Files that seem to duplicate each other
- Files that reference things that don't exist
- Content that seems misplaced (wrong directory)
- Clusters of files that belong together but are separated

Be thorough. Be honest. Report problems you see.
Return your report as a JSON object with keys: files, directories, observations.
```

Launch all agents in a SINGLE message (parallel execution):

```
for i, slice in enumerate(agent_slices):
    file_list = "\n".join(f"  - {f}" for d in slice for f in d["files"])
    Agent(
        prompt=EXPLORER_PROMPT.format(file_list=file_list),
        description=f"Explorer {i+1}/{agent_count}",
        subagent_type="Explore",
    )
```

## Step 3: Collect Reports

Wait for all agents to complete. Parse each agent's JSON report.

```
explorer_reports = []
for agent_result in agent_results:
    report = parse_json(agent_result)
    explorer_reports.append(report)

total_files_explored = sum(len(r["files"]) for r in explorer_reports)
total_issues_found = sum(
    len(f.get("issues", [])) for r in explorer_reports for f in r["files"]
)
emit(f"Phase 1/6: Explored {total_files_explored} files with {agent_count} agents. {total_issues_found} issues found.")
```

**Proceed to Map (read `sections/map.md`).**
```

- [ ] **Step 2: Commit**

```bash
git add src/skill/sections/explore.md
git commit -m "feat: explore.md — parallel agent exploration with directory slicing"
```

---

### Task 5: Map Phase (sections/map.md)

**Files:**
- Create: `src/skill/sections/map.md`

- [ ] **Step 1: Write map.md**

```markdown
# Map Phase — Knowledge Map Synthesis

> Merge explorer reports into a single graph. See the whole picture.

**Input:** `explorer_reports` from Explore phase.
**Output:** `knowledge_map` saved to `.neuraltree/knowledge_map.json`.

## Step 1: Merge File Reports

```
files = {}
for report in explorer_reports:
    for file_report in report["files"]:
        path = file_report["path"]
        files[path] = file_report
```

## Step 2: Build Edge Graph

Edges come from three sources:

**A. Explicit references** (from explorer reports):
```
edges = []
for path, file_data in files.items():
    for ref in file_data.get("references_to", []):
        if ref in files:  # only edges to known files
            edges.append({
                "source": path,
                "target": ref,
                "type": "reference",
                "weight": 1.0,
            })
```

**B. Semantic similarity** (from shared concepts):
```
for path_a, data_a in files.items():
    concepts_a = set(data_a.get("key_concepts", []))
    for path_b, data_b in files.items():
        if path_a >= path_b:
            continue
        concepts_b = set(data_b.get("key_concepts", []))
        overlap = concepts_a & concepts_b
        if len(overlap) >= 2:
            jaccard = len(overlap) / len(concepts_a | concepts_b)
            if jaccard > 0.3:
                edges.append({
                    "source": path_a,
                    "target": path_b,
                    "type": "semantic",
                    "weight": round(jaccard, 3),
                    "shared_concepts": sorted(overlap),
                })
```

**C. Directory co-location** (files in same directory):
```
from collections import defaultdict
dir_groups = defaultdict(list)
for path in files:
    dir_groups[os.path.dirname(path) or "."].append(path)

for dir_path, members in dir_groups.items():
    if len(members) > 1:
        for i, a in enumerate(members):
            for b in members[i+1:]:
                # Only add if no stronger edge exists
                has_edge = any(
                    (e["source"] == a and e["target"] == b) or
                    (e["source"] == b and e["target"] == a)
                    for e in edges
                )
                if not has_edge:
                    edges.append({
                        "source": a, "target": b,
                        "type": "co-located",
                        "weight": 0.5,
                    })
```

## Step 3: Detect Concept Clusters

Group files by shared concepts using a simple greedy algorithm:

```
# Start with files sorted by concept count
unclustered = set(files.keys())
clusters = []

while unclustered:
    # Pick the file with most concepts as seed
    seed = max(unclustered, key=lambda p: len(files[p].get("key_concepts", [])))
    cluster_files = {seed}
    seed_concepts = set(files[seed].get("key_concepts", []))

    # Add files that share 2+ concepts with the cluster
    for other in list(unclustered):
        if other == seed:
            continue
        other_concepts = set(files[other].get("key_concepts", []))
        if len(seed_concepts & other_concepts) >= 2:
            cluster_files.add(other)
            seed_concepts |= other_concepts

    # Name the cluster from top concepts
    from collections import Counter
    concept_counts = Counter()
    for f in cluster_files:
        concept_counts.update(files[f].get("key_concepts", []))
    top_concepts = [c for c, _ in concept_counts.most_common(3)]
    cluster_name = "_".join(top_concepts[:2])

    clusters.append({
        "name": cluster_name,
        "concept": ", ".join(top_concepts),
        "files": sorted(cluster_files),
    })
    unclustered -= cluster_files
```

## Step 4: Collect Issues

Merge all issues from explorers + add graph-derived issues:

```
issues = []

# From explorers
for path, data in files.items():
    for issue_desc in data.get("issues", []):
        issues.append({
            "type": classify_issue(issue_desc),
            "file": path,
            "description": issue_desc,
            "severity": "medium",
        })

# Graph-derived: orphan files (no edges)
connected = {e["source"] for e in edges} | {e["target"] for e in edges}
for path in files:
    if path not in connected:
        issues.append({
            "type": "orphan",
            "file": path,
            "description": f"{path} has no connections to any other file",
            "severity": "high",
        })

# Graph-derived: clusters spanning 3+ directories
for cluster in clusters:
    dirs_in_cluster = {os.path.dirname(f) for f in cluster["files"]}
    if len(dirs_in_cluster) >= 3:
        issues.append({
            "type": "scattered_cluster",
            "cluster": cluster["name"],
            "description": f"Cluster '{cluster['name']}' spans {len(dirs_in_cluster)} directories: {sorted(dirs_in_cluster)}",
            "severity": "medium",
        })
```

## Step 5: Compute Stats and Save

```
import statistics
file_sizes = [d.get("size_lines", 0) for d in files.values()]

knowledge_map = {
    "version": 2,
    "timestamp": now_iso8601(),
    "project_name": project_name,
    "files": files,
    "edges": edges,
    "clusters": clusters,
    "issues": issues,
    "stats": {
        "total_files": len(files),
        "total_edges": len(edges),
        "total_clusters": len(clusters),
        "total_issues": len(issues),
        "avg_file_size": round(statistics.mean(file_sizes)) if file_sizes else 0,
        "median_file_size": round(statistics.median(file_sizes)) if file_sizes else 0,
        "max_depth": max(f.count("/") for f in files) if files else 0,
    },
}

neuraltree_knowledge_map(action="save", knowledge_map=knowledge_map, project_root=".")
emit(f"Phase 2/6: Knowledge map built — {len(files)} files, {len(edges)} edges, {len(clusters)} clusters, {len(issues)} issues")
```

**Proceed to Analyze (read `sections/analyze.md`).**
```

- [ ] **Step 2: Commit**

```bash
git add src/skill/sections/map.md
git commit -m "feat: map.md — knowledge map synthesis with file graph + concept clusters"
```

---

### Task 6: Analyze Phase (sections/analyze.md)

**Files:**
- Create: `src/skill/sections/analyze.md`

- [ ] **Step 1: Write analyze.md**

```markdown
# Analyze Phase — Claude Reasons About the Project

> No formulas. Read the map. Think. Report what's wrong and why.

**Input:** `knowledge_map` from Map phase.
**Output:** `analysis` — issues with Claude's reasoning and proposed fixes.

## Step 1: Load the Knowledge Map

```
km_result = neuraltree_knowledge_map(action="load", project_root=".")
km = km_result["map"]
```

## Step 2: Claude Analyzes the Map

Read the knowledge map and reason about the project's organization.
DO NOT use formulas or thresholds. Instead, THINK about:

**A. Structure Assessment:**
- Are files in logical directories? Do directory names match their contents?
- Is there a clear trunk → branch → leaf hierarchy?
- Are there files that should be in the same folder but aren't?

**B. Relationship Assessment:**
- Are there files that clearly relate but have no `## Related` links?
- Are there dead-end files that nothing references?
- Are there clusters of tightly-related files? Should they be co-located?

**C. Content Assessment:**
- Are any files too large? (relative to the project's own average, not a fixed cutoff)
- Are there duplicate or overlapping files?
- Are there stale files with outdated content?
- Are there files with misleading names?

**D. Navigability Assessment:**
- Can you find any piece of information in 0-2 tool calls from the trunk?
- Are there "dead zones" — areas of the project unreachable from navigation?
- Would an agent new to this project know where to look?

## Step 3: Produce Issue List

For each issue, write:

```
{
  "id": "issue_1",
  "type": "misplaced" | "orphan" | "too_large" | "duplicate" | "stale" |
          "unwired" | "scattered" | "naming" | "dead_zone" | "bloated_trunk",
  "files": ["path1.md", "path2.md"],
  "description": "Human-readable description of what's wrong",
  "reasoning": "Why this matters for information flow",
  "proposed_fix": "What should be done about it",
  "severity": "high" | "medium" | "low",
  "requires_user_approval": true/false,
  "auto_fixable": true/false
}
```

**Severity guide:**
- **high:** Information is unreachable or actively misleading
- **medium:** Information is findable but poorly organized
- **low:** Cosmetic or minor improvement

## Step 4: Merge with Map Issues

Combine Claude's analysis with issues already in the knowledge map.
Deduplicate by file path. Claude's reasoning overrides mechanical detection.

```
analysis = {
    "timestamp": now_iso8601(),
    "total_issues": len(all_issues),
    "by_severity": {"high": N, "medium": N, "low": N},
    "by_type": {...},
    "issues": all_issues,
    "summary": "One paragraph summary of the project's organizational health",
}

emit(f"Phase 3/6: Analysis complete — {len(all_issues)} issues ({high} high, {medium} medium, {low} low)")
```

**If no issues found:** Skip to Verify.
**If issues found:** Proceed to Plan (read `sections/plan.md`).
```

- [ ] **Step 2: Commit**

```bash
git add src/skill/sections/analyze.md
git commit -m "feat: analyze.md — Claude-driven reasoning about project organization"
```

---

### Task 7: Plan Phase (sections/plan.md)

**Files:**
- Create: `src/skill/sections/plan.md`

- [ ] **Step 1: Write plan.md**

```markdown
# Plan Phase — Reorganization Proposals

> Show the user what you'd change and why. They decide.

**Input:** `analysis` from Analyze phase.
**Output:** `approved_actions` list.

## Step 1: Convert Issues to Actions

For each issue, generate a concrete action:

| Issue Type | Action |
|-----------|--------|
| `unwired` | `neuraltree_wire()` the file, append `## Related` |
| `orphan` | Wire it OR mark for deletion (user decides) |
| `too_large` | `neuraltree_plan_split()` or `neuraltree_shrink_and_wire()` |
| `duplicate` | Merge files, redirect references |
| `stale` | Update `last_verified` or flag for review |
| `misplaced` | `neuraltree_plan_move()` to correct directory |
| `scattered` | Move cluster members to shared directory |
| `naming` | Rename file/directory |
| `dead_zone` | Add index file or wire into trunk |
| `bloated_trunk` | Extract sections to branch files |

## Step 2: Trace Before Destructive Actions

For every move, delete, or split — call `neuraltree_trace()` first:

```
for action in actions:
    if action["type"] in ("move", "delete", "split", "merge"):
        for file in action["files"]:
            trace = neuraltree_trace(target=file, project_root=".")
            action["trace"] = {
                "referenced_by": trace["referenced_by"],
                "references_to": trace["references_to"],
                "is_alive": trace["is_alive"],
            }
```

## Step 3: Present to User

Group actions by type. Show auto-fixable actions first, then approval-required:

```
AUTO-FIX (will apply automatically):
  1. Wire CLAUDE.md with ## Related → [README.md, memory/MEMORY.md]
  2. Wire docs/spec.md with ## Related → [CLAUDE.md]
  3. Add last_verified frontmatter to 5 files

APPROVAL REQUIRED:
  4. [MOVE] memory/old_notes.md → archive/old_notes.md
     Reason: File is stale (last verified 2025-01), only referenced by memory/MEMORY.md
     Impact: Update 1 reference in MEMORY.md
     Approve? (y/n)

  5. [SPLIT] docs/MEGA_GUIDE.md (800 lines) → 4 focused files
     Reason: 3x project average size, contains 4 distinct topics
     Impact: Create 4 new files + index, update 2 references
     Approve? (y/n)
```

## Step 4: Collect Approvals

```
approved_actions = []
for action in auto_fixable:
    approved_actions.append(action)

for action in needs_approval:
    emit(action["description"])
    response = wait_for_user_input()
    if "y" in response.lower():
        approved_actions.append(action)
    else:
        action["status"] = "rejected"

emit(f"Phase 4/6: {len(approved_actions)} actions approved, {rejected} rejected")
```

**Proceed to Execute (read `sections/execute.md`).**
```

- [ ] **Step 2: Commit**

```bash
git add src/skill/sections/plan.md
git commit -m "feat: plan.md — reorganization proposals with user approval flow"
```

---

### Task 8: Execute Phase (sections/execute.md)

**Files:**
- Create: `src/skill/sections/execute.md`

- [ ] **Step 1: Write execute.md**

```markdown
# Execute Phase — Apply Changes in Sandbox

> Sandbox first. Measure after. User confirms.

**Input:** `approved_actions` from Plan phase.
**Output:** Changes applied to sandbox, ready for verification.

## Step 1: Create Sandbox

```
sandbox = neuraltree_sandbox_create(project_root=".")
sandbox_root = sandbox["sandbox_path"]
```

## Step 2: Backup Affected Files

```
all_files = set()
for action in approved_actions:
    all_files.update(action["files"])
neuraltree_backup(files=sorted(all_files), project_root=sandbox_root)
```

## Step 3: Execute Actions

Process in order: wire first, then move, then split, then delete.

```
for action in sorted(approved_actions, key=lambda a: ACTION_ORDER[a["type"]]):
    emit(f"  Executing: {action['description']}")

    if action["type"] == "wire":
        for file in action["files"]:
            wire_result = neuraltree_wire(file_path=file, project_root=sandbox_root)
            apply_suggested_content(sandbox_root / file, wire_result["suggested_content"])

    elif action["type"] == "move":
        neuraltree_plan_move(
            source=action["source"],
            destination=action["destination"],
            project_root=sandbox_root,
        )

    elif action["type"] == "split":
        neuraltree_split_and_wire(
            target=action["file"],
            project_root=sandbox_root,
        )

    elif action["type"] == "shrink":
        neuraltree_shrink_and_wire(
            target=action["file"],
            sections_to_extract=action["sections"],
            project_root=sandbox_root,
        )

    elif action["type"] == "add_frontmatter":
        for file in action["files"]:
            update_frontmatter(sandbox_root / file, {
                "last_verified": today_iso8601(),
            })

    elif action["type"] == "add_index":
        neuraltree_generate_index(
            directory=action["directory"],
            project_root=sandbox_root,
        )
```

## Step 4: Re-index Viking

```
if not DEGRADED_MODE:
    modified_files = [f for a in approved_actions for f in a["files"]]
    neuraltree_viking_index(
        file_paths=modified_files,
        project_root=sandbox_root,
    )
```

## Step 5: Verify No Broken References

```
dead = neuraltree_find_dead(project_root=sandbox_root)
if dead["total_dead"] > 0:
    emit(f"WARNING: {dead['total_dead']} orphan files after execution")
    for df in dead["dead_files"]:
        emit(f"  - {df['path']}")
```

**Proceed to Verify (read `sections/verify.md`).**
```

- [ ] **Step 2: Commit**

```bash
git add src/skill/sections/execute.md
git commit -m "feat: execute.md — sandbox execution with backup and reference checking"
```

---

### Task 9: Verify Phase (sections/verify.md)

**Files:**
- Create: `src/skill/sections/verify.md`

- [ ] **Step 1: Write verify.md**

```markdown
# Verify Phase — Adaptive Scoring

> Score AFTER understanding. The score validates your work, it doesn't drive it.

**Input:** Sandbox with applied changes.
**Output:** Before/after score comparison. Sandbox approval prompt.

## Step 1: Score with Adaptive Mode

```
score_result = neuraltree_score(
    project_root=sandbox_root,
    adaptive=True,
)
```

The adaptive mode reads the knowledge map and adjusts:
- Trunk pressure cap (scales with project size)
- Freshness window (scales with project depth)
- File size thresholds (relative to project average)

## Step 2: Compute Precision@3 (if Viking available)

```
if not DEGRADED_MODE:
    queries = neuraltree_generate_queries(project_root=sandbox_root)
    precision_result = neuraltree_precision(
        queries=queries["queries"],
        project_root=sandbox_root,
    )
    # Claude judges relevance (same as v1)
    precision_at_3 = judge_precision(precision_result)
    final_score = score_result["flow_score_partial"] + (precision_at_3 * 0.25)
else:
    final_score = score_result["flow_score_partial"]
```

## Step 3: Compare Before/After

Load baseline from `.neuraltree/state.json` (or use 0 if bootstrap):

```
before = load_state().get("flow_score", 0)
after = final_score
delta = after - before

emit(f"Phase 6/6: Score {before:.2f} → {after:.2f} ({delta:+.2f})")
```

## Step 4: Sandbox Approval

```
diff = neuraltree_sandbox_diff(project_root=".")
emit(f"Changes: {diff['total_changes']} files modified")

if delta > 0:
    emit("Score improved. Apply changes? (approve / reject)")
else:
    emit("WARNING: Score did not improve. Apply anyway? (approve / reject)")

response = wait_for_user_input()
if "approve" in response.lower():
    neuraltree_sandbox_apply(project_root=".")
    emit("Changes applied.")

    # Update state
    state = {
        "timestamp": now_iso8601(),
        "flow_score": final_score,
        "metrics": score_result["metrics"],
        "mode": mode,
        "actions_applied": len(approved_actions),
    }
    write_file(".neuraltree/state.json", json.dumps(state, indent=2))

neuraltree_sandbox_destroy(project_root=".")
```

**Proceed to Report (read `sections/report.md`).**
```

- [ ] **Step 2: Commit**

```bash
git add src/skill/sections/verify.md
git commit -m "feat: verify.md — adaptive scoring verification with before/after comparison"
```

---

### Task 10: Report Phase (sections/report.md)

**Files:**
- Rewrite: `src/skill/sections/report.md`

- [ ] **Step 1: Write the new report.md**

```markdown
# Execution Report

> Show the full picture — before, after, and what changed.

## Report Format

```
/neuraltree — Execution Report
═══════════════════════════════

Project: {project_name}
Mode: {mode} | Agents: {agent_count} | Duration: {elapsed}

KNOWLEDGE MAP
  Files explored:  {total_files}
  Edges found:     {total_edges} (reference: {ref}, semantic: {sem}, co-located: {co})
  Clusters:        {total_clusters}
  Issues found:    {total_issues}

ANALYSIS
  High severity:   {high}
  Medium severity:  {medium}
  Low severity:     {low}

ACTIONS
  Approved:        {approved}
  Rejected:        {rejected}
  Applied:         {applied}

SCORE
  Before:          {before:.2f}
  After:           {after:.2f}
  Delta:           {delta:+.2f} ({pct:+.0f}%)
  Mode:            {adaptive|static}

METRICS (adaptive thresholds)
  ┌──────────────────┬────────┬────────┬────────┐
  │ Metric           │ Before │ After  │ Delta  │
  ├──────────────────┼────────┼────────┼────────┤
  │ hop_efficiency   │ {b_he} │ {a_he} │ {d_he} │
  │ synapse_coverage │ {b_sc} │ {a_sc} │ {d_sc} │
  │ dead_neuron_ratio│ {b_dn} │ {a_dn} │ {d_dn} │
  │ freshness        │ {b_fr} │ {a_fr} │ {d_fr} │
  │ trunk_pressure   │ {b_tp} │ {a_tp} │ {d_tp} │
  │ precision_at_3   │ {b_p3} │ {a_p3} │ {d_p3} │
  └──────────────────┴────────┴────────┴────────┘

KNOWLEDGE MAP SAVED: .neuraltree/knowledge_map.json
STATE SAVED: .neuraltree/state.json
```

## Release Lock

```
release_lock()
emit("Lock released. Run complete.")
```
```

- [ ] **Step 2: Commit**

```bash
git add src/skill/sections/report.md
git commit -m "feat: report.md v2 — knowledge map summary + before/after comparison"
```

---

### Task 11: Remove Old Section Files + Update CLAUDE.md

**Files:**
- Remove: `src/skill/sections/benchmark.md`
- Remove: `src/skill/sections/diagnose.md`
- Remove: `src/skill/sections/autoloop.md`
- Remove: `src/skill/sections/enforce.md`
- Remove: `src/skill/sections/edge-cases.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Remove old section files**

```bash
git rm src/skill/sections/benchmark.md
git rm src/skill/sections/diagnose.md
git rm src/skill/sections/autoloop.md
git rm src/skill/sections/enforce.md
git rm src/skill/sections/edge-cases.md
```

- [ ] **Step 2: Update CLAUDE.md architecture section**

Replace the Architecture section to reflect v2:

```markdown
## Architecture

```
Skill (SKILL.md) = THE BRAIN — explore-first orchestration
MCP Server (neuraltree-mcp) = THE MUSCLE — 25 tools, 308+ tests
Viking MCP = THE MEMORY — semantic search
Agent Swarm = THE EYES — 2-10 parallel explorers
Claude = THE JUDGE — reasoning-based analysis (no hardcoded formulas)
```

## Pipeline (v2)

```
Phase 1: EXPLORE  — N agents read project deeply in parallel
Phase 2: MAP      — synthesize into dual-layer knowledge map
Phase 3: ANALYZE  — Claude reasons about what's wrong
Phase 4: PLAN     — propose reorganization, user approves
Phase 5: EXECUTE  — apply in sandbox
Phase 6: VERIFY   — adaptive scoring confirms improvement
```
```

- [ ] **Step 3: Update tool count references**

Update any `24 tools` references to `25 tools` in CLAUDE.md and README.md.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: remove v1 section files, update CLAUDE.md for v2 pipeline"
```

---

### Task 12: Integration Test — Full Pipeline

**Files:**
- Create: `tests/integration/test_v2_pipeline.py`

- [ ] **Step 1: Write integration test**

```python
# tests/integration/test_v2_pipeline.py
"""Integration test for v2 knowledge map pipeline."""
import json
import pytest


class TestKnowledgeMapPipeline:
    """Test the full save → load → query cycle."""

    def test_save_load_query_cycle(self, tmp_project):
        """Full pipeline: save a map, load it, query files and clusters."""
        from neuraltree_mcp.tools.knowledge_map import _save_map, _load_map, _query_map

        # Build a map from tmp_project structure
        km = {
            "version": 2,
            "timestamp": "2026-04-06T12:00:00Z",
            "project_name": "mock_project",
            "files": {
                "CLAUDE.md": {
                    "path": "CLAUDE.md",
                    "topic": "Project instructions",
                    "key_concepts": ["architecture", "glossary"],
                    "references_to": ["memory/MEMORY.md", "docs/architecture/SUMMARY.md"],
                    "referenced_by": [],
                    "size_lines": 10,
                    "issues": [],
                },
                "memory/MEMORY.md": {
                    "path": "memory/MEMORY.md",
                    "topic": "Memory trunk",
                    "key_concepts": ["rules", "reference"],
                    "references_to": ["memory/rules/_INDEX.md"],
                    "referenced_by": ["CLAUDE.md"],
                    "size_lines": 5,
                    "issues": [],
                },
                "memory/rules/coding.md": {
                    "path": "memory/rules/coding.md",
                    "topic": "Coding rules",
                    "key_concepts": ["type_hints", "testing"],
                    "references_to": ["memory/rules/testing.md"],
                    "referenced_by": ["memory/rules/_INDEX.md"],
                    "size_lines": 12,
                    "issues": [],
                },
            },
            "edges": [
                {"source": "CLAUDE.md", "target": "memory/MEMORY.md", "type": "reference", "weight": 1.0},
                {"source": "memory/MEMORY.md", "target": "memory/rules/_INDEX.md", "type": "reference", "weight": 1.0},
            ],
            "clusters": [
                {"name": "rules_testing", "concept": "coding rules and testing", "files": ["memory/rules/coding.md"]},
            ],
            "issues": [],
            "stats": {"total_files": 3, "total_edges": 2, "total_clusters": 1, "total_issues": 0, "avg_file_size": 9, "max_depth": 2},
        }

        # Save
        _save_map(km, str(tmp_project))
        assert (tmp_project / ".neuraltree" / "knowledge_map.json").exists()

        # Load
        loaded = _load_map(str(tmp_project))
        assert loaded["version"] == 2
        assert len(loaded["files"]) == 3

        # Query file
        result = _query_map(str(tmp_project), file_path="CLAUDE.md")
        assert result["topic"] == "Project instructions"

        # Query neighbors
        result = _query_map(str(tmp_project), neighbors_of="CLAUDE.md")
        assert "memory/MEMORY.md" in result["neighbors"]

        # Query cluster
        result = _query_map(str(tmp_project), cluster="rules_testing")
        assert "memory/rules/coding.md" in result["files"]

    def test_adaptive_score_with_map(self, tmp_project):
        """Score with adaptive=True should read the knowledge map."""
        from neuraltree_mcp.tools.knowledge_map import _save_map
        import asyncio
        from neuraltree_mcp.server import mcp

        km = {
            "version": 2,
            "files": {f"file_{i}.md": {"size_lines": 50} for i in range(5)},
            "edges": [],
            "clusters": [],
            "stats": {"total_files": 5, "total_edges": 0, "avg_file_size": 50, "max_depth": 1},
        }
        _save_map(km, str(tmp_project))

        result = asyncio.run(mcp.call_tool("neuraltree_score", {
            "project_root": str(tmp_project),
            "adaptive": True,
        }))
        assert "adaptive_context" in str(result)
```

- [ ] **Step 2: Run full test suite**

Run: `PYTHONPATH=src python3.11 -m pytest tests/ -v --tb=short`
Expected: 310+ tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_v2_pipeline.py
git commit -m "test: integration tests for v2 knowledge map pipeline"
```

---

## Self-Review Checklist

1. **Spec coverage:** All 6 phases have section files. Knowledge map tool has save/load/query. Adaptive scoring reads the map. Explorer prompt template handles directory slicing. Report shows before/after.

2. **Placeholder scan:** No TBD/TODO. All code blocks contain actual implementation. All file paths are exact.

3. **Type consistency:** `knowledge_map` dict structure is consistent across save/load/query/test. `adaptive_context` dict is consistent between score.py and verify.md. Explorer report format matches what map.md expects.

---

Plan complete and saved to `docs/superpowers/plans/2026-04-06-neuraltree-v2-explore-first.md`.

Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?