---
name: neuraltree
description: >
  Universal neural organization — transforms any project into a structured
  information system where any fact is reachable in 0-2 hops.
version: 0.1.0
tools_required:
  - neuraltree-mcp (20 tools)
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
| No `state.json` | **bootstrap** | Benchmark → Diagnose → AutoLoop (sandbox) → Enforce | First run. Full analysis needed. Sandbox mandatory. |
| `state.json` exists, `flow_score < 0.60` | **critical** | Benchmark → Diagnose → AutoLoop (sandbox) → Enforce | Information flow is broken. Full intervention. Sandbox mandatory. |
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

For each query, call Viking to retrieve the top 3 most relevant results, then read their full content. This tests whether the project's indexed content actually answers the questions an agent would ask.

```
for query in queries:
    viking_result = viking_search(query=query["text"], limit=3)
    # IMPORTANT: Read full content for each result — the search abstract is often
    # empty or just "Directory overview". The LLM judge needs actual content to evaluate.
    for result in viking_result["results"]:
        full_content = viking_read(uri=result["uri"])
        result["content"] = full_content[:2000]  # first ~50 lines for judging
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
Result content (first 50 lines): {result["content"]}

Rubric: Would reading this file help answer the query?
- YES if the file contains information directly useful for answering
- NO if the file is unrelated or only tangentially mentions the topic

Reply YES or NO only.
```

**CRITICAL — LLM Configuration:**

When calling a local LLM (e.g. Ollama with Qwen3.5), you MUST disable "thinking" / chain-of-thought mode. Models with built-in reasoning (Qwen3.5, DeepSeek-R1) will spend 300+ tokens reasoning before answering YES/NO, making the benchmark 10-20x slower.

- **Ollama:** Set `"think": false` in the API request body
- **Other runtimes:** Use the equivalent parameter to disable extended thinking
- **Expected speed:** ~3-5 seconds per judgment (without thinking). If a judgment takes >30 seconds, thinking mode is likely still enabled.

If the LLM does not support disabling thinking, increase `num_predict` to at least 500 tokens to ensure the answer appears after the thinking tokens.

- **Recommended:** Also set `temperature: 0` (or 0.1) for deterministic YES/NO output. At default temperature, the model may prefix the answer with filler text ("Sure!", "The answer is"), causing the malformed-response rule to score it 0 instead of the intended 1.

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
| `FOCUS_GAP` | File is too large (>500 lines) — Viking indexes it but the relevant section is diluted | A 700-line file where the answer is on line 500 — Viking returns the file but the match quality is low |
| `CONTENT_GAP` | No file exists that answers this query — new content must be created | Query about a topic that was discussed verbally but never documented |

### Step 2b: Enrich Dead Neuron Detection

The `dead_neuron_ratio` metric from `neuraltree_score()` uses a simple orphan-file count. Enrich the diagnosis with `neuraltree_find_dead()` which uses word-boundary matching, strips `#anchors` and `?queries` from references, and handles backtick paths — producing a more accurate dead file list.

```
dead_result = neuraltree_find_dead(project_root=".")

# If dead files exist, inject them as additional SYNAPSE_GAP entries
# These files exist but nothing links to them — wiring will make them reachable
if dead_result["total_dead"] > 0:
    for dead_file in dead_result["dead_files"][:20]:  # cap at 20 to avoid queue bloat
        # Only add if not already diagnosed by a failed query (check matching_files, not target_file)
        already_diagnosed = any(
            dead_file["path"] in d.get("matching_files", [])
            for d in diagnosis["diagnoses"]
        )
        if not already_diagnosed:
            diagnosis["diagnoses"].append({
                "query": f"[dead neuron] {dead_file['path']}",
                "gap_type": "SYNAPSE_GAP",
                "target_file": dead_file["path"],
                "matching_files": [dead_file["path"]],
                "fix": f"Wire {dead_file['path']} with ## Related links to make it reachable",
                "source": "neuraltree_find_dead"
            })
    diagnosis["gap_counts"]["SYNAPSE_GAP"] = sum(
        1 for d in diagnosis["diagnoses"] if d["gap_type"] == "SYNAPSE_GAP"
    )
    diagnosis["total_failures"] = len(diagnosis["diagnoses"])
```

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

