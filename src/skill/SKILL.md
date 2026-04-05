---
name: neuraltree
description: >
  Universal neural organization — transforms any project into a structured
  information system where any fact is reachable in 0-2 hops.
version: 0.2.0
tools_required:
  - neuraltree-mcp (24 tools — includes Viking search + LLM judge integration)
---

# /neuraltree — Universal Neural Organization Skill

> You are the brain. neuraltree-mcp is the muscle. Viking is the memory.
> Your job: orchestrate them to make information FLOW.

## How This Skill Works

This file is the **router**. It contains activation, principles, and the pipeline flow.
Detailed step-by-step instructions for each phase live in `sections/` files — read them
on demand as you reach each phase. This keeps context lean (~400 lines always loaded
instead of ~2,200).

```
SKILL.md (this file)          — always loaded: activation + principles + routing
sections/benchmark.md         — Phase 2: queries + precision + score
sections/diagnose.md          — Phase 3: classify failures + priority queue
sections/autoloop.md          — Phase 4: Karpathy-style fix loop
sections/enforce.md           — Phase 5: persist gains + re-index
sections/report.md            — Output: metric table + pending actions
sections/edge-cases.md        — Error recovery + bootstrap edge cases
```

**At each phase boundary, read the next section file and execute it.**

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
| `parse_iso(timestamp)` / `timedelta(days=N)` | Date parsing and arithmetic. |
| `read_calibration_accuracy(path)` | Read `.neuraltree/calibration.json`, return `accuracy` (default 0.5). |
| `git_log_modified_files(since)` | Run `git log --name-only --since={since}`, deduplicate. |
| `is_knowledge_file(path)` | True if `.md` in `memory/`, `docs/`, or has frontmatter. |
| `summarize_fixes(kept_list)` | Count fix types: `["wire: 2", "index: 1"]`. |

> **Note:** Code blocks use Python-like pseudocode for clarity. Use your platform's equivalent operations.

---

## MCP Tools Reference (24 tools)

| Category | Tools |
|----------|-------|
| Filesystem | `neuraltree_scan`, `neuraltree_trace`, `neuraltree_backup`, `neuraltree_restore` |
| Intelligence | `neuraltree_wire`, `neuraltree_generate_queries` |
| Reorganize | `neuraltree_plan_move`, `neuraltree_plan_split`, `neuraltree_find_dead`, `neuraltree_generate_index`, `neuraltree_shrink_and_wire`, `neuraltree_split_and_wire` |
| Lessons | `neuraltree_lesson_match`, `neuraltree_lesson_add` |
| Scoring | `neuraltree_score`, `neuraltree_diagnose`, `neuraltree_predict`, `neuraltree_update_calibration` |
| Semantic | `neuraltree_precision` (Viking + LLM judge), `neuraltree_viking_index` (batch indexing) |
| Sandbox | `neuraltree_sandbox_create`, `neuraltree_sandbox_diff`, `neuraltree_sandbox_apply`, `neuraltree_sandbox_destroy` |

---

## Section 1: Activation

When `/neuraltree` is invoked, execute these five steps in order.

### Step 1: Verify Tools

1. **neuraltree-mcp** — call `neuraltree_scan(path=".", max_files=10000)`.
   - Returns file inventory: **PASS**. Record `total_count`.
   - Errors: **ABORT**. Print: `FATAL: neuraltree-mcp is not available.`

2. **Viking** — call `neuraltree_precision(queries=[{"text":"test"}], project_root=".")`.
   - `viking_available` true: **PASS**. Claude judges relevance (no external LLM needed).
   - Viking unavailable: set `DEGRADED_MODE = true`. Print warning. Continue (scoring capped at 0.75).

### Step 2: Detect Mode

Read `.neuraltree/state.json` (Skill-owned, not MCP-managed).

| Condition | Mode | Pipeline |
|-----------|------|----------|
| No `state.json` | **bootstrap** | Benchmark → Diagnose → AutoLoop (sandbox) → Enforce |
| `flow_score < 0.60` | **critical** | Benchmark → Diagnose → AutoLoop (sandbox) → Enforce |
| `last_run > 7 days` | **health-check** | Benchmark → Diagnose → Fix if degraded → Enforce |
| `flow_score > 0.90`, recent | **spot-check** | Benchmark (critical queries only) |
| Everything else | **maintenance** | Benchmark → Diagnose → Enforce |

Priority: bootstrap(1) > critical(2) > health-check(3) > spot-check(4) > maintenance(5).

### Step 3: Acquire Lock

Lock file: `.neuraltree/.lock` (contains ISO 8601 timestamp).

