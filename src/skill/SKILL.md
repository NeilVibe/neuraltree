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

## Helper Functions Reference

These are operations the agent performs directly (not MCP tools). When executing the skill, use your native capabilities for these:

| Function | What To Do |
|----------|-----------|
| `read_file(path)` | Read file contents. Use your file reading capability. |
| `write_file(path, content)` | Write content to file. Use your file writing capability. |
| `apply_suggested_content(file, content)` | Append `content` to end of `file` (the `## Related` + `## Docs` block from `neuraltree_wire`). If those sections already exist, replace them. |
| `update_frontmatter(file, fields)` | Parse YAML frontmatter in `file`, update the given fields, write back. Preserve all other frontmatter fields unchanged. |
| `viking_add_resource(uri, content)` | Call Viking MCP: `viking_add_resource(uri=uri)` to re-index a file in the semantic search database. |
| `llm_judge_precision(query)` | Re-run the Section 4 Step 3 LLM-as-Judge prompt for one query against its `viking_results`. Return precision as float (0.0-1.0). |
| `execute_pending_action(action, project_root)` | Execute one approved action — see Section 8 inline logic for DELETE/ARCHIVE/CREATE handling. |
| `update_state_and_history(flow_score)` | Write updated `state.json` + append to `history/`. Same logic as Section 7 Steps 1d-1e. |
| `read_calibration_accuracy(path)` | Read `.neuraltree/calibration.json`, return `accuracy` field (default 0.5 if file missing or field absent). |
| `now_iso8601()` | Current datetime in ISO 8601 format, e.g. `2026-04-05T14:30:00Z`. |
| `today_iso8601()` | Current date in ISO 8601 format, e.g. `2026-04-05`. |
| `now()` | Current datetime object (for arithmetic like computing deltas). |
| `parse_iso(timestamp)` | Parse an ISO 8601 timestamp string into a datetime object. |
| `summarize_fixes(kept_list)` | Count fix types from the kept list: e.g. `["wire: 2", "index: 1"]`. Groups by `gap_type` and counts occurrences. |
| `is_knowledge_file(path)` | True if file is `.md` and lives in `memory/`, `docs/`, or has YAML frontmatter. Config files, source code, and binaries return False. |
| `git_log_modified_files(since)` | Run `git log --name-only --since={since}` and return deduplicated list of modified file paths. |
| `describe_action(kept_entry)` | Generate a human-readable description of a kept action, e.g. "added ## Related (3 synapses)" or "re-indexed in Viking". |
| `wait_for_user_input()` | Pause execution and return control to the user. Wait for their response. Return the response as a string. |
| `release_lock()` | Delete `.neuraltree/.lock`. If it doesn't exist, silently succeed (already released). |
| `timedelta(days=N)` | A time duration of N days. Use for date arithmetic (e.g., `now() - timedelta(days=7)`). |

> **Note:** Code blocks in this skill use Python-like pseudocode for clarity. Functions like `os.path.exists()`, `json.load()`, `shutil.rmtree()` indicate the operation to perform, not literal Python imports. Use your platform's equivalent file operations.

---

## Section 1: Activation

When `/neuraltree` is invoked, execute these five steps in order. Do NOT skip steps. Do NOT proceed past a failed step unless explicitly noted.

### Step 1: Verify Tools

Both tool backends must be reachable before any work begins.

1. **neuraltree-mcp** — call `neuraltree_scan(path=".", max_files=10000)`.
   - If it returns a file inventory: **PASS**. Record the `total_count` count.
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

```
state = {}  # default for first run (no state.json)
if os.path.exists(".neuraltree/state.json"):
    state = json.load(open(".neuraltree/state.json"))
```

**If `.neuraltree/state.json` does not exist** (`state` is empty) — this is a first run. Mode = `bootstrap`.

**If it exists** — parse these fields:
- `flow_score` (float, 0.0–1.0): last computed Flow Score
- `last_run` (ISO 8601 timestamp): when the skill last completed a full run
- `calibration_accuracy` (float): prediction model accuracy

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

**After acquiring lock, clean previous run's backup and initialize timing:**

```
# Clean previous run's backup (retained for post-session rollback, now safe to delete)
prev_backup = ".neuraltree/.tmp/backup"
if os.path.exists(prev_backup):
    shutil.rmtree(prev_backup)

# Start timer for duration tracking
run_start_time = now()

# Derive project name from current directory
project_name = os.path.basename(os.path.abspath("."))
```

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

**`/neuraltree enforce` initialization:** Since `enforce` jumps directly to Section 7, variables that normally accumulate through earlier sections must be initialized from the last run's state:

```
# For enforce-only: load state from last run, initialize empty autoloop
if not os.path.exists(".neuraltree/state.json"):
    emit "Cannot run /neuraltree enforce without a previous run. Run /neuraltree first."
    release_lock()
    stop
state = json.load(open(".neuraltree/state.json"))
baseline = {"flow_score": state["flow_score"], "metrics": state.get("metrics", {})}
autoloop_state = {"iteration": 0, "max_iterations": 10, "score_history": [state["flow_score"]], "attempted": set(), "kept": [], "discarded": [], "held": [], "convergence_counter": 0}
latest_metrics = dict(baseline.get("metrics", {}))
current_flow_score = state["flow_score"]
exit_reason = "enforce_only"
precision_at_3 = state.get("metrics", {}).get("precision_at_3")
```

**`/neuraltree fix` baseline recovery:** Since `fix` skips benchmarking, the `baseline` object must be reconstructed from the last run:

```
# Load baseline from last run
import json
state_path = ".neuraltree/state.json"
queries_path = ".neuraltree/queries.json"

if not os.path.exists(state_path):
    emit("Cannot run /neuraltree fix without a previous benchmark. Run /neuraltree benchmark first.")
    release_lock()
    stop()

with open(state_path) as f:
    state = json.load(f)
with open(queries_path) as f:
    loaded_queries = json.load(f)

baseline = {
    "flow_score": state["flow_score"],
    "metrics": {
        "hop_efficiency": state.get("metrics", {}).get("hop_efficiency", 0.0),
        "synapse_coverage": state.get("metrics", {}).get("synapse_coverage", 0.0),
        "dead_neuron_ratio": state.get("metrics", {}).get("dead_neuron_ratio", 0.0),
        "freshness": state.get("metrics", {}).get("freshness", 0.0),
        "trunk_pressure": state.get("metrics", {}).get("trunk_pressure", 0.0),
        "precision_at_3": state.get("metrics", {}).get("precision_at_3")
    },
    "queries": loaded_queries
}
```

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
- `last_verified` — staleness detection. Files not verified in 30+ days get flagged by `neuraltree_diagnose()`

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
- **Use the `{status}` tag** to classify scores: `CRITICAL` (< 0.60), `DEGRADED` (0.60–0.74), `HEALTHY` (0.75–0.89), `EXCELLENT` (≥ 0.90).
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

### Subcommand Phase Adjustment

When a subcommand skips phases, adjust the denominator:
- `/neuraltree audit`: Phase 1/2 (Scan), Phase 2/2 (Benchmark)
- `/neuraltree fix`: Phase 1/3 (Diagnose), Phase 2/3 (AutoLoop), Phase 3/3 (Enforce)
- `/neuraltree enforce`: Phase 1/1 (Enforce)
- `/neuraltree benchmark`: Phase 1/2 (Scan), Phase 2/2 (Benchmark)
- `/neuraltree auto` and default: Phase N/5 (full pipeline)

---

## Section 4: Benchmark Protocol

> Measure before you fix. The Flow Score is the single number that tells you whether information is flowing or stuck.

The Benchmark Protocol generates test queries, searches Viking for answers, judges relevance with LLM, computes structural metrics, and assembles a composite **Flow Score** (0.0–1.0). Every other section depends on this number.

### Step 1: Generate Queries

Generate test queries that probe the project's information structure. These queries simulate what an agent would actually ask during a working session.

```
scan_result = neuraltree_scan(path=".", max_files=10000)
index_paths = [f for f in scan_result["files"] if os.path.basename(f) == "_INDEX.md"]

result = neuraltree_generate_queries(
    project_root=".",
    claude_md_path="CLAUDE.md",
    memory_md_path="memory/MEMORY.md",
    index_paths=index_paths,
    git_log_lines=100,
    indexed_doc_count=scan_result["total_count"]
)
queries = result["queries"]
```