Inspired by Karpathy's autoresearch methodology. The key insight: the unit of measurement is the **strategy**, not the individual file. Wiring one file out of 436 moves the score by 0.001 — noise. Wiring all orphans at once moves it by 0.15 — signal. Each iteration applies a coherent strategy, measures the full result, and KEEPS or DISCARDS the entire strategy.

**Critical:** Claude is the brain in this loop. MCP tools measure (score, predict, backup). Claude thinks (reads files, understands content, decides how to split, what to wire, which files belong together). The tools propose, Claude refines, the score judges.

### Strategy Queue

The AutoLoop operates on strategies, ordered by expected impact:

| Priority | Strategy | What Claude Does | Metrics Affected |
|----------|----------|-----------------|-----------------|
| 1 | `SPLIT_LARGE` | Read each >500-line file, understand its topics, split into focused files with proper frontmatter + naming. Merge related sections, don't split mechanically. | trunk_pressure, hop_efficiency |
| 2 | `WIRE_ORPHANS` | For each file with 0 inbound refs, read content, find related files, add `## Related` links. Wire in batches. | synapse_coverage, dead_neuron_ratio |
| 3 | `INDEX_DIRS` | Generate `_INDEX.md` for every directory containing .md files. | hop_efficiency |
| 4 | `FRESHNESS` | Review files, update `last_verified` on ones that are still accurate. | freshness |
| 5 | `VIKING_INDEX` | Index all .md files in Viking for semantic search. Requires Viking MCP running. | precision_at_3 |
| 6 | `RE_WIRE` | Second pass after splits created new files. Wire the new files + re-wire neighbors. | synapse_coverage |

### Exit Conditions

Check after **every strategy iteration**. The loop terminates when ANY condition is met:

1. **Healthy:** `flow_score > 0.85` — the tree is healthy enough.
2. **Converged:** 2 consecutive strategies where `|delta| < 0.02` — changes aren't moving the needle.
3. **Hard cap:** 6 strategy iterations per round, 3 rounds max.
4. **Exhausted:** All strategies have been attempted or skipped.

### Sandbox Mode

**Mandatory for:** bootstrap and critical mode (flow_score < 0.60).
**Optional for:** health-check, maintenance, spot-check.

For bootstrap/critical:
1. `neuraltree_sandbox_create()` → isolated copy
2. Run all strategies on the sandbox
3. `neuraltree_sandbox_diff()` → review changes
4. User approves → `neuraltree_sandbox_apply()`
5. `neuraltree_sandbox_destroy()` → cleanup

### Initialize

```
autoloop_state = {
    "iteration": 0,
    "max_iterations": 5,
    "score_history": [baseline["flow_score"]],
    "kept": [],
    "discarded": [],
    "held": [],
    "convergence_counter": 0
}

latest_metrics = dict(baseline["metrics"])
current_flow_score = baseline["flow_score"]

# Sandbox for high-risk modes
if mode in ("bootstrap", "critical"):
    sandbox = neuraltree_sandbox_create(project_root=".")
    sandbox_root = sandbox["sandbox_path"]
    emit(f"Sandbox created at {sandbox_root}")
else:
    sandbox_root = "."

# Build strategy queue from diagnosis gap counts
strategy_queue = []
gap_counts = diagnosis["gap_counts"]

if gap_counts.get("FOCUS_GAP", 0) > 0 or latest_metrics["trunk_pressure"] < 0.8:
    strategy_queue.append("SPLIT_LARGE")
if gap_counts.get("SYNAPSE_GAP", 0) > 0 or latest_metrics["synapse_coverage"] < 0.5:
    strategy_queue.append("WIRE_ORPHANS")
if latest_metrics["hop_efficiency"] < 0.5:
    strategy_queue.append("INDEX_DIRS")
if latest_metrics["freshness"] < 0.5:
    strategy_queue.append("FRESHNESS")
# VIKING_INDEX after structural fixes, before re-wire
if not DEGRADED_MODE and (latest_metrics.get("precision_at_3") is None or latest_metrics.get("precision_at_3", 0) < 0.5):
    strategy_queue.append("VIKING_INDEX")
# RE_WIRE always last — catches new connections from splits + indexing
if "SPLIT_LARGE" in strategy_queue or "VIKING_INDEX" in strategy_queue:
    strategy_queue.append("RE_WIRE")
```

### Per-Strategy Steps

