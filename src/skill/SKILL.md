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