Emit: `Phase 2/5: Generating test queries... {result["total"]} queries from {result["sources"]} sources`

**Spot-check mode filtering:** If mode is `spot-check`, load `.neuraltree/queries.json` and filter to only queries tagged `status: "critical"`. This reduces the benchmark to the most important probes — typically 5-10 queries instead of 30-50.

```
if mode == "spot-check":
    if os.path.exists(".neuraltree/queries.json"):
        import json
        with open(".neuraltree/queries.json") as f:
            cached = json.load(f)
        queries = [q for q in cached if q.get("status") == "critical"]
    else:
        # Fall through to full query generation
        emit("queries.json not found — running full benchmark instead of spot-check")
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
- `metrics.freshness` (float, 0.0–1.0): fraction of files verified within 30 days
- `metrics.trunk_pressure` (float, 0.0–1.0): trunk files under 100-line limit (higher = better, less pressure)
- `flow_score_partial` (float): weighted sum of structural metrics ONLY (precision_at_3 excluded — that's our job)
- `flow_score_weights`: the weight configuration used
- `details`: per-file breakdown for diagnostics
- `warnings`: any structural issues detected

**Note:** `score_result` returns `precision_at_3: null` — the MCP server cannot compute it because it requires Viking + LLM judgment. We computed it in Steps 2-3.

### Step 5: Assemble Flow Score

Combine the structural metrics (from MCP) with the semantic metric (from Viking + LLM judge) into the composite Flow Score.

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
    "metrics": {
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
    # Emit spot-check short form report (Section 8)
    days_since = (now() - parse_iso(state.get("last_run", now_iso8601()))).days
    next_date = (now() + timedelta(days=7)).strftime("%Y-%m-%d")
    emit(f"NeuralTree spot-check — {project_name}")
    emit(f"Score: {final_flow_score:.2f} (Excellent) | {len(queries)} queries | 0 failures")
    emit(f"Last full run: {days_since} days ago | Next: {next_date}")
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
structure_reachability = (score_result["metrics"]["hop_efficiency"] + score_result["metrics"]["synapse_coverage"]) / 2

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

Call `neuraltree_diagnose` with the failed queries AND their Viking results. The MCP server needs `viking_results` to distinguish EMBEDDING_GAP (content exists but Viking can't find it) from CONTENT_GAP (content doesn't exist at all).

**DEGRADED_MODE note:** In DEGRADED_MODE, `viking_results_for_diagnose` will be empty lists (no Viking results available). All EMBEDDING_GAP results will be reclassified to SYNAPSE_GAP after diagnosis (see Section 9).

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

# In DEGRADED_MODE, reclassify EMBEDDING_GAP → SYNAPSE_GAP
if DEGRADED_MODE:
    for d in diagnosis["diagnoses"]:
        if d["gap_type"] == "EMBEDDING_GAP":
            d["gap_type"] = "SYNAPSE_GAP"
    diagnosis["gap_counts"]["SYNAPSE_GAP"] = diagnosis["gap_counts"].get("SYNAPSE_GAP", 0) + diagnosis["gap_counts"].get("EMBEDDING_GAP", 0)
    diagnosis["gap_counts"]["EMBEDDING_GAP"] = 0
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
| `FRESHNESS_GAP` | File exists but `last_verified` is stale (>30 days), degrading its score | Memory file from 6 months ago — content may be accurate but staleness penalizes it |
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
    if i < len(lesson_matches.get("matches", [])):
        symptom_result = lesson_matches["matches"][i]
        top_lessons = [l for l in symptom_result["lessons"] if l["score"] > 0.5]
        if top_lessons:
            diag["prior_lesson"] = top_lessons[0]  # best match
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

# Derive target_file from matching_files for all downstream references
for d in diagnosis["diagnoses"]:
    d["target_file"] = d["matching_files"][0] if d.get("matching_files") else None

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

### Step 4b: Parallel Investigation (Complex Audits Only)

For projects with > 100 diagnosed failures or when multiple directories need auditing:

1. Spawn 3-5 investigation agents in parallel, each assigned a subset of failures
2. Each agent: calls `neuraltree_trace()` on its targets, reports keep/archive/delete recommendation with proof
3. Skill synthesizes findings into unified report
4. User approves before any destructive action

For typical runs (< 100 failures): skip this step, proceed to AutoLoop.

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

# Initialize autoloop_state with defaults (in case Section 6 is skipped)
autoloop_state = {
    "iteration": 0, "max_iterations": 10,
    "score_history": [baseline["flow_score"]],
    "attempted": set(), "kept": [], "discarded": [], "held": [],
    "convergence_counter": 0
}
latest_metrics = dict(baseline["metrics"])
current_flow_score = baseline["flow_score"]
exit_reason = "no_failures"
```

Skip Sections 5 Step 4 priority queue and proceed directly to **Section 7 (Enforce)** — there are no failures to fix, so the AutoLoop (Section 6) is unnecessary.

**Routing after Step 5:**

```
if len(priority_queue) > 0:
    # Failures exist — proceed to AutoLoop to fix them
    Proceed to Section 6 (AutoLoop) with the priority_queue, diagnosis, and updated baseline.
else:
    # No failures — already routed to Section 7 above
    pass
```

---

## Section 6: Karpathy AutoLoop

> Predict. Backup. Execute. Measure. Decide. Learn. Repeat until the tree is healthy or you've proven it can't be improved further.

Inspired by Karpathy's autoresearch methodology: for each diagnosed failure, predict the impact of a fix, try it, measure the actual result, and make a data-driven decision. No guessing, no hoping — every change earns its place through measurement.

### Exit Conditions

Check these **after every iteration**, not just at the end. The loop terminates the moment ANY condition is met:

1. **Healthy:** `flow_score > 0.85` — the tree is healthy enough. Stop improving.
2. **Converged:** 3 consecutive iterations where `|delta| < 0.02` — changes aren't moving the needle anymore. Oscillation damping.
3. **Hard cap:** 10 iterations reached — prevent runaway loops regardless of score.
4. **Exhausted:** All failures in the priority queue have been addressed or skipped via dedup guard.

### Sandbox Mode (Optional)

For first runs on unknown projects or when flow_score < 0.60 (critical mode):
- Consider using sandbox for maximum safety:
  1. neuraltree_sandbox_create() → isolated copy
  2. Run AutoLoop on sandbox copy
  3. neuraltree_sandbox_diff() → review changes
  4. User approves → neuraltree_sandbox_apply()
  5. neuraltree_sandbox_destroy() → cleanup

For health-check and maintenance modes: sandbox is optional (backup/restore provides sufficient safety).

Note: The current AutoLoop operates directly on project files with backup/restore as the safety net.
Sandbox integration provides stronger isolation but adds complexity. Use when risk is high.

### Initialize

Before entering the loop, set up the tracking state:

```
# Variables carried from previous sections (must remain in scope):
# - baseline: from Section 4, Step 6 (metric snapshot)
# - diagnosis: from Section 5, Step 2 (failure classifications)
# - priority_queue: from Section 5, Step 4 (ordered failures)
# - scan_result: from Section 4, Step 1 (filesystem inventory)
# - autoloop_state: initialized in Section 5, Step 5
# - latest_metrics: initialized below
# - current_flow_score: initialized below

autoloop_state = {
    "iteration": 0,
    "max_iterations": 10,
    "score_history": [baseline["flow_score"]],
    "attempted": set(),       # {(gap_type, target)} tuples for dedup
    "kept": [],               # list of successful changes
    "discarded": [],          # list of rolled-back changes
    "held": [],               # list of changes kept but flagged for review
    "convergence_counter": 0  # consecutive iterations with |delta| < 0.02
}

latest_metrics = dict(baseline["metrics"])  # copy baseline metrics as starting point
current_flow_score = baseline["flow_score"]
```

### Per-Iteration Steps

For each failure in `priority_queue`, execute these 9 steps in order. Each step depends on the previous one — no parallelization within an iteration.

#### Step 1: Dedup Guard

Before attempting any fix, check whether this exact (gap_type, target) combination has already been tried. This prevents wasting iterations on the same failure when the fix didn't work or the failure is a duplicate.

```
dedup_key = (failure["gap_type"], failure.get("target_file", failure.get("query", "")))

if dedup_key in autoloop_state["attempted"]:
    # Already tried this exact fix — skip to next failure in queue
    continue

autoloop_state["attempted"].add(dedup_key)
```