For each strategy in `strategy_queue`, execute these steps. Each strategy is atomic — KEEP the whole thing or DISCARD the whole thing.

#### Step 1: Predict

```
prediction = neuraltree_predict(
    current_metrics=latest_metrics,
    proposed_changes=[{"action": strategy.lower(), "target": "batch"}],
    project_root=sandbox_root
)
predicted_delta = prediction["predicted_delta"]
emit(f"Strategy {strategy}: predicted delta {predicted_delta:+.4f}")
```

#### Step 2: Backup

```
neuraltree_backup(files=["__ALL_MD__"], project_root=sandbox_root)
```

**`__ALL_MD__`** is a sentinel that tells the backup tool to snapshot all .md files. This is the safety net — if the strategy fails, we restore everything.

#### Step 3: Execute Strategy (Claude Thinks Here)

This is where Claude reads files, understands content, and makes intelligent decisions. The MCP tools propose; Claude refines.

**SPLIT_LARGE strategy:**

```
# 1. Find all files >500 lines
large_files = [f for f in scan_result["files"] if f.endswith(".md")]
for file_path in large_files:
    content = read_file(file_path)
    if len(content.splitlines()) <= 500:
        continue

    # 2. Get mechanical split proposal from MCP tool
    split_plan = neuraltree_plan_split(target=file_path, project_root=sandbox_root, max_lines=500)

    # 3. CLAUDE READS AND THINKS — this is NOT mechanical
    # - Read each proposed section's content
    # - Merge sections that cover the same topic
    # - Rename files to be meaningful (not CLAUDE_section_14.md)
    # - Decide if any section is too small to be its own file
    # - Write proper frontmatter (name, description, last_verified)

    # 4. Write the refined splits
    # For each refined split file:
    #   - Write content with frontmatter
    #   - Add ## Related links to sibling files from the same parent
    #   - If not DEGRADED_MODE: viking_add_resource(uri=new_file)

    # 5. Replace original with an index file linking to all splits
    # 6. Generate _INDEX.md via neuraltree_generate_index if new directory created
```

**WIRE_ORPHANS strategy:**

```
# 1. Get the dead/orphan file list
dead_result = neuraltree_find_dead(project_root=sandbox_root)

# 2. For each orphan, wire it
all_leaf_paths = scan_result["files"]
wired_count = 0
for dead_file in dead_result["dead_files"]:
    wire_result = neuraltree_wire(
        file_path=dead_file["path"],
        all_leaf_paths=all_leaf_paths,
        project_root=sandbox_root
    )
    if wire_result.get("suggested_content") and wire_result.get("related"):
        # CLAUDE REVIEWS the suggestions — are these related files actually relevant?
        # Claude reads the target file and the suggested related files.
        # If the suggestions make sense, apply them:
        apply_suggested_content(dead_file["path"], wire_result["suggested_content"])
        wired_count += 1

emit(f"  Wired {wired_count}/{len(dead_result['dead_files'])} orphan files")
```

**INDEX_DIRS strategy:**

```
# Find all directories containing .md files
md_dirs = set()
for md_file in scan_result["files"]:
    if md_file.endswith(".md"):
        d = os.path.dirname(md_file)
        if d:
            md_dirs.add(d)

for dir_path in sorted(md_dirs):
    existing_index = os.path.join(sandbox_root, dir_path, "_INDEX.md")
    if os.path.exists(existing_index):
        continue  # Don't overwrite existing indexes

    index_result = neuraltree_generate_index(directory=dir_path, project_root=sandbox_root)
    if index_result.get("file_count", 0) > 0:
        write_file(os.path.join(sandbox_root, dir_path, "_INDEX.md"), index_result["index_content"])
        if not DEGRADED_MODE:
            viking_add_resource(uri=os.path.join(dir_path, "_INDEX.md"))

emit(f"  Generated {len(md_dirs)} index files")
```

**FRESHNESS strategy:**

```
# Update last_verified on files whose content is still accurate
for md_file in scan_result["files"]:
    if not md_file.endswith(".md"):
        continue
    content = read_file(os.path.join(sandbox_root, md_file))
    date_str = _parse_last_verified(content)

    # Only update if file has frontmatter but stale/missing date
    if "---" in content[:10]:  # has frontmatter
        # CLAUDE READS the file and judges: is the content still accurate?
        # If yes: update last_verified to today
        # If no: skip (content needs updating, not just date-stamping)
        update_frontmatter(md_file, {"last_verified": today_iso8601()})
```

