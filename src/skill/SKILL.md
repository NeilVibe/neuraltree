---
name: neuraltree
description: >
  Universal neural organization — transforms any project into a structured
  information system where any fact is reachable in 0-2 hops.
version: 0.1.0
tools_required:
  - neuraltree-mcp (16 tools)
  - openviking (semantic search)
---

# /neuraltree — Universal Neural Organization Skill

> You are the brain. neuraltree-mcp is the muscle. Viking is the memory.
> Your job: orchestrate them to make information FLOW.

---

## Section 1: Activation

When `/neuraltree` is invoked, execute these five steps in order. Do NOT skip steps. Do NOT proceed past a failed step unless explicitly noted.

### Step 1: Verify Tools

Both tool backends must be reachable before any work begins.

1. **neuraltree-mcp** — call `neuraltree_scan(project_root=".", include_contents=false)`.
   - If it returns a file inventory: **PASS**. Record the `total_files` count.
   - If it errors (connection refused, tool not found, timeout): **ABORT**.
     Print: `FATAL: neuraltree-mcp is not available. Install and configure it before running /neuraltree.`
     Release lock if acquired. Stop.

2. **Viking (openviking)** — call `viking_search(query="test")`.
   - If it returns results (even empty): **PASS**.
   - If it errors (connection refused, server down, timeout): set `DEGRADED_MODE = true`.
     Print: `WARNING: Viking is unavailable. Running in DEGRADED mode — semantic search disabled, precision_at_3 will be null, EMBEDDING_GAP detection disabled.`
     Continue — the skill can still run, but scoring will be partial (Flow Score capped at 0.75).

Record tool status for Step 5:

```
tools:
  neuraltree_mcp: PASS | ABORT
  viking:         PASS | DEGRADED
```

### Step 2: Detect Mode

Read `.neuraltree/state.json` from the project root. This file is Skill-owned — the MCP server does NOT create or manage it.

**If `.neuraltree/state.json` does not exist** — this is a first run. Mode = `bootstrap`.

**If it exists** — parse these fields:
- `flow_score` (float, 0.0–1.0): last computed Flow Score
- `last_run` (ISO 8601 timestamp): when the skill last completed a full run
- `calibration_version` (int): prediction model version

Determine mode from this decision table:

| Condition | Mode | Pipeline | Rationale |
|-----------|------|----------|-----------|
| No `state.json` | **bootstrap** | Benchmark → Diagnose → AutoLoop → Enforce | First run. Full analysis needed. |
| `state.json` exists, `flow_score < 0.60` | **critical** | Benchmark → Diagnose → AutoLoop → Enforce | Information flow is broken. Full intervention. |
| `state.json` exists, `last_run > 7 days ago` | **health-check** | Benchmark → Diagnose → Fix if degraded → Enforce | Stale data. Re-evaluate everything. |
| `state.json` exists, `last_run ≤ 7 days`, `flow_score > 0.90` | **spot-check** | Benchmark (critical queries only) | Project is healthy. Quick verification. |
| `state.json` exists, `last_run ≤ 7 days`, `0.60 ≤ flow_score ≤ 0.90` | **maintenance** | Benchmark → Diagnose degraded areas → Enforce | Stable but imperfect. Targeted fixes. |

**Priority rules** (evaluated top-to-bottom, first match wins):
1. No state.json → bootstrap
2. flow_score < 0.60 → critical (regardless of last_run)
3. last_run > 7 days → health-check (regardless of flow_score, since it's ≥ 0.60)
4. flow_score > 0.90 → spot-check
5. Everything else → maintenance

Store the detected mode for use in all subsequent sections.

### Step 3: Acquire Lock

The lock prevents concurrent runs from corrupting state. ALL skill operations that write to `.neuraltree/` MUST hold the lock.

**Lock file:** `.neuraltree/.lock`

**Protocol:**

1. Check if `.neuraltree/.lock` exists.

2. **If it exists** — read the timestamp inside.
   - If the lock is **older than 1 hour**: auto-remove it.
     Print: `WARNING: Stale lock detected (created {timestamp}). Auto-removing — previous run likely crashed.`
   - If the lock is **less than 1 hour old**: **ABORT**.
     Print: `ABORT: Another /neuraltree run is active (lock created {timestamp}). Wait for it to finish or manually remove .neuraltree/.lock if it crashed.`
     Stop. Do NOT proceed.

3. **Create the lock** — write current ISO 8601 timestamp to `.neuraltree/.lock`.

4. **CRITICAL: ALL exit paths MUST release the lock.** This includes:
   - Normal completion
   - Errors / exceptions
   - User cancellation
   - ABORT conditions in later sections

   The lock release pattern:
   ```
   try:
     [all skill work here]
   finally:
     delete .neuraltree/.lock
   ```

   If you are an AI agent executing this skill: before you finish your response (whether success or failure), you MUST delete `.neuraltree/.lock`. No exceptions.

### Step 4: Handle Subcommands

If the user invoked `/neuraltree` with a subcommand, route to the specific pipeline instead of the auto-detected mode pipeline.

| Subcommand | Pipeline | Description |
|------------|----------|-------------|
| `/neuraltree audit` | Benchmark only | Read-only analysis. No changes to project. No AutoLoop. Outputs Flow Score + gap report. |
| `/neuraltree fix` | Diagnose → AutoLoop | Skip benchmarking (use last score). Jump straight to fixing diagnosed gaps. |
| `/neuraltree enforce` | Enforce only | Update state.json, re-index Viking, clean .tmp files. No analysis or fixes. |
| `/neuraltree benchmark` | Full Benchmark report | Detailed scoring with per-metric breakdown, query results, precision analysis. More verbose than `audit`. |
| `/neuraltree auto` | Full pipeline (same as bootstrap) | Benchmark → Diagnose → AutoLoop → Enforce. Ignores mode detection — always runs everything. |
| `/neuraltree` (no subcommand) | Mode-detected pipeline | Uses the mode from Step 2 to determine which pipeline sections to execute. |

**Subcommand overrides mode.** If the user says `/neuraltree audit`, run the audit pipeline even if mode detection says `critical`. The user's explicit intent takes priority.

**Unknown subcommands:** Print `Unknown subcommand: {cmd}. Available: audit, fix, enforce, benchmark, auto` and ABORT (release lock).

### Step 5: Emit Status

Before entering any pipeline section, print a status block so the user (and any observing agents) know the starting conditions:

```
╔══════════════════════════════════════════════╗
║  /neuraltree — Activation Complete           ║
╠══════════════════════════════════════════════╣
║  Mode:        {mode}                         ║
║  Pipeline:    {pipeline description}         ║
║  Tools:                                      ║
║    neuraltree-mcp:  ✓ ({file_count} files)   ║
║    viking:          ✓ | DEGRADED             ║
║  Lock:        acquired ({timestamp})         ║
║  State:       {exists|new} (score: {N.NN})   ║
╚══════════════════════════════════════════════╝
```

Replace placeholders with actual values from Steps 1–4.

**Then proceed to the pipeline section indicated by the mode or subcommand.**

---

*Section 2 (Artery Principle) follows. This section is the entry point — everything else flows from here.*