**Why dedup matters:** Without this guard, the loop can waste iterations re-attempting fixes that already failed. A SYNAPSE_GAP between files A and B is the same gap whether it appears in query 1 or query 7 — fix it once, measure once.

#### Step 2: Predict

Before making any change, ask the prediction engine what it expects will happen. This creates the baseline for the KEEP/HOLD/DISCARD decision in Step 6.

Map the gap type to the proposed action:

```
ACTION_MAP = {
    "SYNAPSE_GAP":   "wire",
    "FRESHNESS_GAP": "update_freshness",
    "EMBEDDING_GAP": "index",
    "FOCUS_GAP":     "split",
    "CONTENT_GAP":   "wire",  # create file + wire (content provided by user)
}

proposed_action = ACTION_MAP[failure["gap_type"]]
```

Call the prediction tool:

```
prediction = neuraltree_predict(
    current_metrics={
        "flow_score": current_flow_score,
        "hop_efficiency": latest_metrics["hop_efficiency"],
        "synapse_coverage": latest_metrics["synapse_coverage"],
        "dead_neuron_ratio": latest_metrics["dead_neuron_ratio"],
        "freshness": latest_metrics["freshness"],
        "trunk_pressure": latest_metrics["trunk_pressure"],
        "precision_at_3": latest_metrics.get("precision_at_3")
    },
    proposed_changes=[{
        "action": proposed_action,
        "target": failure.get("target_file", failure.get("query", "")),
        "gap_type": failure["gap_type"]
    }],
    project_root="."
)

predicted_delta = prediction["predicted_delta"]
```

Emit: `Phase 4/5: AutoLoop iteration {n}/10 — predicting impact of {proposed_action} on {target}...`

**If `predicted_delta < 0.001`:** The prediction engine expects no measurable improvement. Log and skip to the next failure:

```
if predicted_delta < 0.001:
    emit(f"  Predicted delta {predicted_delta:.4f} — too small, skipping")
    continue
```

#### Step 3: Backup

Before touching any file, create a restorable backup. This is the safety net that makes DISCARD possible.

**Skip backup for gap types that don't modify files in this step.** CONTENT_GAP and FOCUS_GAP both `continue` before any file is written (Step 4), so backing up `None` or a placeholder path would crash. Guard before calling:

```
# CONTENT_GAP and FOCUS_GAP skip Step 4 via continue — no file is modified, no backup needed
if failure["gap_type"] in ("CONTENT_GAP", "FOCUS_GAP"):
    # Will be routed to HOLD in Step 4 without touching any file — skip backup
    pass
elif failure.get("target_file") is None:
    # No target file resolved (e.g. CONTENT_GAP with no matching_files) — skip
    pass
else:
    backup_result = neuraltree_backup(
        files=[failure["target_file"]],
        project_root="."
    )
```

**Important:** The backup captures the exact file state before the fix. If the fix makes things worse, Step 6 can restore to this exact state. Without backup, DISCARD would be impossible and every change would be permanent.

#### Step 4: Execute the Fix

Apply the fix based on the gap type. Each gap type has a specific execution strategy:

**SYNAPSE_GAP — Wire missing `## Related` links:**

```
wire_result = neuraltree_wire(
    file_path=failure["target_file"],
    all_leaf_paths=scan_result["files"],
    project_root="."
)

# Apply the suggested wiring content
# neuraltree_wire() returns suggested_content with ## Related links
# Write the updated content to the file
apply_suggested_content(failure["target_file"], wire_result["suggested_content"])
```

**FRESHNESS_GAP — Update `last_verified` in frontmatter:**

```
# Read the file, parse frontmatter, update last_verified to today
update_frontmatter(failure["target_file"], {"last_verified": today_iso8601()})
```

Only update `last_verified` if the content has been verified as still accurate. The autoloop confirms accuracy by checking:
- The file's `## Related` links are not dead
- The file's `## Docs` references still exist
- The content doesn't contradict current project state (checked via Viking search)

If verification fails, skip this fix and flag for manual review.

**EMBEDDING_GAP — Add to Viking index:**

```
# In DEGRADED_MODE, EMBEDDING_GAP was reclassified to SYNAPSE_GAP in Section 5.
# This block should not be reached in DEGRADED_MODE. Guard defensively:
if DEGRADED_MODE:
    continue  # Skip — Viking unavailable, cannot re-index

viking_add_resource(
    uri=failure["target_file"],
    content=read_file(failure["target_file"])
)
```

**FOCUS_GAP — Route to HOLD for user review:**

FOCUS_GAP splits are complex operations that require user judgment on section boundaries. The autoloop does NOT auto-split files.

```
# FOCUS_GAP: Route to HOLD — do not auto-split
autoloop_state["held"].append({
    "failure": failure,
    "gap_type": "FOCUS_GAP",
    "target": failure["target_file"],
    "reason": "FOCUS_GAP splits require user judgment on section boundaries",
    "suggested_action": f"Split {failure['target_file']} into focused leaves"
})
continue  # Skip to next failure — do not auto-split
```

**CONTENT_GAP — Flag as PENDING ACTION:**

Content gaps cannot be auto-fixed because they require new knowledge that doesn't exist in the project yet. The autoloop does NOT auto-generate content — that would produce hallucinated documentation.

```
emit(f"  CONTENT_GAP: {failure['query']} — requires new content")
emit(f"  PENDING ACTION: User must provide content for this topic")
emit(f"  Suggested file: {failure.get('suggested_path', 'TBD')}")

# Record as HOLD — the gap is real but the fix requires human input
autoloop_state["held"].append({
    "gap_type": "CONTENT_GAP",
    "query": failure["query"],
    "reason": "Content does not exist — user must provide",
    "suggested_path": failure.get("suggested_path", "TBD")
})
continue  # Skip to next failure — no measurement needed
```

#### Step 5: Measure

After applying the fix, re-measure everything. No assumptions about improvement — prove it with numbers.

**5a. Re-run structural scoring:**

```
new_score_result = neuraltree_score(project_root=".")
```

**5b. Re-run Viking search for affected queries:**

```
# In DEGRADED_MODE, skip Viking re-search. Re-score using structural metrics only.
if not DEGRADED_MODE:
    affected_queries = [
        q for q in baseline["queries"]
        if failure["target_file"] in q.get("source", "")
        or failure["target_file"] in str(q.get("viking_results", []))
    ]

    for query in affected_queries:
        viking_result = viking_search(query=query["text"], limit=3)
        query["viking_results"] = viking_result["results"]
        # Re-run LLM judge on new results
        query["precision"] = llm_judge_precision(query)
```

**5c. Recompute precision_at_3:**

```
if DEGRADED_MODE:
    new_precision_at_3 = None
else:
    values = [q["precision"] for q in baseline["queries"] if q.get("precision") is not None]
    new_precision_at_3 = mean(values) if values else 0.0  # fallback for empty
```

**5d. Assemble new Flow Score:**

```
if DEGRADED_MODE:
    # Use degraded formula — no semantic scoring available
    sr = (new_score_result["metrics"]["hop_efficiency"] + new_score_result["metrics"]["synapse_coverage"]) / 2
    new_flow_score = min(0.75,
        sr * 0.45 +
        new_score_result["metrics"]["dead_neuron_ratio"] * 0.25 +
        new_score_result["metrics"]["freshness"] * 0.20 +
        new_score_result["metrics"]["trunk_pressure"] * 0.10
    )
else:
    new_flow_score = new_score_result["flow_score_partial"] + (new_precision_at_3 * 0.25)
actual_delta = new_flow_score - current_flow_score
```

Emit: `Phase 4/5: AutoLoop iteration {n}/10 — Flow Score {current_flow_score:.3f} → {new_flow_score:.3f} ({actual_delta:+.3f})`

#### Step 6: Decide — KEEP / HOLD / DISCARD

Compare the actual improvement against the prediction. The ratio determines the decision:

```
ratio = actual_delta / max(abs(predicted_delta), 0.001)
```

**KEEP** — `ratio >= 0.8`:

The fix delivered at least 80% of the predicted improvement. Commit the change.