**VIKING_INDEX strategy:**

```
# Index all .md files in Viking for semantic search.
# This is the #1 driver for precision_at_3 (25% of Flow Score).
# Requires Viking MCP (OpenViking) to be running.

if DEGRADED_MODE:
    emit("  VIKING_INDEX skipped — Viking unavailable (DEGRADED mode)")
else:
    md_files_to_index = [f for f in scan_result["files"] if f.endswith(".md")]
    indexed_count = 0
    for md_file in md_files_to_index:
        content = read_file(os.path.join(sandbox_root, md_file))
        viking_add_resource(uri=md_file, content=content)
        indexed_count += 1

    emit(f"  Indexed {indexed_count} files in Viking")

    # After indexing, re-run precision benchmark on a sample of queries
    # to measure the actual improvement in semantic retrieval
    sample_queries = baseline.get("queries", [])[:20]
    if sample_queries:
        precision_sum = 0.0
        for query in sample_queries:
            viking_result = viking_search(query=query["text"], limit=3)
            for result in viking_result.get("results", []):
                full_content = viking_read(uri=result["uri"])
                result["content"] = full_content[:2000]
            query["precision"] = llm_judge_precision(query)
            precision_sum += query["precision"]
        new_precision = precision_sum / len(sample_queries)
        emit(f"  Precision@3: {new_precision:.3f} ({len(sample_queries)} queries sampled)")
```

**RE_WIRE strategy:**

```
# After splits and Viking indexing created new files/connections, wire them.
# Targets: new files from SPLIT_LARGE + files that gained Viking neighbors.
all_leaf_paths = scan_result["files"]
rewire_targets = set()

for kept_entry in autoloop_state["kept"]:
    if kept_entry.get("strategy") == "SPLIT_LARGE":
        rewire_targets.update(kept_entry.get("new_files", []))

# Also wire any file that doesn't have ## Related yet
for md_file in scan_result["files"]:
    if not md_file.endswith(".md"):
        continue
    content = read_file(os.path.join(sandbox_root, md_file))
    if "## Related" not in content:
        rewire_targets.add(md_file)

for target in rewire_targets:
    wire_result = neuraltree_wire(
        file_path=target,
        all_leaf_paths=all_leaf_paths,
        project_root=sandbox_root
    )
    if wire_result.get("suggested_content"):
        apply_suggested_content(target, wire_result["suggested_content"])
```

#### Step 4: Measure

After executing the full strategy, re-score the entire project:

```
new_score = neuraltree_score(project_root=sandbox_root)
new_flow = new_score["flow_score_partial"]

# If not DEGRADED_MODE, re-run precision_at_3 via Viking benchmark
if not DEGRADED_MODE:
    # Re-run Viking search on affected queries and LLM judge
    # (same as Section 4 Step 2-3, but only for queries related to changed files)
    new_precision = llm_judge_precision_batch(affected_queries)
    new_flow = new_score["flow_score_partial"] + (new_precision * 0.25)

actual_delta = new_flow - current_flow_score
emit(f"  Strategy {strategy}: {current_flow_score:.3f} → {new_flow:.3f} ({actual_delta:+.3f})")
```

#### Step 5: Decide — KEEP or DISCARD

```
if actual_delta > 0.01:  # Meaningful improvement
    # KEEP — the strategy worked
    current_flow_score = new_flow
    latest_metrics = new_score["metrics"]
    autoloop_state["kept"].append({
        "strategy": strategy,
        "predicted_delta": predicted_delta,
        "actual_delta": actual_delta,
        "files_changed": wired_count or len(split_files) or len(md_dirs),
    })
    emit(f"  KEEP — delta {actual_delta:+.3f}")

elif actual_delta >= 0:
    # Marginal improvement — KEEP but note low impact
    current_flow_score = new_flow
    latest_metrics = new_score["metrics"]
    autoloop_state["kept"].append({
        "strategy": strategy,
        "predicted_delta": predicted_delta,
        "actual_delta": actual_delta,
        "note": "marginal",
    })
    emit(f"  KEEP (marginal) — delta {actual_delta:+.3f}")

else:
    # DISCARD — strategy made things worse, restore all .md files
    neuraltree_restore(files=["__ALL_MD__"], project_root=sandbox_root)
    autoloop_state["discarded"].append({
        "strategy": strategy,
        "predicted_delta": predicted_delta,
        "actual_delta": actual_delta,
    })
    emit(f"  DISCARD — delta {actual_delta:+.3f}, restored from backup")
```