- Exists and < 1 hour: **ABORT** (another run active).
- Exists and > 1 hour: auto-remove (stale lock from crash).
- **ALL exit paths MUST release the lock** (try/finally pattern).

After acquiring: clean previous backup, start timer, derive project name.

### Step 4: Handle Subcommands

| Subcommand | Pipeline |
|------------|----------|
| `/neuraltree audit` | Benchmark only (read-only) |
| `/neuraltree fix` | Diagnose → AutoLoop (use last score) |
| `/neuraltree enforce` | Enforce only |
| `/neuraltree benchmark` | Full Benchmark report |
| `/neuraltree auto` | Full pipeline (ignore mode) |
| `/neuraltree` | Mode-detected pipeline |

Subcommand overrides mode. For `enforce` and `fix`, load baseline from last run's `state.json`.

### Step 5: Emit Status

```
/neuraltree — Activation Complete
Mode: {mode} | Pipeline: {pipeline} | ETA: ~{duration}
Tools: neuraltree-mcp ✓ ({file_count} files) | viking: ✓|DEGRADED | judge: Claude (sequential-thinking)
Lock: acquired | State: {exists|new} (score: {N.NN})
```

---

## Section 2: The Artery Principle

> "It's NOT about disk space. It's about FLOW."

### The Four Principles

**1. Synapse Quality** — Every `## Related` link must lead somewhere alive and useful. Dead links waste hops.

**2. Hop Synergy** — Three layers: trunk (MEMORY.md, CLAUDE.md) → branch (_INDEX.md) → leaf (topic files). Each hop adds specificity. Trunk directs, branch lists, leaf tells.

**3. Electrical Flow** — `## Related` links fire toward the 2-4 files that **complete the thought**, not everything tangentially related.

**4. Trunk Pressure** — >100 lines in a trunk file = pressure drops. Trunk files are indexes, not content.

### The 0-1-2 Hop Rule

| Hop | What's Reachable | Examples |
|-----|------------------|---------|
| 0 | Always in context | MEMORY.md, CLAUDE.md, rules/, .neuraltree/state.json |
| 1 | One tool call | _INDEX.md files, `neuraltree_scan()`, Viking search, Grep/Glob |
| 2 | Two tool calls | Leaf files via index → read, `neuraltree_trace()` → read |
| 3+ | **BROKEN** — treat as critical gap | Missing index, missing wiring, missing embedding |

### Perfect Neuron Format

```markdown
---
name: [topic]
description: [one-line summary]
type: [user | feedback | project | reference]
last_verified: [YYYY-MM-DD]
---

[Content — 20-80 lines, single topic]

## Related
- [other.md](path) — why these fire together

## Docs
- `path/to/source.py` — what it implements
```

### Decision Rules

1. **Cleanup is a side effect, not the goal.** Measure flow first. Only intervene where flow is broken.
2. **Trace before prune.** NEVER delete without calling `neuraltree_trace()` first.
3. **Show both sides.** Reports show KEPT and DELETED/CHANGED with proof.
4. **User approves destructive actions.** Wiring/indexing = auto. Deletes/moves/splits = ask.

---

## Section 3: Progress Protocol

Emit status at every phase boundary: `Phase {n}/{total}: {action}... {metric}`

| Mode | ETA |
|------|-----|
| spot-check | ~30s |
| health-check | ~1-3 min |
| maintenance | ~3-5 min |
| bootstrap/critical | ~8-15 min |

Phase denominators adjust per subcommand (audit=2, fix=3, enforce=1, auto/default=5).

---

## Pipeline Routing

**After activation completes, execute phases by reading section files in order.**

### Phase 2: Benchmark
**Read `sections/benchmark.md` and execute all steps.**
Generates queries, measures Precision@3 via `neuraltree_precision`, computes structural metrics, assembles Flow Score.

### Phase 3: Diagnose
**Read `sections/diagnose.md` and execute all steps.**
Classifies failed queries by gap type, enriches with dead neurons and lessons, builds priority queue.
*Skip if no failures (all queries passed).*

### Phase 4: AutoLoop
**Read `sections/autoloop.md` and execute all steps.**
Karpathy-style loop: analyze → propose → backup → execute → measure → keep/discard → learn → repeat.
*Skip if no failures.*

### Phase 5: Enforce
**Read `sections/enforce.md` and execute all steps.**
Graduate queries, compress history, update state.json, re-index Viking, install org rule, cleanup.

### Report
**Read `sections/report.md` and execute.**
Emit metric table, action lists, handle pending user approvals.

### Edge Cases
**Read `sections/edge-cases.md` when encountering:** no CLAUDE.md, no git, empty project, monorepo, concurrent runs, service failures, scale limits.

---

**Lock must be released at the end of every run (success or failure). No exceptions.**