```
if ratio >= 0.8:
    current_flow_score = new_flow_score
    latest_metrics = new_score_result["metrics"]
    latest_metrics["precision_at_3"] = new_precision_at_3
    autoloop_state["kept"].append({
        "gap_type": failure["gap_type"],
        "target": failure.get("target_file", ""),
        "predicted_delta": predicted_delta,
        "actual_delta": actual_delta,
        "ratio": ratio
    })
    emit(f"  KEEP — ratio {ratio:.2f} (predicted {predicted_delta:+.3f}, actual {actual_delta:+.3f})")
```

**HOLD** — `0.5 <= ratio < 0.8`:

The fix helped but underperformed predictions. Keep the change in place but flag it for user review.

```
elif 0.5 <= ratio < 0.8:
    current_flow_score = new_flow_score
    latest_metrics = new_score_result["metrics"]
    latest_metrics["precision_at_3"] = new_precision_at_3
    autoloop_state["held"].append({
        "gap_type": failure["gap_type"],
        "target": failure.get("target_file", ""),
        "predicted_delta": predicted_delta,
        "actual_delta": actual_delta,
        "ratio": ratio,
        "reason": "Underperformed prediction — review recommended"
    })
    emit(f"  HOLD — ratio {ratio:.2f} (predicted {predicted_delta:+.3f}, actual {actual_delta:+.3f})")
```

**DISCARD** — `ratio < 0.5`:

The fix failed to deliver meaningful improvement — or made things worse. Roll back to the backup.

```
else:
    if actual_delta < 0:
        emit(f"  WARNING: Fix caused regression (score decreased by {abs(actual_delta):.3f}). Rolling back.")
    restore_result = neuraltree_restore(
        files=[failure["target_file"]],
        project_root="."
    )
    if restore_result.get("not_found"):
        emit(f"WARNING: Could not restore {failure['target_file']} — backup not found. File may be in modified state.")
    autoloop_state["discarded"].append({
        "gap_type": failure["gap_type"],
        "target": failure.get("target_file", ""),
        "predicted_delta": predicted_delta,
        "actual_delta": actual_delta,
        "ratio": ratio
    })
    emit(f"  DISCARD — ratio {ratio:.2f} (predicted {predicted_delta:+.3f}, actual {actual_delta:+.3f}), restored from backup")
```

#### Step 7: Update Calibration

After every decision, feed the prediction/actual pair back to the calibration system. This makes future predictions more accurate.

```
neuraltree_update_calibration(
    predicted_delta=predicted_delta,
    actual_delta=actual_delta,
    project_root="."
)
```

The calibration system tracks prediction accuracy over time. Early predictions may be wildly off — that's expected. By iteration 5-6, the system should be calibrating within 20% of actual results. If calibration accuracy remains below 50% after 10+ runs across sessions, the prediction model needs retraining (recorded as a lesson).

#### Step 8: Record Lesson

Every KEEP and DISCARD generates a lesson for future autoloop sessions. HOLD does not generate a lesson — the outcome is ambiguous.

**On KEEP — record what worked:**

```
neuraltree_lesson_add(
    domain=failure["gap_type"].lower(),
    lesson={
        "symptom": f"{failure['gap_type']} on {failure.get('target_file', 'unknown')}",
        "root_cause": f"{failure['gap_type']} — predicted {predicted_delta:+.3f}, actual {actual_delta:+.3f} (ratio {ratio:.2f})",
        "fix": f"KEEP: {proposed_action}. Score improved {current_flow_score - actual_delta:.3f} → {current_flow_score:.3f}.",
        "key_file": failure.get("target_file", "unknown")
    },
    project_root="."
)
```

**On DISCARD — record what didn't work:**

```
neuraltree_lesson_add(
    domain=failure["gap_type"].lower(),
    lesson={
        "symptom": f"{failure['gap_type']} on {failure.get('target_file', 'unknown')}",
        "root_cause": f"{failure['gap_type']} — predicted {predicted_delta:+.3f}, actual {actual_delta:+.3f} (ratio {ratio:.2f})",
        "fix": f"DISCARD: {proposed_action}. Fix rolled back. Target may resist automated {proposed_action} — consider manual intervention.",
        "key_file": failure.get("target_file", "unknown")
    },
    project_root="."
)
```

Lessons are recorded after autoloop KEEP/HOLD/DISCARD decisions. Future runs use `neuraltree_lesson_match()` (Section 5, Step 3) to check whether a similar fix has been tried before and what happened.

#### Step 9: Check Exit Conditions

After every iteration, check all four exit conditions. The order matters — check the most desirable outcome first.

```
autoloop_state["iteration"] += 1
autoloop_state["score_history"].append(current_flow_score)

# --- Convergence detection ---
if len(autoloop_state["score_history"]) >= 2:
    delta = abs(autoloop_state["score_history"][-1] - autoloop_state["score_history"][-2])
    if delta < 0.02:
        autoloop_state["convergence_counter"] += 1
    else:
        autoloop_state["convergence_counter"] = 0

# --- Oscillation detection ---
# Check for alternating up/down/up pattern in last 4 scores
oscillating = False
if len(autoloop_state["score_history"]) >= 4:
    recent = autoloop_state["score_history"][-4:]
    deltas = [recent[i+1] - recent[i] for i in range(3)]
    # Oscillation: signs alternate (positive, negative, positive or vice versa)
    if (deltas[0] > 0 and deltas[1] < 0 and deltas[2] > 0) or \
       (deltas[0] < 0 and deltas[1] > 0 and deltas[2] < 0):
        oscillating = True

# --- Check exit conditions ---
exit_reason = None

# 1. Healthy
if current_flow_score > 0.85:
    exit_reason = f"Flow Score {current_flow_score:.3f} > 0.85 — tree is healthy"

# 2. Converged (includes oscillation damping)
elif autoloop_state["convergence_counter"] >= 3:
    exit_reason = f"Converged — 3 consecutive iterations with |delta| < 0.02"
elif oscillating:
    exit_reason = f"Oscillation detected — score alternating without net improvement"

# 3. Hard cap
elif autoloop_state["iteration"] >= autoloop_state["max_iterations"]:
    exit_reason = f"Hard cap — {autoloop_state['max_iterations']} iterations reached"

# 4. Exhausted
elif all(
    (d["gap_type"], d.get("target_file", d.get("query", ""))) in autoloop_state["attempted"]
    for d in priority_queue
):
    exit_reason = f"Exhausted — all {len(priority_queue)} failures addressed or skipped"

if exit_reason:
    break  # Exit the autoloop
```

### AutoLoop Summary

After exiting the loop, emit a structured summary of what happened:

```
kept_count = len(autoloop_state["kept"])
discarded_count = len(autoloop_state["discarded"])
held_count = len(autoloop_state["held"])
iterations = autoloop_state["iteration"]
baseline_score = autoloop_state["score_history"][0]
final_score = autoloop_state["score_history"][-1]
delta = final_score - baseline_score

emit(f"AutoLoop complete — {exit_reason}")
emit(f"Iterations: {iterations}, KEEP: {kept_count}, DISCARD: {discarded_count}, HOLD: {held_count}")
emit(f"Flow Score: {baseline_score:.3f} → {final_score:.3f} ({delta:+.3f})")
```

**Detailed breakdown (always shown):**

```
if autoloop_state["kept"]:
    emit("KEPT changes:")
    for k in autoloop_state["kept"]:
        emit(f"  ✓ {k['gap_type']} on {k['target']} — delta {k['actual_delta']:+.3f}")

if autoloop_state["discarded"]:
    emit("DISCARDED changes (rolled back):")
    for d in autoloop_state["discarded"]:
        emit(f"  ✗ {d['gap_type']} on {d['target']} — predicted {d['predicted_delta']:+.3f}, actual {d['actual_delta']:+.3f}")

if autoloop_state["held"]:
    emit("HELD for review:")
    for h in autoloop_state["held"]:
        emit(f"  ? {h['gap_type']} on {h.get('target', h.get('query', 'unknown'))} — {h.get('reason', 'review recommended')}")
```

### Degraded Mode Behavior

When operating in degraded mode (no Viking), the AutoLoop has reduced capabilities:

- **EMBEDDING_GAP fixes are skipped entirely** — Viking is unavailable, so re-indexing is impossible
- **Step 5b (Viking re-search) is skipped** — precision_at_3 remains null throughout
- **Flow Score is computed using the degraded formula** (Section 4, Degraded Mode)
- **The 0.75 cap still applies** — the loop cannot push past HEALTHY without semantic verification
- **Fewer iterations are typical** — without semantic scoring, fewer gap types can be addressed