#### Step 6: Calibrate and Learn

```
# Calibrate prediction model
neuraltree_update_calibration(
    predicted_delta=predicted_delta,
    actual_delta=actual_delta,
    project_root="."  # Always write to real project, not sandbox
)

# Record lesson
neuraltree_lesson_add(
    domain=strategy.lower(),
    lesson={
        "symptom": f"Strategy {strategy} on {scan_result.get('project_name', 'unknown')}",
        "root_cause": f"Predicted {predicted_delta:+.3f}, actual {actual_delta:+.3f}",
        "fix": f"{'KEEP' if actual_delta >= 0 else 'DISCARD'}: {strategy}",
        "key_file": "autoloop"
    },
    project_root="."  # Always write to real project, not sandbox
)
```

#### Step 7: Check Exit Conditions

```
autoloop_state["iteration"] += 1
autoloop_state["score_history"].append(current_flow_score)

# Convergence detection
if len(autoloop_state["score_history"]) >= 2:
    delta = abs(autoloop_state["score_history"][-1] - autoloop_state["score_history"][-2])
    if delta < 0.02:
        autoloop_state["convergence_counter"] += 1
    else:
        autoloop_state["convergence_counter"] = 0

exit_reason = None

if current_flow_score > 0.85:
    exit_reason = f"Healthy — Flow Score {current_flow_score:.3f} > 0.85"
elif autoloop_state["convergence_counter"] >= 2:
    exit_reason = f"Converged — 2 consecutive strategies with |delta| < 0.02"
elif autoloop_state["iteration"] >= autoloop_state["max_iterations"]:
    exit_reason = f"Hard cap — {autoloop_state['max_iterations']} strategies reached"

if exit_reason:
    emit(f"AutoLoop exit: {exit_reason}")
    break
```

### CONTENT_GAP Routing

Before the strategy loop begins, route CONTENT_GAP diagnoses directly to HOLD. These require user-provided content and cannot be auto-fixed by any strategy:

```
for d in diagnosis["diagnoses"]:
    if d["gap_type"] == "CONTENT_GAP":
        autoloop_state["held"].append({
            "failure": d,
            "gap_type": "CONTENT_GAP",
            "reason": "Content does not exist — user must provide",
            "suggested_path": d.get("fix", "TBD")
        })
```


### AutoLoop Summary

After exiting the loop, emit a structured summary:

```
kept_count = len(autoloop_state["kept"])
discarded_count = len(autoloop_state["discarded"])
iterations = autoloop_state["iteration"]
baseline_score = autoloop_state["score_history"][0]
final_score = autoloop_state["score_history"][-1]
delta = final_score - baseline_score

emit(f"AutoLoop complete — {exit_reason}")
emit(f"Strategies: {iterations}, KEEP: {kept_count}, DISCARD: {discarded_count}")
emit(f"Flow Score: {baseline_score:.3f} → {final_score:.3f} ({delta:+.3f})")
emit(f"Score curve: {' → '.join(f'{s:.3f}' for s in autoloop_state['score_history'])}")
```

**Strategy breakdown:**

```
if autoloop_state["kept"]:
    emit("KEPT strategies:")
    for k in autoloop_state["kept"]:
        emit(f"  ✓ {k['strategy']} — delta {k['actual_delta']:+.3f} ({k.get('files_changed', '?')} files)")

if autoloop_state["discarded"]:
    emit("DISCARDED strategies (rolled back):")
    for d in autoloop_state["discarded"]:
        emit(f"  ✗ {d['strategy']} — predicted {d['predicted_delta']:+.3f}, actual {d['actual_delta']:+.3f}")
```

### Degraded Mode Behavior

In degraded mode (no Viking), the AutoLoop skips Viking-dependent operations:

- **WIRE_ORPHANS** still works (wiring is structural, not semantic)
- **Viking re-indexing** is skipped in all strategies
- **precision_at_3** remains null — Flow Score uses degraded formula (capped at 0.75)
- **Fewer strategies may fire** — EMBEDDING_GAP fixes are impossible

