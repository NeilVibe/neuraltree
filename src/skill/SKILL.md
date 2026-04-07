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
sections/understand.md      — Phase 1: explore + map (parallel agents + knowledge graph)
sections/analyze.md         — Phase 2: Claude-driven issue analysis
sections/plan.md            — Phase 3: reorganization proposals
sections/execute.md         — Phase 4: sandbox execution
sections/verify.md          — Phase 5: adaptive scoring verification
sections/report.md          — Output: before/after comparison
```

**At each phase boundary, read the next section file and execute it.**

---

## v1 vs v2 — What Changed

| v1 (metric-driven) | v2 (understanding-first) |
|--------------------|--------------------------|
| Score first, fix what formula says | Explore first, understand, then fix |
| Hardcoded weights (0.25, 0.20...) | Adaptive thresholds from project shape |
| Single-threaded autoloop | Parallel explorer agents (2-10) |
| Keyword Jaccard similarity | Deep reading + concept clustering |
| No knowledge map | Persistent dual-layer knowledge map |

---

## Helper Functions Reference

These are operations you perform directly (not MCP tools). Use your native capabilities:

| Function | What To Do |
|----------|-----------|
| `read_file(path)` | Read tool |
| `write_file(path, content)` | Write tool |
| `apply_suggested_content(file, content)` | Append `## Related` + `## Docs` block from `neuraltree_wire`. Replace if exists. |
| `update_frontmatter(file, fields)` | Parse YAML frontmatter, update fields, write back. |
| `wait_for_user_input()` | Ask the user and wait for response. |
| `release_lock()` | Delete `.neuraltree/.lock`. |
| `now_iso8601()` / `today_iso8601()` | Current datetime/date in ISO 8601. |

---

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

---

## The Artery Principle

> "It's NOT about disk space. It's about FLOW."

### The Four Principles

**1. Synapse Quality** — Every `## Related` link must lead somewhere alive and useful. Dead links waste hops.

**2. Hop Synergy** — Three layers: trunk (MEMORY.md, CLAUDE.md) → branch (_INDEX.md) → leaf (topic files). Each hop adds specificity.

**3. Electrical Flow** — `## Related` links fire toward the 2-4 files that **complete the thought**, not everything tangentially related.

**4. Trunk Pressure** — Trunk files are indexes, not content. Keep them lean.

### Decision Rules

1. **Understand before fixing.** Explore and map first. Only intervene where the map shows a problem.
2. **Trace before prune.** NEVER delete without calling `neuraltree_trace()` first.
3. **Show both sides.** Reports show KEPT and DELETED/CHANGED with proof.
4. **User approves destructive actions.** Wiring/indexing = auto. Deletes/moves/splits = ask.

---

## Section 1: Activation

When `/neuraltree` is invoked, execute these steps in order.

### Step 1: Verify Tools

1. **neuraltree-mcp** — call `neuraltree_scan(path=".", max_files=10000)`.
   - Returns file inventory: **PASS**. Record `total_count`, `files`, `dirs`.
   - Errors: **ABORT**. Print: `FATAL: neuraltree-mcp is not available.`

2. **Viking** — call `neuraltree_precision(queries=[{"text":"test"}], project_root=".")`.
   - `viking_available` true: **PASS**.
   - Viking unavailable: set `DEGRADED_MODE = true`. Print warning. Continue.

### Step 2: Detect Mode

Read `.neuraltree/knowledge_map.json` and `.neuraltree/state.json`.

| Condition | Mode | Pipeline |
|-----------|------|----------|
| No knowledge map | **full** | Understand → Analyze → Plan → Execute → Verify |
| Map exists, stale (>7 days) | **refresh** | Understand → Analyze → Plan → Execute → Verify |
| Map exists, recent, score < 0.60 | **fix** | Analyze → Plan → Execute → Verify |
| Map exists, recent, score >= 0.60 | **check** | Verify only (quick re-score) |

### Step 3: Determine Agent Count

Scale exploration to project size:

```
knowledge_files = [f for f in scan_result["files"]
                   if f.endswith((".md", ".txt"))
                   and not f.startswith((".pytest_cache/", ".ruff_cache/"))]
total_kb_files = len(knowledge_files)

if total_kb_files < 30:       agent_count = 2
elif total_kb_files < 100:    agent_count = 3
elif total_kb_files < 300:    agent_count = 5
elif total_kb_files < 1000:   agent_count = 7
else:                         agent_count = 10
```

### Step 4: Acquire Lock + Emit Status

Lock file: `.neuraltree/.lock` (contains ISO 8601 timestamp).
- Exists and < 1 hour: **ABORT** (another run active).
- Exists and > 1 hour: auto-remove (stale lock from crash).
- **ALL exit paths MUST release the lock** (try/finally pattern).

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
| `/neuraltree explore` | Understand only (explore + map) |
| `/neuraltree analyze` | Analyze only (uses existing map) |
| `/neuraltree fix` | Analyze → Plan → Execute → Verify |
| `/neuraltree verify` | Verify only (quick re-score) |
| `/neuraltree map` | Show knowledge map summary |
| `/neuraltree auto` | Full pipeline regardless of mode |

---

## Pipeline Routing

**After activation completes, execute phases by reading section files in order.**

### Phase 1: Understand
**Read `sections/understand.md` and execute all steps.**
Launch N explorer agents in parallel. Each reads a directory slice deeply.
Synthesize explorer reports into dual-layer knowledge map.
Layer 1: file graph (nodes + edges). Layer 2: concept clusters.
Save to `.neuraltree/knowledge_map.json`.

### Phase 2: Analyze
**Read `sections/analyze.md` and execute all steps.**
Claude reads the knowledge map and REASONS about what's wrong.
No formulas — understanding-driven issue identification.
Output: issues list with severity + proposed fixes.
*Skip if no issues found in map.*

### Phase 3: Plan
**Read `sections/plan.md` and execute all steps.**
Convert issues into concrete actions. Trace before destructive changes.
Show user: "Here's what I'd change and why." User approves per-item.
*Skip if no issues.*

### Phase 4: Execute
**Read `sections/execute.md` and execute all steps.**
Apply approved changes in sandbox. Wire new/moved files. Re-index Viking.
Verify no broken references.
*Skip if no approved actions.*

### Phase 5: Verify
**Read `sections/verify.md` and execute all steps.**
Score with adaptive mode. Compare before/after.
Score VALIDATES the changes — it doesn't drive them.

### Report
**Read `sections/report.md` and execute.**
Before/after comparison. Knowledge map summary. Action log.

---

**Lock must be released at the end of every run (success or failure). No exceptions.**