Emit once at loop start if degraded:

```
if DEGRADED_MODE:
    emit("WARNING: AutoLoop running in DEGRADED mode — EMBEDDING_GAP fixes disabled, semantic scoring unavailable")
```

**Proceed to Section 7 (Enforce) with the `autoloop_state` and updated metrics.**

---

## Section 7: Enforce

> The autoloop converged. Now lock in the gains — graduate learnings, re-index the world, install guardrails, and clean up.

Enforcement happens after the AutoLoop exits (or after Diagnose, if all queries passed). This section ensures that every improvement persists across sessions, Viking stays current, and the project inherits organizational rules that maintain tree health going forward.

### Step 1: Graduation Protocol

The autoloop produced data. Graduation converts that data into durable project knowledge.

**1a. Calibration — already done.**

`neuraltree_update_calibration()` was called after every AutoLoop iteration (Section 6, Step 7). No additional calibration work is needed here. The calibration file at `.neuraltree/calibration.json` reflects the cumulative prediction accuracy from this run.

**1b. Evolve queries.**

The benchmark queries (Section 4) have earned status updates based on their performance in this run. Queries that consistently pass are wasting benchmark time. Queries that caught real issues are the canaries worth keeping.

```
evolved_queries = []

for query in baseline["queries"]:
    query_status = query.get("status", "active")

    # Queries that passed in ALL iterations → demote to spot-check
    # These queries found no failures — they're healthy canaries
    if query.get("precision", 0) >= 0.67 and query_status != "critical":
        query["status"] = "spot-check"

    # Queries that caught real issues → promote to critical
    # These queries found failures that led to KEEP or HOLD decisions
    matching_kept = any(
        k["target"] in query.get("source", "")
        for k in autoloop_state["kept"]
    )
    matching_held = any(
        h.get("target", h.get("query", "")) in query.get("source", "")
        for h in autoloop_state["held"]
    )
    if matching_kept or matching_held:
        query["status"] = "critical"

    evolved_queries.append({
        "text": query["text"],
        "source": query.get("source", ""),
        "status": query["status"],
        "last_precision": query.get("precision"),
        "last_run": now_iso8601()
    })
```

**1c. Generate fresh queries from recent git activity.**

New files and recently modified areas may not have queries covering them yet. Generate fresh queries to fill the gap:

```
# Get files modified since last run (or last 7 days if first run)
recent_files = git_log_modified_files(since=state.get("last_run", "7 days ago"))

# Filter to knowledge files (memory/, docs/, CLAUDE.md, etc.)
knowledge_files = [f for f in recent_files if is_knowledge_file(f)]

if knowledge_files:
    fresh_result = neuraltree_generate_queries(
        project_root=".",
        claude_md_path="CLAUDE.md",
        memory_md_path="memory/MEMORY.md",
        index_paths=[f for f in knowledge_files if f.endswith("_INDEX.md")],
        git_log_lines=50,
        indexed_doc_count=len(knowledge_files)
    )

    for q in fresh_result["queries"]:
        # Only add if not already covered by an existing query
        if not any(eq["text"] == q["text"] for eq in evolved_queries):
            evolved_queries.append({
                "text": q["text"],
                "source": q.get("source", ""),
                "status": "active",
                "last_precision": None,
                "last_run": None
            })
```

**1d. Compress to history.**

Write a single-line summary of this run to the history directory. This creates a time series of tree health that compounds across sessions.

```json
// .neuraltree/history/YYYY-MM-DD.json
{
    "date": "2026-04-05",
    "flow_score_before": 0.58,
    "flow_score_after": 0.91,
    "delta": 0.33,
    "iterations": 4,
    "kept": 3,
    "discarded": 0,
    "held": 1,
    "fixes": ["wire: 2", "index: 1"],
    "exit_reason": "healthy",
    "calibration_accuracy": 0.87,
    "duration_seconds": 480
}
```

```
import json, os
from datetime import datetime

history_dir = os.path.join(".neuraltree", "history")
os.makedirs(history_dir, exist_ok=True)

elapsed_seconds = int((now() - run_start_time).total_seconds())

history_entry = {
    "date": datetime.now().strftime("%Y-%m-%d"),
    "flow_score_before": autoloop_state["score_history"][0],
    "flow_score_after": autoloop_state["score_history"][-1],
    "delta": autoloop_state["score_history"][-1] - autoloop_state["score_history"][0],
    "iterations": autoloop_state["iteration"],
    "kept": len(autoloop_state["kept"]),
    "discarded": len(autoloop_state["discarded"]),
    "held": len(autoloop_state["held"]),
    "fixes": summarize_fixes(autoloop_state["kept"]),  # e.g. ["wire: 2", "index: 1"]
    "exit_reason": exit_reason,
    "calibration_accuracy": read_calibration_accuracy(".neuraltree/calibration.json"),
    "duration_seconds": elapsed_seconds
}

history_path = os.path.join(history_dir, f"{history_entry['date']}.json")
with open(history_path, "w") as f:
    json.dump(history_entry, f, indent=2)
```

If a history file already exists for today (multiple runs in one day), append a numeric suffix: `2026-04-05_2.json`, `2026-04-05_3.json`, etc.

**1e. Update state.json.**

This is the persistent state that the Skill reads on next activation (Section 1, Step 2). It determines the mode for the next run.

```json
// .neuraltree/state.json
{
    "flow_score": 0.91,
    "last_run": "2026-04-05T14:30:00Z",
    "mode": "bootstrap",
    "run_count": 1,
    "calibration_accuracy": 0.87
}
```

```
# Load previous state (from Section 1, Step 2 — carried forward as previous_state)
previous_state = {}  # default for first run
if os.path.exists(".neuraltree/state.json"):
    previous_state = json.load(open(".neuraltree/state.json"))

state = {
    "flow_score": current_flow_score,
    "last_run": now_iso8601(),
    "mode": mode,
    "run_count": (previous_state.get("run_count", 0) + 1),
    "calibration_accuracy": read_calibration_accuracy(".neuraltree/calibration.json"),
    "metrics": {
        "hop_efficiency": latest_metrics.get("hop_efficiency", 0.0),
        "synapse_coverage": latest_metrics.get("synapse_coverage", 0.0),
        "dead_neuron_ratio": latest_metrics.get("dead_neuron_ratio", 0.0),
        "freshness": latest_metrics.get("freshness", 0.0),
        "trunk_pressure": latest_metrics.get("trunk_pressure", 0.0),
        "precision_at_3": latest_metrics.get("precision_at_3")
    }
}

with open(".neuraltree/state.json", "w") as f:
    json.dump(state, f, indent=2)
```

**1f. Save evolved queries.**

Write the evolved query set to disk. Future spot-check runs will filter to `status: "critical"` only, and future full runs will skip `status: "spot-check"` queries unless they fail again.

```
with open(".neuraltree/queries.json", "w") as f:
    json.dump(evolved_queries, f, indent=2)
```

**1g. Clean .tmp/ working files (retain backups).**

The `.neuraltree/.tmp/` directory holds both working files (iteration logs, prediction buffers) and backup files created during the AutoLoop. Working files are transient and should be cleaned. Backups are retained until the NEXT successful run so the user can verify and rollback after the session.

```
# Retain .tmp/backup/ until NEXT successful run (user can verify and rollback after session)
# Only delete .tmp/ working files (iteration_*.json, predictions_buffer.json)
import glob, os

tmp_dir = os.path.join(".neuraltree", ".tmp")
if os.path.exists(tmp_dir):
    # Delete working files
    for pattern in ["iteration_*.json", "predictions_buffer.json"]:
        for f in glob.glob(os.path.join(tmp_dir, pattern)):
            os.remove(f)

# Keep: .neuraltree/.tmp/backup/ (retained for post-session rollback)
# The NEXT run's backup phase will clean the previous backup before creating new ones.
```

### Step 2: Re-index Viking

Every file that was modified, created, or wired during the AutoLoop needs to be re-indexed in Viking. Without re-indexing, Viking's search results will be stale — the next benchmark would penalize files that are actually fixed.