```
if DEGRADED_MODE:
    emit("WARNING: AutoLoop in DEGRADED mode — Viking unavailable, semantic scoring disabled")
```

### Sandbox Finalization

After convergence (bootstrap/critical modes only):

```
if sandbox_root != ".":
    diff = neuraltree_sandbox_diff(project_root=".")
    emit(f"Sandbox changes: {diff['total_changes']} total ({len(diff['added'])} added, {len(diff['changed'])} changed)")
    emit("Approve sandbox changes? (approve / reject)")
    user_response = wait_for_user_input()
    if "approve" in user_response.lower():
        neuraltree_sandbox_apply(files=[f["path"] for f in diff["modified"] + diff["added"]], project_root=".")
        emit("Sandbox changes applied to real project.")
    neuraltree_sandbox_destroy(project_root=".")
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
        k.get("strategy", "") in query.get("source", "")
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

# Collect all files changed by kept strategies
for k in autoloop_state["kept"]:
    strategy = k.get("strategy", "")

    # Each strategy tracks which files it touched
    if strategy == "SPLIT_LARGE":
        modified_files.update(k.get("new_files", []))
    elif strategy in ("WIRE_ORPHANS", "RE_WIRE"):
        modified_files.update(k.get("wired_files", []))
    elif strategy == "INDEX_DIRS":
        modified_files.update(k.get("index_files", []))
    elif strategy == "VIKING_INDEX":
        pass  # Already indexed in Viking during execution

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

### Step 2b: Regenerate Index Files

After splits, moves, and wiring, directory contents may have changed. Use `neuraltree_generate_index()` to regenerate `_INDEX.md` files for any directory that was affected.

```
# Collect directories that had files added, removed, or split
affected_dirs = set()

# Collect affected directories from kept strategies
for k in autoloop_state["kept"]:
    for f in k.get("new_files", []) + k.get("wired_files", []) + k.get("index_files", []):
        d = os.path.dirname(f)
        if d:
            affected_dirs.add(d)

# Also check HELD FOCUS_GAP splits that were executed via pending actions
for h in autoloop_state["held"]:
    if h.get("gap_type") == "FOCUS_GAP" and h.get("target"):
        d = os.path.dirname(h["target"])
        if d:
            affected_dirs.add(d)

for dir_path in affected_dirs:
    if os.path.isdir(os.path.join(sandbox_root, dir_path)):
        index_result = neuraltree_generate_index(
            directory=dir_path,
            project_root=sandbox_root
        )
        if index_result.get("file_count", 0) > 0:
            index_path = os.path.join(dir_path, "_INDEX.md")
            write_file(os.path.join(sandbox_root, index_path), index_result["index_content"])
            # Re-index the new _INDEX.md in Viking
            if not DEGRADED_MODE:
                viking_add_resource(uri=index_path, content=index_result["index_content"])

if affected_dirs:
    emit(f"Phase 5/5: Regenerated _INDEX.md for {len(affected_dirs)} directories")
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

