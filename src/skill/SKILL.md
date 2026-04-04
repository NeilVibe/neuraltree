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

---

## Section 2: The Artery Principle

> "It's NOT about disk space. It's about FLOW."

Organization exists for one reason: so information reaches the brain at the moment it's needed. A perfectly organized project where nothing is findable is worse than a messy one with good search. NeuralTree optimizes for **retrieval speed**, not tidiness.

### The Four Principles

#### 1. Synapse Quality

Every connection between files must lead somewhere **alive**. A `## Related` link to a deleted file is a dead synapse — it wastes a hop and erodes trust in the network. A link to a 500-line dump that buries the relevant paragraph is a **weak** synapse — technically alive, but the signal degrades in transit.

**Test:** Follow every link. Does it land on exactly what you need, within 10 seconds of reading? If not, the synapse is weak.

#### 2. Hop Synergy

The tree has three layers: **trunk** (indexes, MEMORY.md, CLAUDE.md), **branch** (_INDEX.md files, category directories), and **leaf** (individual topic files, source code). Each hop down the tree must add specificity:

- **Trunk** tells you WHERE to look (which branch)
- **Branch** tells you WHAT exists (which leaves)
- **Leaf** tells you THE THING (the actual knowledge)

If a trunk file contains leaf-level detail, it's doing two jobs and doing both badly. If a leaf file contains trunk-level overviews, it should be promoted or split.

**Test:** Read any trunk entry. Can you predict what the branch contains? Read any branch entry. Can you predict what the leaf says? If yes, hop synergy is working.

#### 3. Electrical Flow

The `## Related` section at the bottom of every neuron is the wiring. These synapses must fire toward the **right next neuron** — the one the reader most likely needs after absorbing this one.

Bad wiring: linking to everything tangentially related (creates noise).
Good wiring: linking to the 2-4 files that **complete the thought** or **answer the next question**.

**Test:** After reading a leaf, do the `## Related` links answer "what would I look for next?" If they answer "what else exists in this project?" the wiring is wrong.

#### 4. Trunk Pressure

The trunk (MEMORY.md, CLAUDE.md, _INDEX.md files) is the heart of the system. It loads into context on every session start. Every line in the trunk competes for attention with every other line.

**>100 lines in a trunk file = pressure drops.** The agent starts skimming. Critical entries get lost in the noise. Information that should be instant-access becomes buried.

**Rule:** Trunk files are indexes, not content. They point to branches. They never explain — they direct.

**Test:** Count the lines in MEMORY.md. If it exceeds 100, something that belongs in a branch has leaked into the trunk.

---

### The 0-1-2 Hop Rule

Every piece of project knowledge must be reachable in **at most 2 tool calls** from a fresh session. This is the fundamental performance guarantee of a neural tree.

#### HOP 0 — Always in Context

These files load automatically at session start. Zero tool calls needed.

- `MEMORY.md` — the trunk index
- `CLAUDE.md` — project instructions and structure
- `rules/` files — behavioral constraints
- `.neuraltree/state.json` — last known health

**If it's needed every session, it belongs at HOP 0.** If it's only needed sometimes, it does NOT belong here — trunk pressure.

#### HOP 1 — One Tool Call

One call to any of these retrieval methods reaches the branch layer:

- Read an `_INDEX.md` file (pointed to by trunk)
- `viking_search("query")` — semantic search across all indexed content
- `neuraltree_scan()` — file inventory
- `Grep` / `Glob` — pattern-based search

**If it's needed frequently but not every session, it belongs at HOP 1.** The trunk must point to it clearly enough that the agent knows which call to make.

#### HOP 2 — Two Tool Calls Maximum

A second call reaches the leaf layer: individual topic files, source code, archived content.

- HOP 1 (index or search) reveals the path → HOP 2 (read the file)
- `viking_search()` → `viking_read(uri)` for full content
- `neuraltree_trace(path)` → read the connected files

**If it's reference material, historical, or deeply specific, it belongs at HOP 2.**

#### NEVER HOP 3+

If reaching a piece of information requires 3 or more tool calls, the neural tree is broken. Possible causes:

- Missing index entry (trunk doesn't point to the right branch)
- Missing `## Related` link (leaf doesn't wire to its neighbor)
- Missing Viking embedding (content exists but isn't indexed)
- File buried too deep in directory nesting

**When `neuraltree_diagnose()` reports HOP 3+ paths, treat them as critical gaps.**

---

### Perfect Neuron Format

Every leaf file in the neural tree must follow this template. The format is not decorative — each section serves the retrieval system.

```markdown
---
name: [topic]
description: [one-line summary — what Viking indexes, what _INDEX.md displays]
type: [user | feedback | project | reference]
last_verified: [YYYY-MM-DD — when a human or agent confirmed this is still accurate]
---

[Content — 20-80 lines, single topic only]

## Related
- [other_leaf.md](path) — why these fire together

## Docs
- `path/to/source.py` — what it implements
```

**Frontmatter** (required):
- `name` — the topic, used for search and display
- `description` — one line, appears in index listings and Viking search results
- `type` — categorization for filtering (`user` = about the human, `feedback` = from reviews/retrospectives, `project` = about the codebase, `reference` = stable external knowledge)
- `last_verified` — staleness detection. Files not verified in 90+ days get flagged by `neuraltree_diagnose()`

**Content** (20-80 lines):
- Single topic per file. If you need a heading to separate concerns, you need two files.
- 20 lines minimum — below this, the neuron is too thin to justify its own file. Merge it into a related neuron.
- 80 lines maximum — above this, the neuron is trying to cover too much. Split it.

**## Related** (required):
- 2-4 links to other neurons that complete the thought
- Each link includes a reason ("why these fire together") — not just the filename
- Dead links (pointing to deleted files) are scored as failures by `neuraltree_score()`

**## Docs** (required):
- Links to source code, config files, or external docs that this neuron describes
- Keeps the neuron grounded in implementation — prevents drift between docs and reality

---

### Decision Rules

These rules govern every action the skill takes. They are non-negotiable.

#### 1. Cleanup Is a Side Effect, Not the Goal

NeuralTree's purpose is to improve **information flow** — the speed and accuracy of finding what you need. Deleting files, renaming directories, and reorganizing structures are tools in service of that goal, not the goal itself.

If the neural tree scores 0.95 but has a messy directory structure, **do not reorganize**. The flow is working. Reorganizing risks breaking links, invalidating caches, and confusing the user — all for cosmetic gain.

**Principle:** Measure flow first. Only intervene where flow is broken.

#### 2. Trace Before Prune

**NEVER recommend deleting, moving, or archiving a file without calling `neuraltree_trace(path)` first.**

`neuraltree_trace()` reveals:
- What other files reference this one (incoming links)
- What this file references (outgoing links)
- Whether Viking has it indexed
- Whether any _INDEX.md lists it

A file with zero incoming links might be orphaned — or it might be the only copy of critical knowledge that nothing has linked to yet. Trace tells you which.

**Rule:** If `neuraltree_trace()` shows ANY incoming references, the file is alive. Deletion requires either rewiring those references first or explicit user approval with full context.

#### 3. Show Both Sides

Every report the skill generates must show what was **KEPT** and what was **DELETED/CHANGED**, with proof for each decision.

Bad report:
```
Deleted 12 stale files. Flow score improved 0.72 → 0.78.
```

Good report:
```
KEPT (8 files):
  - memory/rules/build_rules.md — 3 incoming refs, verified 2 days ago
  - memory/active/phase2.md — active phase, 5 incoming refs
  ...

DELETED (4 files, pending user approval):
  - memory/old_notes.md — 0 incoming refs, last_verified 180 days ago, trace shows no connections
  - docs/draft_v1.md — superseded by docs/draft_v2.md, 0 incoming refs since v2 published
  ...

Flow score: 0.72 → 0.78 (projected)
```

The user must be able to verify every decision from the report alone.

#### 4. User Approves Destructive Actions

Two categories of actions:

**Auto-approved** (skill executes without asking):
- Wiring `## Related` links between existing files
- Adding files to Viking index
- Updating `_INDEX.md` entries
- Writing `.neuraltree/state.json`
- Creating sandbox worktrees for testing changes

**Requires user approval** (skill proposes, user confirms):
- Deleting any file
- Moving any file to a new location
- Renaming any file
- Archiving (moving to archive/)
- Splitting a file into multiple files
- Merging multiple files into one
- Any change to CLAUDE.md or MEMORY.md content (not just links)

**Presentation format for approval requests:**
```
PROPOSED: Delete memory/old_notes.md
REASON:   0 incoming refs, not verified in 180 days, content duplicated in memory/rules/build_rules.md
TRACE:    neuraltree_trace() shows no connections
IMPACT:   Flow score unchanged (file was unreachable anyway)
APPROVE?  [yes / no / show-trace]
```

The `[show-trace]` option lets the user see the full trace output before deciding.

---

## Section 3: Progress Protocol

> The user should never wonder "is it stuck?"

Every long-running operation must emit status messages so the user (and any observing agents) can track progress in real time. Silence breeds uncertainty — and uncertainty breeds cancellation.

### Status Messages

Emit a status message after each major step. The format is: `Phase {n}/{total}: {action}... {metric}`.

```
Phase 1/5: Scanning project... {total_count} files found
Phase 1/5: Generating test queries... {query_count} queries from {source_count} sources
Phase 2/5: Benchmarking... {completed}/{total} queries scored
Phase 2/5: Baseline Flow Score: {score} ({status})
Phase 3/5: Diagnosing... {failure_count} failures classified
Phase 4/5: AutoLoop iteration {n}/10... Flow Score {before} → {after}
Phase 4/5: AutoLoop converged — {kept} KEEP, {discarded} DISCARD, {held} HOLD
Phase 5/5: Enforcing rules, re-indexing Viking...
Complete: Flow Score {before} → {after} ({delta:+.2f})
```

**Rules:**
- **Every phase boundary gets a message.** No silent transitions.
- **Include counts and metrics.** "Scanning..." is bad. "Scanning... 847 files found" is good.
- **Show before/after on changes.** Flow Score deltas, iteration counts, kept/discarded tallies.
- **Use the `{status}` tag** to classify scores: `CRITICAL` (< 0.60), `DEGRADED` (0.60–0.79), `HEALTHY` (0.80–0.89), `EXCELLENT` (≥ 0.90).
- **Shorter modes emit fewer messages.** A `spot-check` emits 2-3 messages. A `bootstrap` emits all of them.

### Time Estimates

Before starting the pipeline, tell the user how long to expect based on the detected mode:

| Mode | Expected Duration |
|------|------------------|
| spot-check | ~30 seconds |
| health-check | ~1-3 minutes |
| maintenance | ~3-5 minutes |
| bootstrap/critical | ~8-15 minutes |

Emit the estimate in the activation status block (Section 1, Step 5):

```
║  ETA:         ~{duration}                     ║
```

If a phase takes significantly longer than expected (>2x the estimate), emit a warning:

```
WARNING: Phase 2/5 is taking longer than expected ({elapsed}s vs ~{expected}s estimate). Large project or slow Viking responses may be the cause.
```

### Subcommand Messages

Subcommands that skip phases should still indicate what was skipped:

```
/neuraltree audit — skipping AutoLoop and Enforce (read-only mode)
/neuraltree fix — skipping Benchmark (using last score: {score})
/neuraltree enforce — skipping Benchmark, Diagnose, and AutoLoop (enforce-only mode)
```

This ensures the user understands why the run is shorter than usual.

---

## Section 4: Benchmark Protocol

> Measure before you fix. The Flow Score is the single number that tells you whether information is flowing or stuck.

The Benchmark Protocol generates test queries, searches Viking for answers, judges relevance with LLM, computes structural metrics, and assembles a composite **Flow Score** (0.0–1.0). Every other section depends on this number.

### Step 1: Generate Queries

Generate test queries that probe the project's information structure. These queries simulate what an agent would actually ask during a working session.

```
scan_result = neuraltree_scan(project_root=".", include_contents=false)
index_paths = [f for f in scan_result["files"] if f["name"] == "_INDEX.md"]

result = neuraltree_generate_queries(
    claude_md_path="CLAUDE.md",
    memory_md_path="memory/MEMORY.md",
    index_paths=[p["path"] for p in index_paths],
    git_log_lines=100,
    indexed_doc_count=scan_result["total_files"]
)
queries = result["queries"]
```

Emit: `Phase 2/5: Generating test queries... {result["total"]} queries from {result["sources"]} sources`

**Spot-check mode filtering:** If mode is `spot-check`, load `.neuraltree/queries.json` and filter to only queries tagged `status: "critical"`. This reduces the benchmark to the most important probes — typically 5-10 queries instead of 30-50.

```
if mode == "spot-check":
    import json
    with open(".neuraltree/queries.json") as f:
        cached = json.load(f)
    queries = [q for q in cached if q.get("status") == "critical"]
```

### Step 2: Viking Search (Precision@3)

For each query, call Viking to retrieve the top 3 most relevant results. This tests whether the project's indexed content actually answers the questions an agent would ask.

```
for query in queries:
    viking_result = viking_search(query=query["text"], limit=3)
    query["viking_results"] = viking_result["results"]
```

Emit progress every 10 queries: `Phase 2/5: Benchmarking... {completed}/{total} queries scored`

**If `DEGRADED_MODE` is true:** Skip this entire step. Set `precision_at_3 = None`. Proceed directly to Step 4. Viking is unavailable — semantic search scoring is impossible.

### Step 3: LLM-as-Judge

For each Viking result from Step 2, judge whether the retrieved content is actually relevant to the query. This converts raw search results into a binary relevance signal.

**For each query, for each of its 3 Viking results, evaluate with this exact prompt:**

```
RELEVANCE JUDGMENT
Query: {query["text"]}
Result file: {result["uri"]}
Result content (first 50 lines): {result["content"][:50_lines]}

Rubric: Would reading this file help answer the query?
- YES if the file contains information directly useful for answering
- NO if the file is unrelated or only tangentially mentions the topic

Reply YES or NO only.
```

**Scoring rules:**
- `YES` → 1 point
- `NO` → 0 points
- Malformed response (anything other than exactly "YES" or "NO") → 0 points (conservative — assume irrelevant)

**Per-query score:** `query_precision = count(YES) / 3`

**Aggregate metric:** `precision_at_3 = mean(query_precision for all queries)`

This gives a float between 0.0 (Viking returns nothing useful) and 1.0 (every result for every query is relevant).

**Store per-query results** for later use by `neuraltree_diagnose()`:
```
for query in queries:
    query["precision"] = query_precision
    query["judgments"] = [
        {"uri": r["uri"], "relevant": judgment}
        for r, judgment in zip(query["viking_results"], judgments)
    ]
```

### Step 4: Structural Metrics

Call the MCP server to compute the structural health metrics. These measure the tree's wiring, freshness, and pressure — independent of Viking search quality.

```
score_result = neuraltree_score(project_root=".")
```

Returns:
- `metrics.hop_efficiency` (float, 0.0–1.0): fraction of files reachable in ≤2 hops
- `metrics.synapse_coverage` (float, 0.0–1.0): fraction of files with valid `## Related` links
- `metrics.dead_neuron_ratio` (float, 0.0–1.0): fraction of files with NO incoming references (inverted — higher = better, fewer dead neurons)
- `metrics.freshness` (float, 0.0–1.0): fraction of files verified within 90 days
- `metrics.trunk_pressure` (float, 0.0–1.0): trunk files under 100-line limit (higher = better, less pressure)
- `flow_score_partial` (float): weighted sum of structural metrics ONLY (precision_at_3 excluded — that's our job)
- `flow_score_weights`: the weight configuration used
- `details`: per-file breakdown for diagnostics
- `warnings`: any structural issues detected

**Note:** `score_result` returns `precision_at_3: null` — the MCP server cannot compute it because it requires Viking + LLM judgment. We computed it in Steps 2-3. This is **integration point #1** from the handoff.

### Step 5: Assemble Flow Score

Combine the structural metrics (from MCP) with the semantic metric (from Viking + LLM judge) into the composite Flow Score. This is **integration point #5** — two-phase scoring.

**Full mode (Viking available):**

```
Flow Score = (
    hop_efficiency     * 0.25 +
    precision_at_3     * 0.25 +
    synapse_coverage   * 0.20 +
    dead_neuron_ratio  * 0.15 +
    freshness          * 0.10 +
    trunk_pressure     * 0.05
)
```

The MCP server already computed the structural portion as `flow_score_partial`. The Skill adds the semantic portion:

```
final_flow_score = score_result["flow_score_partial"] + (precision_at_3 * 0.25)
```

**Weight rationale:**
- **hop_efficiency (0.25)** — the 0-1-2 hop rule is the fundamental guarantee. If files aren't reachable, nothing else matters.
- **precision_at_3 (0.25)** — retrieval quality. A perfectly structured tree that Viking can't search is half-blind.
- **synapse_coverage (0.20)** — wiring completeness. `## Related` links are the synapses that enable hop traversal.
- **dead_neuron_ratio (0.15)** — orphan detection. Files nobody references are invisible to the network.
- **freshness (0.10)** — staleness. Old unverified content degrades trust over time.
- **trunk_pressure (0.05)** — index bloat. Important but less critical than the structural and semantic metrics.

### Step 6: Record Baseline

Store the complete metric snapshot as the `baseline` for before/after comparison. This snapshot is used by the Diagnose and AutoLoop sections to measure improvement.

```
baseline = {
    "timestamp": now_iso8601(),
    "mode": mode,
    "flow_score": final_flow_score,
    "precision_at_3": precision_at_3,
    "structural": {
        "hop_efficiency": score_result["metrics"]["hop_efficiency"],
        "synapse_coverage": score_result["metrics"]["synapse_coverage"],
        "dead_neuron_ratio": score_result["metrics"]["dead_neuron_ratio"],
        "freshness": score_result["metrics"]["freshness"],
        "trunk_pressure": score_result["metrics"]["trunk_pressure"]
    },
    "flow_score_partial": score_result["flow_score_partial"],
    "query_count": len(queries),
    "queries": queries,  # includes per-query precision and judgments
    "warnings": score_result["warnings"]
}
```

Emit: `Phase 2/5: Baseline Flow Score: {final_flow_score:.2f} ({status})`

Where `{status}` is determined by:
| Flow Score | Status |
|------------|--------|
| >= 0.90 | `EXCELLENT` |
| 0.75–0.89 | `HEALTHY` |
| 0.60–0.74 | `DEGRADED` |
| < 0.60 | `CRITICAL` |

### Step 7: Route by Score

The Flow Score determines what happens next. Higher scores mean less intervention needed.

| Flow Score | Status | Next Step |
|------------|--------|-----------|
| > 0.90 | Excellent | **spot-check mode:** report metrics and stop — project is healthy. **Other modes:** continue to Diagnose for targeted improvements. |
| 0.75–0.90 | Healthy | Continue to Diagnose. The tree is working but has room for improvement. Focus on the lowest-scoring metrics. |
| 0.60–0.74 | Degraded | Continue to Diagnose. Multiple areas need attention. The tree is functional but information flow is impaired. |
| < 0.60 | Critical | Continue to Diagnose. Information flow is broken. Full intervention required — expect significant restructuring in AutoLoop. |

**Routing logic:**
```
if mode == "spot-check" and final_flow_score > 0.90:
    emit("Flow Score {score} — project is healthy. No intervention needed.")
    release_lock()
    stop()
elif mode == "spot-check" and final_flow_score <= 0.90:
    emit("WARNING: Flow Score dropped to {score} since last run. Upgrading to maintenance mode.")
    mode = "maintenance"
    # fall through to Diagnose
else:
    # all other modes: continue to Diagnose
    pass
```

**Proceed to Section 5 (Diagnose) with the `baseline` object and updated `mode`.**

---

### Degraded Mode (No Viking)

When Viking is unavailable (`DEGRADED_MODE = true`), the Benchmark Protocol operates in structure-only mode. This provides meaningful scoring but loses the semantic dimension.

**What changes:**
- **Steps 2-3 are skipped entirely.** No Viking search, no LLM-as-Judge, no precision_at_3.
- **precision_at_3 = None** — not zero, not estimated. Explicitly null.

**Degraded scoring formula:**

Without precision_at_3, the weights must be redistributed across structural metrics only:

```
structure_reachability = (hop_efficiency + synapse_coverage) / 2

Degraded Flow Score = (
    structure_reachability * 0.45 +
    dead_neuron_ratio      * 0.25 +
    freshness              * 0.20 +
    trunk_pressure         * 0.10
)
```

**Why these weights:**
- **structure_reachability (0.45)** — combines the two most important structural metrics. Without Viking, structural reachability is the primary signal.
- **dead_neuron_ratio (0.25)** — elevated from 0.15 because orphan files are harder to find without semantic search.
- **freshness (0.20)** — elevated from 0.10 because stale content is harder to detect without Viking verification.
- **trunk_pressure (0.10)** — elevated from 0.05 because trunk quality matters more when semantic search is unavailable.

**Degraded mode caps:** The degraded Flow Score is **capped at 0.75** — even a structurally perfect tree cannot score above HEALTHY without semantic verification. This prevents false confidence.

**User warning (emitted once at benchmark start):**
```
WARNING: Operating in DEGRADED mode — Viking unavailable.
Semantic search scoring disabled (precision_at_3 = null).
EMBEDDING_GAP detection disabled in Diagnose phase.
Flow Score capped at 0.75 (structure-only assessment).
Recommendation: Start Viking and re-run for full assessment.
```

**Baseline recording in degraded mode:** Same as Step 6, but `precision_at_3` is stored as `null` and `mode_degraded: true` is added to the baseline object.

---

## Section 5: Diagnose Protocol

> Failed queries are symptoms. Gap types are the diagnosis. The priority queue is the treatment plan.

The Diagnose Protocol takes every query that failed the benchmark, classifies WHY it failed, enriches the diagnosis with past lessons, and produces a priority queue ordered by fix cost. This is the bridge between "we know the score" (Section 4) and "we know what to do about it" (Section 6: AutoLoop).

### Step 1: Identify Failed Queries

A query "fails" if it meets either condition:

- **precision_at_3 < 0.67** — fewer than 2 of 3 Viking results were judged relevant by the LLM
- **The correct file was not in Viking's top 3 at all** — the expected source (from `query["source"]`) does not appear in any of the returned URIs

Collect all failed queries from the benchmark's `baseline.queries` list:

```
failed_queries = []
for query in baseline["queries"]:
    correct_file_found = any(
        query.get("source", "") in r["uri"]
        for r in query.get("viking_results", [])
    )
    if query.get("precision", 1.0) < 0.67 or not correct_file_found:
        failed_queries.append(query)
```

If `failed_queries` is empty, all queries passed — skip to Step 5 (emit healthy message) and proceed to Section 7 (Enforce).

### Step 2: Classify Failures

Call `neuraltree_diagnose` with the failed queries AND their Viking results. This is **integration point #2** from the handoff — the MCP server needs `viking_results` to distinguish EMBEDDING_GAP (content exists but Viking can't find it) from CONTENT_GAP (content doesn't exist at all).

```
viking_results_for_diagnose = []
for query in failed_queries:
    viking_results_for_diagnose.append({
        "query": query["text"],
        "results": [r["uri"] for r in query.get("viking_results", [])]
    })

diagnosis = neuraltree_diagnose(
    failed_queries=[
        {"text": q["text"], "expected_topic": q.get("source", "")}
        for q in failed_queries
    ],
    project_root=".",
    viking_results=viking_results_for_diagnose
)
```

The MCP server returns:
- `diagnoses` — per-query classification with `gap_type` and recommended fix
- `gap_counts` — tally per gap type (`{"SYNAPSE_GAP": 3, "EMBEDDING_GAP": 2, ...}`)
- `fix_priority` — server's initial ordering (overridden by Step 4)
- `total_failures` — count of diagnosed failures
- `warnings` — any issues during classification

**Gap types returned by `neuraltree_diagnose`:**

| Gap Type | Meaning | Example |
|----------|---------|---------|
| `SYNAPSE_GAP` | Files exist and are indexed, but lack `## Related` wiring between them | Query about "build rules" fails because `build_rules.md` doesn't link to `ci_config.md` |
| `FRESHNESS_GAP` | File exists but `last_verified` is stale (>90 days), degrading its score | Memory file from 6 months ago — content may be accurate but staleness penalizes it |
| `EMBEDDING_GAP` | File exists on disk but Viking hasn't indexed it, so semantic search misses it | New file added to `memory/` but never run through `openviking add-resource` |
| `FOCUS_GAP` | File is too large (>80 lines) — Viking indexes it but the relevant section is diluted | A 200-line file where the answer is on line 150 — Viking returns the file but the match quality is low |
| `CONTENT_GAP` | No file exists that answers this query — new content must be created | Query about a topic that was discussed verbally but never documented |

### Step 3: Enrich with Lessons

Check whether past autoloop sessions encountered similar failures. Lessons from previous runs can inform strategy — a recurring EMBEDDING_GAP on the same directory suggests a systematic indexing issue, not a one-off miss.

```
symptoms = [d["query"] + " " + d["gap_type"] for d in diagnosis["diagnoses"]]

lesson_matches = neuraltree_lesson_match(
    symptoms=symptoms,
    project_root="."
)
```

**Enrichment rules:**
- If a lesson match has `score > 0.5`, attach it to the corresponding diagnosis entry as `prior_lesson`
- Past lessons **inform** the fix strategy but **do not override** the autoloop's decisions — the autoloop may find a better solution than what worked last time
- If `lesson_matches["total_matches"] == 0`, no prior lessons exist — this is expected on first run

```
for i, diag in enumerate(diagnosis["diagnoses"]):
    matching_lessons = [
        m for m in lesson_matches.get("matches", [])
        if m["score"] > 0.5 and m["symptom_index"] == i
    ]
    if matching_lessons:
        diag["prior_lesson"] = matching_lessons[0]  # best match
```

### Step 4: Build Priority Queue

Sort diagnosed failures by **fix cost**, cheapest first. Cheap fixes are applied first because they have the highest ROI — small effort, immediate score improvement.

**Priority order (cheapest → most expensive):**

| Priority | Gap Type | Fix Cost | What the AutoLoop Does |
|----------|----------|----------|----------------------|
| 1 | `SYNAPSE_GAP` | ~5 seconds | Add `## Related` links between existing files. No content creation, no re-indexing. |
| 2 | `FRESHNESS_GAP` | ~10 seconds | Update `last_verified` date after confirming content is still accurate. |
| 3 | `EMBEDDING_GAP` | ~30 seconds | Re-index the file in Viking via `openviking add-resource`. File already exists. |
| 4 | `FOCUS_GAP` | ~2 minutes | Split large file into focused neurons. Requires creating new files + updating references. |
| 5 | `CONTENT_GAP` | ~5 minutes | Create entirely new content. Most expensive — requires writing, wiring, and indexing. |

```
PRIORITY_ORDER = {
    "SYNAPSE_GAP": 1,
    "FRESHNESS_GAP": 2,
    "EMBEDDING_GAP": 3,
    "FOCUS_GAP": 4,
    "CONTENT_GAP": 5,
}

priority_queue = sorted(
    diagnosis["diagnoses"],
    key=lambda d: PRIORITY_ORDER.get(d["gap_type"], 99)
)
```

**Within the same gap type**, sort by the query's precision score (lowest first — worst failures get fixed first):

```
priority_queue = sorted(
    diagnosis["diagnoses"],
    key=lambda d: (PRIORITY_ORDER.get(d["gap_type"], 99), d.get("precision", 0.0))
)
```

### Step 5: Emit Diagnosis Summary

Emit a structured status message summarizing the diagnosis results.

**When failures exist:**

```
gap_counts = diagnosis["gap_counts"]
emit(
    f"Phase 3/5: Diagnosed {diagnosis['total_failures']} failures: "
    f"{gap_counts.get('SYNAPSE_GAP', 0)} SYNAPSE, "
    f"{gap_counts.get('EMBEDDING_GAP', 0)} EMBEDDING, "
    f"{gap_counts.get('FRESHNESS_GAP', 0)} FRESHNESS, "
    f"{gap_counts.get('FOCUS_GAP', 0)} FOCUS, "
    f"{gap_counts.get('CONTENT_GAP', 0)} CONTENT"
)
emit(f"Priority queue: {len(priority_queue)} fixes ordered by cost (cheapest first)")
```

If lessons were matched:
```
lesson_count = sum(1 for d in priority_queue if d.get("prior_lesson"))
if lesson_count > 0:
    emit(f"Lessons: {lesson_count} prior lessons matched (informing fix strategy)")
```

**When no failures exist:**

```
emit("Phase 3/5: All queries passing. Tree is healthy.")
```

Skip Sections 5 Step 4 priority queue and proceed directly to **Section 7 (Enforce)** — there are no failures to fix, so the AutoLoop (Section 6) is unnecessary.

**Proceed to Section 6 (AutoLoop) with the `priority_queue`, `diagnosis`, and updated `baseline`.**