```
modified_files = set()

# Files modified by KEEP actions
for k in autoloop_state["kept"]:
    modified_files.add(k["target"])

# Files created by FOCUS_GAP splits (new leaves)
for k in autoloop_state["kept"]:
    if k["gap_type"] == "FOCUS_GAP":
        # The split created new files — they need indexing too
        modified_files.update(k.get("new_files", []))

# Files wired (## Related links added)
for k in autoloop_state["kept"]:
    if k["gap_type"] == "SYNAPSE_GAP":
        # Wire adds ## Related to the target AND its newly-linked neighbors
        modified_files.update(k.get("linked_files", []))

emit(f"Phase 5/5: Re-indexing {len(modified_files)} files in Viking...")

for file_path in modified_files:
    if os.path.exists(file_path):
        viking_add_resource(uri=file_path, content=read_file(file_path))
```

**If `DEGRADED_MODE` is true:** Skip this step entirely. Viking is unavailable — re-indexing is impossible. Emit:

```
if DEGRADED_MODE:
    emit("Phase 5/5: Skipping Viking re-index (DEGRADED mode)")
```

### Step 3: Install Organization Rule

Create a `.claude/rules/neuraltree.md` file in the target project. This rule ensures that the project's organizational standards are enforced in every Claude Code session — not just during NeuralTree runs.

**Only install on first run** (`state["run_count"] == 1`) or if the file doesn't exist. Don't overwrite on subsequent runs — the user may have customized it.

```
project_root = "."
rules_dir = os.path.join(project_root, ".claude", "rules")
rules_path = os.path.join(rules_dir, "neuraltree.md")

NEURALTREE_RULE_CONTENT = """# NeuralTree Organization Rule

> Installed by /neuraltree. Enforces information flow standards in every session.

## Session Start Protocol

1. Read `_INDEX.md` files in `memory/` and `docs/` before navigating
2. Check trunk files (MEMORY.md, CLAUDE.md) — if approaching 100 lines, alert user
3. Use Viking semantic search before grepping for project knowledge

## File Standards (Memory & Docs)

- **Size:** 20-80 lines per leaf file. Trunks (_INDEX.md, MEMORY.md) under 100 lines.
- **Frontmatter:** Every leaf file must have `name`, `description`, `type`, `last_verified`
- **## Related:** Every leaf must link to 1-5 related files (synapses)
- **## Docs:** Reference project files where applicable

## Weekly Hygiene Checklist

- [ ] Run `/neuraltree` (or spot-check if recent)
- [ ] Verify MEMORY.md < 100 lines
- [ ] Archive completed phases from `active/` to `archive/`
- [ ] Delete `__pycache__/`, stale logs, orphaned temp files
- [ ] Check `_INDEX.md` files match actual directory contents
"""

if not os.path.exists(rules_path):
    os.makedirs(rules_dir, exist_ok=True)
    write_file(rules_path, NEURALTREE_RULE_CONTENT)
    emit("Phase 5/5: Installed .claude/rules/neuraltree.md")
else:
    emit("Phase 5/5: Organization rule already installed — skipping")
```

### Step 4: Cleanup

Final housekeeping. Remove transient artifacts, verify persistent state, and release the lock.

```
# 1. Remove .lock file (allows next run)
lock_path = os.path.join(".neuraltree", ".lock")
if os.path.exists(lock_path):
    os.remove(lock_path)

# 2. Remove .tmp/ working files ONLY (preserve backup for post-session rollback)
for f in glob.glob(".neuraltree/.tmp/iteration_*.json"):
    os.remove(f)
predictions = os.path.join(".neuraltree", ".tmp", "predictions_buffer.json")
if os.path.exists(predictions):
    os.remove(predictions)
# DO NOT delete .neuraltree/.tmp/backup/ — retained until next run

# 3. Verify state.json was written
assert os.path.exists(".neuraltree/state.json"), "CRITICAL: state.json not written!"

# 4. Verify history was written
today = datetime.now().strftime("%Y-%m-%d")
history_path = os.path.join(".neuraltree", "history", f"{today}.json")
assert os.path.exists(history_path), f"CRITICAL: history/{today}.json not written!"

emit("Phase 5/5: Cleanup complete. Lock released.")
```

**Proceed to Section 8 (Execution Report) with all data assembled.**

---

## Section 8: Execution Report

> The final output. One glance tells the user everything: what improved, what's pending, and when to run again.

Every NeuralTree run ends with a structured report. The report format varies based on the run type — full runs get the complete table, spot-checks get a one-liner.

### Full Report Format

Emit this report after every `bootstrap`, `critical`, `maintenance`, or `health-check` run:

```
═══════════════════════════════════════════════════
  NeuralTree Report — {project_name}
  Mode: {mode} | Duration: {elapsed_seconds}s
═══════════════════════════════════════════════════

Flow Score: {before} → {after} ({delta:+.2f})

┌──────────────────────────────────────────────────┐
│ Metric              Before   After    Delta      │
│ Hop Efficiency       0.45    0.88    +0.43       │
│ Precision@3          0.33    0.87    +0.54       │
│ Synapse Coverage     0.61    0.97    +0.36       │
│ Dead Neuron Ratio    0.70    1.00    +0.30       │
│ Freshness            0.80    0.95    +0.15       │
│ Trunk Pressure       0.80    1.00    +0.20       │
└──────────────────────────────────────────────────┘
```

**Metric table assembly:**

```
before_metrics = baseline["metrics"]
before_metrics["precision_at_3"] = baseline.get("precision_at_3", "N/A")

after_metrics = {
    "hop_efficiency": latest_metrics["hop_efficiency"],
    "precision_at_3": latest_metrics.get("precision_at_3", "N/A"),
    "synapse_coverage": latest_metrics["synapse_coverage"],
    "dead_neuron_ratio": latest_metrics["dead_neuron_ratio"],
    "freshness": latest_metrics["freshness"],
    "trunk_pressure": latest_metrics["trunk_pressure"]
}

METRIC_LABELS = [
    ("hop_efficiency",    "Hop Efficiency"),
    ("precision_at_3",    "Precision@3"),
    ("synapse_coverage",  "Synapse Coverage"),
    ("dead_neuron_ratio", "Dead Neuron Ratio"),
    ("freshness",         "Freshness"),
    ("trunk_pressure",    "Trunk Pressure"),
]

for key, label in METRIC_LABELS:
    bv = before_metrics.get(key, "N/A")
    av = after_metrics.get(key, "N/A")
    if isinstance(bv, (int, float)) and isinstance(av, (int, float)):
        delta = av - bv
        emit(f"│ {label:<20} {bv:>6.2f}   {av:>6.2f}   {delta:>+6.2f}       │")
    else:
        emit(f"│ {label:<20} {'N/A':>6}   {'N/A':>6}   {'N/A':>6}       │")
```

### Action Sections

After the metric table, list all actions grouped by category:

**SAFE ACTIONS (executed — non-destructive):**

These are changes the autoloop already applied. They don't need approval because they're non-destructive (wiring links, updating freshness, re-indexing).

```
if autoloop_state["kept"]:
    emit("\nSAFE ACTIONS (executed — non-destructive):")
    for k in autoloop_state["kept"]:
        action_desc = describe_action(k)  # e.g. "added ## Related (3 synapses)"
        emit(f"  ✓ {k['target']} — {action_desc}")
```

**PENDING ACTIONS (require approval — destructive):**

These are changes the autoloop identified but did NOT execute because they're destructive (deletes, moves, archives). They're gathered from CONTENT_GAP items and any FOCUS_GAP splits that would delete the original file.

```
# PENDING ACTIONS come from HOLD items that need user approval
pending_actions = []
for held in autoloop_state["held"]:
    if held.get("gap_type") == "CONTENT_GAP":
        pending_actions.append({"type": "CREATE", "target": held.get("suggested_path", "unknown"), "reason": held["reason"]})
    elif held.get("gap_type") == "FOCUS_GAP":
        pending_actions.append({"type": "SPLIT", "target": held.get("target", "unknown"), "reason": held["reason"]})

if pending_actions:
    emit("\nPENDING ACTIONS (require approval — destructive):")
    for i, pa in enumerate(pending_actions, 1):
        if pa["type"] == "DELETE":
            emit(f"  {i}. ⚠ DELETE {pa['target']} — {pa['reason']} (trace: {pa['trace']})")
        elif pa["type"] == "ARCHIVE":
            emit(f"  {i}. ⚠ ARCHIVE {pa['target']} → {pa['destination']} — {pa['reason']}")
        elif pa["type"] == "CREATE":
            emit(f"  {i}. ⚠ CREATE {pa['target']} — {pa['reason']}")
        elif pa["type"] == "SPLIT":
            emit(f"  {i}. ⚠ SPLIT {pa['target']} — {pa['reason']}")
```