- **Size:** Aim for 20-80 lines per leaf (ideal). Files >500 lines trigger FOCUS_GAP (autoloop split threshold). Trunks (_INDEX.md, MEMORY.md) under 100 lines.
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
        # Carry the split_plan from neuraltree_plan_split (computed in Section 6 Step 1b)
        pending_actions.append({
            "type": "SPLIT",
            "target": held.get("target", "unknown"),
            "reason": held["reason"],
            "split_plan": held.get("split_plan", []),
            "index_file": held.get("index_file"),
        })

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
            split_count = len(pa.get("split_plan", []))
            emit(f"  {i}. ⚠ SPLIT {pa['target']} → {split_count} files — {pa['reason']}")
            # Show proposed filenames for transparency
            for sp in pa.get("split_plan", [])[:5]:
                emit(f"       └─ {sp['filename']} ({sp['estimated_lines']} lines) — {sp['heading']}")
            if split_count > 5:
                emit(f"       └─ ... and {split_count - 5} more")
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
        # Use neuraltree_plan_move to compute all reference rewrites BEFORE moving
        archive_dest = os.path.join("archive", os.path.basename(action["target"]))
        move_plan = neuraltree_plan_move(
            source=action["target"],
            destination=archive_dest,
            project_root=project_root
        )
        if move_plan.get("error"):
            emit(f"  ERROR: {move_plan['error']} — skipping archive of {action['target']}")
            return

        # Execute the move
        archive_dir = os.path.join(project_root, "archive")
        os.makedirs(archive_dir, exist_ok=True)
        shutil.move(
            os.path.join(project_root, action["target"]),
            os.path.join(project_root, archive_dest)
        )

        # Apply all reference rewrites computed by plan_move
        for rewrite in move_plan.get("rewrites", []):
            file_content = read_file(os.path.join(project_root, rewrite["file"]))
            file_content = file_content.replace(rewrite["old_text"], rewrite["new_text"])
            write_file(os.path.join(project_root, rewrite["file"]), file_content)

        emit(f"  Archived {action['target']} → {archive_dest} ({len(move_plan.get('rewrites', []))} references updated)")

    elif action["type"] == "SPLIT":
        # Use the split_plan from Step 1b (already computed via neuraltree_plan_split)
        split_plan = action.get("split_plan", [])
        if not split_plan:
            emit(f"  No split plan available for {action['target']} — run neuraltree_plan_split() first.")
            return

        emit(f"FOCUS_GAP: {action['target']} → {len(split_plan)} focused leaves proposed:")
        for sp in split_plan:
            emit(f"    {sp['filename']} ({sp['estimated_lines']} lines) — {sp['heading']}")

        emit(f"  Execute this split? (yes / skip)")
        user_content = wait_for_user_input()
        if user_content.strip().lower() == "skip":
            return  # Deferred to next run

        # Execute the split: read original, write each section to its proposed file
        original_content = read_file(os.path.join(project_root, action["target"]))
        original_lines = original_content.splitlines()

        new_files = []
        for sp in split_plan:
            start = sp["start_line"] - 1  # convert 1-indexed to 0-indexed
            end = sp["end_line"]
            section_content = "\n".join(original_lines[start:end]) + "\n"
            write_file(os.path.join(project_root, sp["filename"]), section_content)
            new_files.append(sp["filename"])

        # Generate an index file for the split pieces
        split_dir = os.path.dirname(action["target"]) or "."
        index_result = neuraltree_generate_index(
            directory=split_dir,
            project_root=project_root
        )
        if index_result.get("index_content"):
            index_path = action.get("index_file") or os.path.join(split_dir, "_INDEX.md")
            write_file(os.path.join(project_root, index_path), index_result["index_content"])
            new_files.append(index_path)

        # Re-index all new files in Viking
        if not DEGRADED_MODE:
            for nf in new_files:
                full_path = os.path.join(project_root, nf)
                if os.path.exists(full_path):
                    viking_add_resource(uri=nf, content=read_file(full_path))

        # Check for references to the original file before removing it
        move_plan = neuraltree_plan_move(
            source=action["target"],
            destination=new_files[0] if new_files else action["target"],
            project_root=project_root
        )
        if move_plan.get("references_found", 0) > 0:
            emit(f"  WARNING: {move_plan['references_found']} files reference {action['target']}. Update them to point to the appropriate split file.")
            for rw in move_plan.get("rewrites", [])[:5]:
                emit(f"       └─ {rw['file']}:{rw['line']}")

        # Remove the original file — it has been replaced by split leaves
        original_path = os.path.join(project_root, action["target"])
        if os.path.exists(original_path):
            os.remove(original_path)

        emit(f"  Split {action['target']} → {len(new_files)} files. Original removed. Re-indexed in Viking.")
        return

    elif action["type"] == "CREATE":
        emit(f"CONTENT_GAP: What content should go in {action['target']}? Provide it now or type 'skip'.")
        user_content = wait_for_user_input()
        if user_content.strip().lower() == "skip":
            return  # Deferred to next run
        write_file(os.path.join(project_root, action["target"]), user_content)

        # Wire the new file with ## Related links to make it discoverable
        wire_result = neuraltree_wire(
            file_path=action["target"],
            all_leaf_paths=scan_result["files"],
            project_root=project_root
        )
        if wire_result.get("suggested_content"):
            apply_suggested_content(action["target"], wire_result["suggested_content"])

        # Index in Viking so semantic search finds it
        if not DEGRADED_MODE:
            viking_add_resource(uri=action["target"], content=user_content)

        emit(f"  Created {action['target']} (wired + indexed)")
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