**NEEDS REVIEW (HOLD items):**

```
hold_items = [h for h in autoloop_state["held"] if h.get("gap_type") not in ("CONTENT_GAP", "FOCUS_GAP")]

if hold_items:
    emit("\nNEEDS REVIEW (HOLD items):")
    for h in hold_items:
        target = h.get("target", h.get("query", "unknown"))
        emit(f"  ? {target} — {h.get('reason', 'review recommended')}")
```

**KEPT (verified alive):**

```
if autoloop_state["kept"]:
    emit("\nKEPT (verified alive):")
    for k in autoloop_state["kept"]:
        emit(f"  ✓ {k['target']} — {k['gap_type']} fixed, delta {k['actual_delta']:+.3f}")
```

### Footer

```
emit(f"\nAutoLoop: {autoloop_state['iteration']} iterations, "
     f"{len(autoloop_state['kept'])} KEEP / "
     f"{len(autoloop_state['discarded'])} DISCARD / "
     f"{len(autoloop_state['held'])} HOLD")

calibration_acc = read_calibration_accuracy(".neuraltree/calibration.json")
emit(f"Calibration accuracy: {calibration_acc:.0%}")
emit(f"Exit reason: {exit_reason}")

# Calculate next run ETA based on current score
if current_flow_score >= 0.90:
    next_eta = "7 days (weekly spot-check)"
elif current_flow_score >= 0.75:
    next_eta = "3 days (health-check)"
else:
    next_eta = "1 day (maintenance)"

emit(f"Next run ETA: {next_eta}")
```

### Handling User Response to Pending Actions

If `pending_actions` is non-empty, the report ends with an interactive prompt:

```
if pending_actions:
    emit(f"\nWhich actions? (all / none / pick by number, e.g. '1,3')")
    user_response = wait_for_user_input()
```

**Processing the response:**

**CREATE actions:**

When user approves a CREATE action:
1. Emit: "This file needs new content that doesn't exist in the project yet."
2. Emit: "Suggested path: {action.path}"
3. Emit: "Topic needed: {action.reason}"
4. Emit: "Please provide the content, or type 'skip' to defer."
5. Wait for user input
6. If user provides content: write to file with proper frontmatter, wire with neuraltree_wire()
7. If user types 'skip': mark as deferred, save to next run's pending list

**Inline logic for `execute_pending_action`:**

For each approved pending action, execute based on type:

```
def execute_pending_action(action, project_root):
    if action["type"] == "DELETE":
        # Trace Before Prune (Section 2 rule)
        trace = neuraltree_trace(target=action["target"], project_root=project_root)
        if trace["is_alive"]:
            emit(f"WARNING: {action['target']} still has {len(trace['referenced_by'])} references. Skipping delete.")
            return  # Do not delete alive files
        # File is dead — safe to delete
        os.remove(os.path.join(project_root, action["target"]))
        emit(f"  Deleted {action['target']}")

    elif action["type"] == "ARCHIVE":
        archive_dir = os.path.join(project_root, "archive")
        os.makedirs(archive_dir, exist_ok=True)
        dest = os.path.join(archive_dir, os.path.basename(action["target"]))
        shutil.move(os.path.join(project_root, action["target"]), dest)
        # Update any _INDEX.md that referenced the moved file
        emit(f"  Archived {action['target']} → archive/{os.path.basename(action['target'])}")

    elif action["type"] == "SPLIT":
        emit(f"FOCUS_GAP: {action['target']} is too large and should be split into focused leaves.")
        emit(f"  1. Read the file and identify distinct topics/sections")
        emit(f"  2. Create a new leaf file for each topic (20-80 lines each)")
        emit(f"  3. Update _INDEX.md and ## Related links to point to the new leaves")
        emit(f"  4. Re-index all new files in Viking")
        emit(f"  Manual splitting recommended — type 'skip' to defer.")
        user_content = wait_for_user_input()
        if user_content.strip().lower() == "skip":
            return  # Deferred to next run
        # User confirmed — they will handle the split manually
        emit(f"  Split of {action['target']} acknowledged. Verify results on next /neuraltree run.")
        return

    elif action["type"] == "CREATE":
        emit(f"CONTENT_GAP: What content should go in {action['target']}? Provide it now or type 'skip'.")
        user_content = wait_for_user_input()
        if user_content.strip().lower() == "skip":
            return  # Deferred to next run
        write_file(os.path.join(project_root, action["target"]), user_content)
        emit(f"  Created {action['target']}")
```

**"all"** — Execute all pending actions, re-score, and emit a final update:

```
if user_response == "all":
    for pa in pending_actions:
        execute_pending_action(pa, project_root=".")

    # Re-score after executing pending actions
    new_score = neuraltree_score(project_root=".")
    p3 = latest_metrics.get("precision_at_3") or 0.0
    if DEGRADED_MODE:
        sr = (new_score["metrics"]["hop_efficiency"] + new_score["metrics"]["synapse_coverage"]) / 2
        new_flow_score = min(0.75,
            sr * 0.45 + new_score["metrics"]["dead_neuron_ratio"] * 0.25 +
            new_score["metrics"]["freshness"] * 0.20 + new_score["metrics"]["trunk_pressure"] * 0.10
        )
    else:
        new_flow_score = new_score["flow_score_partial"] + (p3 * 0.25)

    emit(f"\nPending actions executed. Flow Score: {current_flow_score:.2f} → {new_flow_score:.2f}")

    # Update state.json and history with final score
    update_state_and_history(new_flow_score)
```

**Specific picks** (e.g. "1,3") — Execute only the selected actions:

```
elif "," in user_response or user_response.isdigit():
    picks = [int(x.strip()) for x in user_response.split(",")]
    for pick in picks:
        if 1 <= pick <= len(pending_actions):
            execute_pending_action(pending_actions[pick - 1], project_root=".")

    # Re-score and update
    new_score = neuraltree_score(project_root=".")
    p3 = latest_metrics.get("precision_at_3") or 0.0
    if DEGRADED_MODE:
        sr = (new_score["metrics"]["hop_efficiency"] + new_score["metrics"]["synapse_coverage"]) / 2
        new_flow_score = min(0.75,
            sr * 0.45 + new_score["metrics"]["dead_neuron_ratio"] * 0.25 +
            new_score["metrics"]["freshness"] * 0.20 + new_score["metrics"]["trunk_pressure"] * 0.10
        )
    else:
        new_flow_score = new_score["flow_score_partial"] + (p3 * 0.25)
    emit(f"\nSelected actions executed. Flow Score: {current_flow_score:.2f} → {new_flow_score:.2f}")
    update_state_and_history(new_flow_score)
```

**"none"** — No actions executed. Pending actions are saved for the next run:

```
elif user_response == "none":
    emit("\nNo actions executed. Pending items saved for next run.")
    # Pending actions are implicitly available via diagnose in the next run
```

### Spot-Check Short Form

When the run mode is `spot-check` and the score is healthy (Section 4, Step 7 exits early), emit this compact format instead of the full report:

```
NeuralTree spot-check — {project_name}
Score: {score} ({status}) | {query_count} queries | 0 failures
Last full run: {days} days ago | Next: {date}
```

```
# Note: Spot-check report is emitted in Section 4 Step 7. This block handles
# the case where spot-check was upgraded to maintenance mid-run.
if mode == "spot-check" and current_flow_score > 0.90:
    days_since = (now() - parse_iso(state.get("last_run", now_iso8601()))).days
    next_date = (now() + timedelta(days=7)).strftime("%Y-%m-%d")

    emit(f"NeuralTree spot-check — {project_name}")
    emit(f"Score: {current_flow_score:.2f} (Excellent) | {len(queries)} queries | 0 failures")
    emit(f"Last full run: {days_since} days ago | Next: {next_date}")
```

### Degraded Mode Report

When operating in degraded mode, the report includes additional context:

- **Precision@3 row shows "N/A"** instead of numbers
- **A warning banner appears** above the metric table:

```
if DEGRADED_MODE:
    emit("⚠ DEGRADED MODE — Viking unavailable. Semantic metrics disabled. Score capped at 0.75.")
```

- **The footer includes a recommendation:**

```
if DEGRADED_MODE:
    emit("Recommendation: Start Viking and re-run for full assessment.")
```

### Report Complete

After the report is emitted and any user response to pending actions is processed, the NeuralTree run is complete. The lock has been released (Section 7, Step 4), state is persisted, and the project is ready for the next session.

---

## Section 9: Degraded Mode & Edge Cases

> Things go wrong. The skill must handle every failure gracefully — never crash, never corrupt, never leave the project worse than it found it.

This section defines how NeuralTree behaves when dependencies are missing, projects are unusual, or infrastructure fails. Every scenario here has been anticipated — there are no "undefined" states.

### Without Viking (DEGRADED_MODE)

When Viking MCP is unreachable (connection refused, timeout, not installed):

1. **Warn immediately:** `"Viking not found. Operating in structure-only mode (4 of 6 metrics)."`
2. **Skip:** Precision@3 evaluation, Viking re-indexing in post-loop enforcement
3. **Merge structure_reachability:** `structure_reachability = (hop_efficiency + synapse_coverage) / 2` — the two structural sub-metrics absorb what Precision@3 would have measured
4. **Reweight the remaining metrics:**

| Metric | Normal Weight | Degraded Weight |
|--------|--------------|-----------------|
| structure_reachability | — | 0.45 |
| dead_neuron_ratio | 0.15 | 0.25 |
| freshness | 0.10 | 0.20 |
| trunk_pressure | 0.05 | 0.10 |
| precision_at_3 | 0.25 | — (skipped) |

5. **Reclassify EMBEDDING_GAP → SYNAPSE_GAP:** Without Viking, embedding gaps cannot be fixed by re-indexing. Reclassify them as SYNAPSE_GAP so the AutoLoop fixes them via wiring (adding `## Related` links, cross-references) instead of attempting Viking operations that will fail.

**Score cap in degraded mode:** Flow Score is capped at 0.75. A project cannot be rated HEALTHY or EXCELLENT without semantic search validation.

### Bootstrap: No CLAUDE.md

When the target project has no CLAUDE.md (common for new or external projects):

1. **Check README.md as initial trunk.** If a README.md exists, treat it as the provisional trunk node — extract structure, purpose, and navigation hints from it.
2. **No README either:** Fall back to directory structure + filenames. Use `neuraltree_scan()` output to infer project shape. File names and directory names become the only source for `neuraltree_generate_queries()`.
3. **Create minimal CLAUDE.md nav hub.** After the scan phase, generate a minimal CLAUDE.md that contains:
   - Project name (from package.json, pyproject.toml, or directory name)
   - Directory listing with one-line descriptions
   - `## Key Files` section linking to the most-connected files
4. **Proceed with full pipeline.** A low Flow Score is expected and normal — the AutoLoop will improve it. Do not skip phases or lower thresholds.

### Bootstrap: No Git

When the project directory is not a git repository:

- `neuraltree_backup()` uses file copy instead of git stash — this already works (the MCP tool detects git absence and falls back to directory copy).
- `neuraltree_sandbox_create()` falls back to rsync instead of git worktree — this already works (same detection logic).
- **Warn about harder reversibility:** `"No git detected. Backups use file copy — reverting changes requires manual restore from .neuraltree/.tmp/backup/."` Git-based undo is instant; file-copy undo requires the user to confirm which backup to restore.
- All other operations proceed normally. Git is a convenience, not a requirement.

### Bootstrap: Empty Project

When the project has very few files (< 5 files, or only config files):

- `neuraltree_scan()` returns minimal file list — this is expected.
- `neuraltree_generate_queries()` generates queries from filenames only — fewer sources means fewer queries, which is correct.
- Flow Score will be ~0.0 — this is expected and normal for an empty project.
- The AutoLoop creates initial structure: CLAUDE.md, suggested directory layout, initial wiring. This is the bootstrap path — NeuralTree is creating the neural tree from scratch.
- Do not treat a low score as a failure. Emit: `"Empty project detected. Creating initial structure..."`

### Monorepo Detection

When the project contains multiple CLAUDE.md files or multiple package.json files at different directory depths:

- **Scope to cwd only.** NeuralTree operates on the current working directory, not the entire repository. If cwd is `/repo/packages/frontend`, only that subtree is scanned.
- **Detect cross-boundary references:** If `neuraltree_wire()` or `neuraltree_trace()` reveals links pointing outside the cwd scope, flag them but do not follow them.
- **Warn about cross-boundary wiring:** `"Monorepo detected. Scoping to {cwd}. Cross-boundary references found — wiring limited to current scope."`
- Do not attempt to score or modify files outside cwd. Monorepo-wide organization requires running NeuralTree separately in each subproject.

### Concurrent Run Protection

NeuralTree must never run twice on the same project simultaneously. File mutations from two concurrent runs would corrupt the project.

- **Lock check at activation.** Before any work begins (Section 1, Step 3), check for `.neuraltree/.lock`. The lock file contains only an ISO 8601 timestamp string (e.g. `2026-04-05T14:30:00Z`). No PID, no other content.
- **Stale lock (>1 hour):** Auto-remove the lock with a warning: `"Stale lock found (started {timestamp}). Removing and proceeding."` One hour is generous — no NeuralTree run should take that long.
- **Active lock:** Abort immediately. `"NeuralTree is already running (started {timestamp}). Aborting."` Do not attempt to queue or wait.
- **ALL code paths release lock.** Success, failure, crash, user cancellation — every exit path must release the lock. Use try/finally or equivalent. A leaked lock blocks all future runs until the 1-hour stale timeout.

### Scale Limits

NeuralTree is designed for typical projects (10–5,000 files). At extreme scale, operations are capped to prevent runaway resource consumption:

| Parameter | Limit | Behavior At Limit |
|-----------|-------|-------------------|
| File scan | 10,000 files | `"Large project — sampling mode"` — randomly sample files, prioritize trunk/branch nodes |
| Test queries | 50 max | Cap query generation regardless of project size |
| AutoLoop iterations | 10 max | Hard stop, emit partial report with results so far |
| Leaf file size | 500 lines | Flag as FOCUS_GAP — file should be split or promoted to branch |
| Trunk (CLAUDE.md) size | 100 lines | Flag as TRUNK_PRESSURE — trunk is overloaded, needs delegation to branches |
| Backup directory | 100 MB | Skip large files (binaries, data files) with warning: `"Skipping {file} ({size} MB) — exceeds backup limit"` |

These limits are hard caps, not suggestions. Exceeding them degrades quality and wastes resources.

### Error Recovery

When infrastructure fails mid-run, NeuralTree must recover gracefully — never leave the project in a worse state than it started:

| Error | Recovery |
|-------|----------|
| MCP crash mid-loop | Release lock, report partial results from completed iterations, suggest `"Restart NeuralTree to continue from iteration {n}"` |
| Viking timeout | Retry once (5-second timeout). If retry fails, switch to DEGRADED_MODE for the remainder of the run. Do not retry again. |
| File permission denied | Report warning: `"Permission denied: {path} — skipping"`. Continue with remaining files. Do not abort the entire run for one inaccessible file. |
| Disk full during backup | Abort the backup phase. Release lock. Report: `"Disk full — backup aborted. Free space and retry."` Do not proceed without a backup. |
| LLM judge returns garbage | Default to NO (conservative — do not apply the change). Log warning: `"LLM judge returned unparseable response — defaulting to HOLD"`. Continue with next iteration. |
| State file corrupted | Re-initialize state from defaults. Warn: `"State file corrupted — resetting to defaults. Previous calibration data lost."` |
| calibration.json corrupted | Delete file and restart with defaults (accuracy=0.5). Predictions will be less accurate for 2-3 runs until recalibrated. |
| queries.json corrupted | Delete file. Next run generates fresh queries from project context. Spot-check filtering unavailable until queries are re-evolved (1-2 full runs). |
| Network partition (Viking mid-query) | Treat as Viking timeout — retry once, then degrade. Do not hang waiting for reconnection. |

**The cardinal rule of error recovery:** Never leave the lock held. Never leave the project modified without a backup. Never silently swallow an error — always warn the user.
