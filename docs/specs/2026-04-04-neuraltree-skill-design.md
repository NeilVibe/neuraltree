# /neuraltree — Universal Neural Organization Skill

> **Status:** Design Spec v5 — Final (4 rounds, 18 agents, all issues resolved)
> **Date:** 2026-04-04
> **Author:** Neil + Claude (collaborative design)
> **Target:** Any AI coding agent (Claude Code, Gemini CLI, Codex)

---

## 1. Vision

Organization is an **information retrieval problem for AI agents**. Agents forget not because they don't know, but because they can't FIND. Every project hits the same wall: flat memory dumps, unindexed docs, cluttered roots, no cross-references.

`/neuraltree` transforms any project into a neural tree — a structured information system where any fact is reachable in 0-2 hops, every node is wired to related nodes, and semantic search catches what structure misses.

### The Artery Principle (Soul of NeuralTree)

**It's NOT about disk space. It's about FLOW.**

The neural tree is an artery system. Information (blood) must flow cleanly from heart to extremities. The metric is not "how many MB freed" — it's:

1. **Synapse Quality** — does every connection lead somewhere alive? Dead synapses are blood clots.
2. **Hop Synergy** — trunk -> branch -> leaf. Each hop ADDS specificity, never repeats or confuses.
3. **Electrical Flow** — when reading a leaf, do its ## Related synapses fire toward the RIGHT next neuron?
4. **Trunk Pressure** — the trunk is the heart. If bloated (>100 lines), pressure drops, context fills with noise.

Cleanup is a side effect, not the goal. We delete dead files because dead neurons block signal flow. We wire ## Related because lateral synapses create alternative retrieval paths.

---

## 2. Architecture

### Three Components

```
/neuraltree (Skill) = THE BRAIN + SOLE ORCHESTRATOR
  |-- Artery Principle, investigation protocol, 0-1-2 hop rule
  |-- Orchestrates: Benchmark -> Diagnose -> AutoLoop -> Enforce
  |-- Spawns parallel investigation agents
  |-- Makes decisions (keep/archive/delete) based on evidence
  |-- Karpathy autoloop with prediction + measurement
  |-- ONLY component that calls Viking (clean ownership)
  |-- ONLY component that calls neuraltree-mcp tools

neuraltree-mcp (MCP Server) = THE MUSCLE (pure computation, no Viking calls)
  |-- neuraltree_scan()             Fast filesystem inventory
  |-- neuraltree_trace(path)        Reference tracing (grep all connections)
  |-- neuraltree_generate_queries() Auto-generate test queries from project context
  |-- neuraltree_score()            Compute structural metrics (4 of 6)
  |-- neuraltree_diagnose()         Classify failures by gap type
  |-- neuraltree_wire(file)         Auto-generate ## Related + ## Docs
  |-- neuraltree_predict()          Virtual backtest (simulate changes)
  |-- neuraltree_backup()/restore() Safe rollback (dedicated backup, NOT git stash)

Viking MCP = THE MEMORY (REQUIRED, called ONLY by skill)
  |-- Semantic search across all indexed content
  |-- Re-indexing after structural changes
  |-- The embedding field that catches fuzzy queries
  |-- Powered by Model2Vec (79x faster than SBERT)
```

**Ownership rule:** The Skill is the SOLE orchestrator. It calls neuraltree-mcp for filesystem work and Viking MCP for semantic work. The MCP server NEVER calls Viking directly — this prevents dual-access confusion and keeps the data flow as a clean DAG.

### Data Flow

```
User: "launch neuraltree"
  |
  v
Skill loads (Brain activates)
  |
  +--> Detect project state
  |    First time? --> Full setup pipeline (bootstrap if no CLAUDE.md/git)
  |    Existing tree? --> Health check mode
  |    Score dropped? --> Fix mode
  |
  +--> Acquire lock (.neuraltree/.lock) --> prevent concurrent runs
  +--> neuraltree_scan() --> filesystem inventory (capped at 10k files)
  +--> neuraltree_generate_queries() --> test queries from project context
  +--> Skill calls Viking for Precision@3 (LLM-as-judge relevance)
  +--> neuraltree_score() --> structural metrics
  +--> Skill computes composite Flow Score
  +--> Spawn investigation agents (3-5 parallel)
  +--> KARPATHY AUTOLOOP (max 10 iterations) until Flow Score > 0.85
  +--> neuraltree enforce --> install rules, re-index Viking
  +--> Release lock
  +--> Final report with before/after proof
```

---

## 3. The Neural Tree Pattern

### Structure (Universal)

```
TRUNK (always in context, <100 lines)
  |-- BRANCH indexes (_INDEX.md per semantic category)
  |     |-- LEAF files (focused, single-topic, 20-80 lines)
  |     |     |-- ## Related --> other leaves (SYNAPSES - lateral wiring)
  |     |     |-- ## Docs --> project source files (AXONS - downward wiring)
  |     |-- ...
  |-- ...
```

### The 0-1-2 Hop Rule

```
HOP 0: Always in context (auto-loaded)
  |-- MEMORY.md (trunk, <100 lines, links to everything)
  |-- CLAUDE.md / AGENTS.md / GEMINI.md (nav hub)
  |-- Rules files in .claude/rules/ (auto-injected)

HOP 1: One tool call away
  |-- _INDEX.md per domain (scannable routing switchboard)
  |-- Viking search (semantic fuzzy match)
  |-- Grep/Glob (exact match, known filename)

HOP 2: Two calls max
  |-- Leaf files (deep, focused, single-topic)
  |-- Source code files (pointed to by ## Docs)

NEVER HOP 3+. If anything requires 3+ hops, the structure is broken.
```

### Perfect Neuron (Leaf File) Format

```markdown
---
name: [topic name]
description: [one-line — used for relevance matching]
type: [user | feedback | project | reference]
last_verified: [YYYY-MM-DD]
---

## Content
[The actual knowledge — 20-80 lines, single topic]

## Related (SYNAPSES — lateral fire-together)
- [other_leaf.md](path) — why these fire together
- [another_leaf.md](path) — the connection

## Docs (AXONS — downward to source code)
- `path/to/source.py` — what it implements
- `path/to/config.json` — where it's configured
```

### Three Domains (Same Pattern)

| Domain | Trunk | Branches | Leaves |
|--------|-------|----------|--------|
| **Memory** | MEMORY.md | rules/, active/, reference/, archive/ | topic files with frontmatter |
| **Docs** | INDEX.md | architecture/, protocols/, reference/, guides/ | topic docs |
| **Project** | CLAUDE.md / README.md | server/, frontend/, scripts/, tests/ | source files |

---

## 4. Invocation Model

### Smart Single Entry + Subcommands

```
/neuraltree              Smart mode (detects state, does what's needed)
/neuraltree audit        Score only, no changes, read-only report
/neuraltree fix          Diagnose + fix + re-score loop
/neuraltree enforce      Install rules + session protocol
/neuraltree benchmark    Generate queries + full scoring report
/neuraltree auto         Full Karpathy autoloop until converged
```

**Default behavior** (`/neuraltree` or "launch neuraltree"):
- First time on project? --> Full pipeline (benchmark -> diagnose -> autoloop -> enforce)
- Tree exists, >7 days since last run? --> Health check (benchmark -> fix if needed)
- Tree exists, <7 days? --> Quick spot-check (run critical queries only)
- Score below threshold? --> Auto-fix mode

---

## 5. The Scoring System

### Six Metrics

| Metric | What It Measures | Scoring (0.0 - 1.0) | Ground Truth |
|--------|-----------------|---------------------|--------------|
| **Hop Efficiency** | Standardized tree walk: trunk -> index -> leaf | 0 hops=1.0, 1=0.9, 2=0.7, 3+=0.3 | Deterministic path: always walk trunk->index->leaf. Not agent-dependent. |
| **Precision@3** | Of top 3 Viking results, how many relevant? | 3/3=1.0, 2/3=0.67, 1/3=0.33 | **LLM-as-judge:** For each result, the agent evaluates "Given query Q and result R, is R relevant? yes/no" with a structured prompt. Adds 1 LLM call per result but makes the metric real. |
| **Synapse Coverage** | % of files with ## Related pointing to alive targets | wired/total | Deterministic: grep for "## Related" + verify targets exist. |
| **Dead Neuron Ratio** | Files with zero inbound references | 1 - (orphans/total) | Deterministic: for each file, grep project for references to its name. |
| **Freshness** | % of files with last_verified within 30 days | fresh/total | Deterministic: parse frontmatter dates. |
| **Trunk Pressure** | Trunk line count vs 100-line cap | <80=1.0, <100=0.8, >100=0.3 | Deterministic: `wc -l`. |

### LLM-as-Judge for Precision@3

```
For each test query Q:
  results = viking_search(Q, limit=3)
  for each result R in results:
    relevance = agent_judge(
      "RELEVANCE JUDGMENT\n"
      "Query: {Q}\n"
      "Result file: {R.filename}\n"
      "Result content (first 50 lines): {R.content}\n\n"
      "Rubric: Would reading this file help answer the query?\n"
      "- YES if the file contains information directly useful for answering\n"
      "- NO if the file is unrelated or only tangentially mentions the topic\n\n"
      "Reply YES or NO only."
    )
    # Handle malformed responses: anything not starting with "YES" = NO
    score += 1 if relevance.strip().upper().startswith("YES") else 0
  precision = score / 3
```

Cost: ~3 LLM calls per query, ~90 calls for 30 queries. Fast with local Qwen3 or cheap with Haiku.
Malformed response handling: Default to NO (conservative — doesn't inflate scores).

### Flow Score (Composite)

```
Flow Score = (
    hop_efficiency * 0.25 +
    precision_at_3 * 0.25 +
    synapse_coverage * 0.20 +
    dead_neuron_ratio * 0.15 +
    freshness * 0.10 +
    trunk_pressure * 0.05
)
```

Weights prioritize RETRIEVAL (hop + precision = 50%) over STRUCTURE (synapse + dead = 35%) over MAINTENANCE (freshness + trunk = 15%).

### Query Scaling

Query count scales with project size:
```
query_count = max(20, min(50, indexed_docs / 3))
```
- Small project (30 docs): 20 queries (minimum)
- Medium project (90 docs): 30 queries
- Large project (150+ docs): 50 queries (maximum)

### Thresholds

| Flow Score | Status | Action |
|------------|--------|--------|
| 0.90+ | Excellent | Spot-check only |
| 0.75-0.89 | Healthy | Minor fixes |
| 0.60-0.74 | Degraded | Autoloop recommended |
| <0.60 | Critical | Full pipeline required |

---

## 6. Karpathy Autoresearch AutoLoop

### The Core Loop

```
PHASE 1: BENCHMARK (beginning, read-only)
  Generate 20-30 test queries from:
    - CLAUDE.md / MEMORY.md / AGENTS.md (project context)
    - Recent git log (last 30 days of work)
    - Existing _INDEX.md files (known topics)
  Run each query:
    - Viking search --> Precision@3
    - Tree walk (trunk -> index -> leaf) --> Hop count
    - Grep fallback --> Coverage gap detection
  Result: Baseline Flow Score

PHASE 2: DIAGNOSE (read-only)
  For each failed query, classify:
    - CONTENT GAP:   No file covers this topic
    - EMBEDDING GAP: File exists but Viking can't find it
    - SYNAPSE GAP:   File exists, no cross-refs lead to it
    - FRESHNESS GAP: File exists but content is stale/wrong
    - FOCUS GAP:     Answer buried in 500+ line file (needs splitting)

PHASE 3: KARPATHY AUTOLOOP (iterative, reversible, max 10 iterations)
  For each failure (highest predicted impact first):
    1. PREDICT (virtual backtest, no file changes)
       - Calculate expected score improvement
       - Use calibration weights from past runs
       - Confidence = f(simulatable_metrics / total_metrics, calibration_accuracy)
    2. BACKUP (neuraltree_backup() — dedicated backup dir, NOT git stash)
       - Copies affected files to .neuraltree/.tmp/backup/
       - Never touches user's git stash or working tree
    3. EXECUTE
       - Apply the fix (add wire, re-index, split, update)
    4. MEASURE (real score via LLM-as-judge + structural metrics)
       - Re-run the same failing queries
       - Compare actual vs predicted improvement
    5. KEEP / HOLD / DISCARD (three-tier decision)
       - Actual >= Predicted * 0.8? --> KEEP (commit the change)
       - 0.5 <= Actual/Predicted < 0.8? --> HOLD (keep in place, add to "Needs Review"
         section of final report. Auto-promoted to first check in next run.)
       - Actual < Predicted * 0.5? --> DISCARD (neuraltree_restore())
    6. UPDATE calibration weights with prediction accuracy
    7. DEDUP CHECK: Track attempted {gap_type, target} pairs.
       If same gap_type+target was attempted before, skip (novelty guard).
       Prevents re-attempting the same fix class that already failed.

  Confidence formula for predictions:
    confidence = (simulatable_metric_count / 6) * calibration_accuracy
    Where calibration_accuracy starts at 0.5 (no data) and converges
    toward actual prediction accuracy over runs. Stored in calibration.json.

  Oscillation damping:
    - "No improvement" = |delta| < 0.02 (tolerance band)
    - Requires 3 consecutive iterations with |delta| < 0.02 to declare convergence
    - Track score direction: if score alternates up/down for 3 iterations, stop

  Exit when:
    - Flow Score > 0.85 (healthy), OR
    - 3 consecutive iterations with |delta| < 0.02 (converged), OR
    - 10 iterations reached (hard cap), OR
    - All diagnosed failures addressed (or skipped via dedup guard)

PHASE 4: EXECUTION REPORT (autoloop output — NOT auto-executed)
  The autoloop produces a COMPLETE ACTION PLAN with proofs.
  NOTHING destructive is executed automatically.
  
  The report contains:
  - Before/after Flow Score with full metric breakdown
  - SAFE ACTIONS (already executed during autoloop):
    - Wiring added (## Related, ## Docs) — non-destructive, reversible
    - Indexes created/updated (_INDEX.md) — non-destructive
    - Viking re-indexed — non-destructive
    - Frontmatter updated (last_verified) — non-destructive
  - PENDING ACTIONS (require user approval):
    - DELETE: files/dirs to remove (with trace() proof of zero refs)
    - ARCHIVE: files to move to archive (with staleness proof)
    - MOVE: files to relocate (with reference update plan)
    - SPLIT: large files to decompose (with proposed split plan)
    - Each action includes: target, reason, proof, what would break if wrong
  - NEEDS REVIEW: HOLD items from autoloop (partial improvement)
  - Calibration accuracy + next run ETA
  
  User reviews the report, then says "execute" or picks specific actions.
  Only THEN are destructive actions performed.

PHASE 5: ENFORCE (after user approval)
  - Execute approved destructive actions
  - Install .claude/rules/neuraltree.md (enforcement rule)
  - Re-index all changed files in Viking
  - Graduate training data (see Data Lifecycle)
  - Final confirmation: "Done. {N} actions executed. Flow Score: {before} -> {after}."
```

### Virtual Backtest (Prediction)

| Metric | Can Simulate? | How |
|--------|--------------|-----|
| Synapse Coverage | YES | Count wired + planned wires / total |
| Dead Neuron Ratio | YES | Count orphans - planned index additions |
| Trunk Pressure | YES | Current lines +/- planned changes |
| Hop Efficiency | ESTIMATE | Adding index = predicted -1 hop |
| Precision@3 | NO | Needs actual Viking re-index |
| Freshness | YES | Check dates + planned updates |

Prediction serves PRIORITIZATION (which fix to try first).
Real measurement serves DECISION (keep or discard).

### Sandbox Virtualization (Full Isolation)

For maximum safety, the autoloop can run in a **fully isolated sandbox**:

```
SANDBOX MODE (--sandbox flag or auto-detected on first run):
  1. Create isolated copy:
     - Git worktree: `git worktree add .neuraltree/sandbox neuraltree-sandbox`
     - OR if no git: rsync memory/ + docs/ + CLAUDE.md to .neuraltree/sandbox/
  2. Run ENTIRE autoloop on the sandbox copy
     - All wiring, splitting, archiving happens in the sandbox
     - Score measured on sandbox state
     - Viking indexes sandbox files with `sandbox/` URI prefix:
       `viking_add_resource(file, "sandbox/memory/rules/coding.md")`
       After sandbox destroyed, remove sandbox/ entries from Viking.
       This prevents pollution of the real index while enabling
       real Precision@3 measurement on sandbox state.
  3. Generate diff report:
     - Compare sandbox vs original (file-by-file diff)
     - Show exactly what would change
     - Include Flow Score: original vs sandbox
  4. User reviews diff, approves
  5. Apply approved changes from sandbox to real project
  6. Clean up sandbox (delete worktree)
```

**Benefits:**
- Zero risk to real project during autoloop
- Full Karpathy iteration with real file modifications (not just predictions)
- Precision@3 measured on ACTUAL re-indexed files (not simulated)
- User sees a complete before/after diff, not a prediction
- Git worktree is native, lightweight, and isolated

**When to use sandbox:**
- First run on any project (unknown state = higher risk)
- When Flow Score < 0.60 (critical = many changes expected)
- When user requests maximum safety

**When to skip sandbox:**
- Health checks on healthy trees (score > 0.85, few changes expected)
- Repeat runs where calibration accuracy > 0.90 (predictions are reliable)

---

## 7. Investigation Protocol

### Trace Before Prune

Before recommending ANY delete/archive/move:

```
1. SCAN   -- what exists? (dirs, files, sizes, dates)
2. TRACE  -- what references this? (configs, CI, imports, memory, docs)
3. INVESTIGATE -- Viking search + memory check + config grep
4. UNDERSTAND  -- WHY does this exist? Connected to something alive?
5. DECIDE -- only NOW can you say keep/archive/delete
```

### Always Show Both Sides

Every cleanup report MUST show:

```
DELETED (with proof):
  .swarm/ -- 0 refs, Ruflo dead, 2.4MB
  archive/old_builds/ -- 0 refs, ancient v1.0.0, 75MB

KEPT (with proof):
  .agents/skills/ -- 18 symlinks active, .claude/skills/ depends on it
  ui-ux-pro-max/ -- 14KB SKILL.md, git-tracked, resolves in 1 hop
```

The KEPT list prevents "did you accidentally delete X?" anxiety.

### Parallel Investigation Agents

For complex audits, spawn 3-5 investigation agents in parallel:
- Each agent investigates a specific target/directory
- Each traces all wiring independently
- Skill synthesizes findings into unified report
- User approves before any destructive action

---

## 8. Data Lifecycle

### Three-Tier State

```
.neuraltree/                      (gitignored, local to machine)
|-- .lock                         LOCK: prevents concurrent runs
|-- state.json                    PERSISTENT: Flow Score, last run, config
|-- queries.json                  PERSISTENT: test queries (evolve each run)
|-- calibration.json              PERSISTENT: prediction accuracy weights
|-- history/                      HISTORY: compressed run summaries
|   |-- 2026-04-04.json           "0.58->0.91, 23 fixes, 4 iterations"
|   |-- 2026-04-11.json           "0.89->0.93, 2 fixes, 1 iteration"
|-- .tmp/                         EPHEMERAL: autoloop working state
    |-- backup/                   File backups for rollback (NOT git stash)
    |-- iteration_003.json        Current loop state
    |-- predictions_buffer.json   Predicted vs actual tracking
    ^^^ ENTIRE .tmp/ DELETED after convergence
```

**Safety:**
- Uses dedicated backup directory, never git stash. User's working tree and stash are never touched.
- Lock file uses atomic creation (`O_CREAT|O_EXCL` or equivalent) to prevent race conditions.
- Backup is retained until NEXT successful run (not wiped immediately after convergence).
  This means the user can verify results and roll back even after the session ends.
  Only the NEXT run's backup phase cleans the previous backup.
- Size cap: backup dir capped at 100MB. If exceeded, warn and skip backing up large files.
- neuraltree_trace() uses grep which has known false-negative risks:
  dynamic imports, template strings, YAML anchors, env-var references.
  The execution report flags this: "trace() coverage: grep-based. Dynamic references may be missed.
  Review PENDING ACTIONS carefully before approving deletes."

### Graduation Protocol (After Convergence)

```
1. Merge .tmp/ prediction accuracy into calibration.json
2. Refine queries.json:
   - Always-pass queries --> demote to spot-check
   - Caught-real-issues queries --> promote to critical
   - New project areas --> generate new queries
3. Compress run to history/ (one-liner JSON)
4. Update state.json (new Flow Score + timestamp)
5. DELETE .tmp/ entirely
```

### Query Evolution

```
Run 1: 30 fresh queries, 15 fail --> all fixed
Run 2: 30 veteran + 5 new, 5 fail --> fixed
Run 3: 30 veteran (spot-check) + 10 active + 3 new, 1 fail
Run N: Mostly spot-checks, very fast, only new queries scored fully
```

System gets FASTER over time. Healthy queries are cheap spot-checks. Only new/failing queries get full scoring.

---

## 9. neuraltree-mcp (MCP Server Spec)

### Technology

- **Language:** Python (FastMCP)
- **Transport:** stdio (Claude Code standard)
- **Dependencies:** fastmcp, pathlib, json, subprocess (for git). NO httpx — MCP never calls Viking directly.

### Tools (13 tools — single-responsibility)

```python
@mcp.tool()
async def neuraltree_scan(path: str = ".", max_files: int = 10000) -> dict:
    """Fast filesystem inventory with scale cap.
    Returns: {dirs: [...], files: [...], sizes: {...}, dates: {...},
              empty_dirs: [...], total_count: int, capped: bool}
    Scans memory/, docs/, project root. Counts files per dir.
    Stops at max_files to prevent OOM on huge repos."""

@mcp.tool()
async def neuraltree_trace(target: str) -> dict:
    """Trace ALL references to a file/directory.
    Greps: CI workflows, configs, imports, docs, memory, scripts.
    Handles permission errors gracefully (reports, doesn't crash).
    Returns: {referenced_by: [...], references_to: [...], is_alive: bool,
              permission_errors: [...]}"""

@mcp.tool()
async def neuraltree_generate_queries(
    claude_md_path: str | None = None,
    memory_md_path: str | None = None,
    index_paths: list[str] | None = None,
    git_log_lines: int = 100,
    indexed_doc_count: int = 30
) -> dict:
    """Auto-generate test queries from project context.
    
    Query generation strategies:
      1. CLAUDE.md glossary: extract terms -> "What is {term}?"
      2. CLAUDE.md nav table: extract links -> "How does {topic} work?"
      3. MEMORY.md sections: extract leaf names -> "What do we know about {topic}?"
      4. _INDEX.md files: extract entries -> "Where is {topic} documented?"
      5. git log subjects: extract nouns -> "What changed with {feature}?"
         Filter out: CI triggers, version bumps, merge commits, "chore:" prefixes
    
    Query count: max(20, min(50, indexed_doc_count / 3))
    
    Returns: {
      queries: [{text: str, source: str, category: "what_is"|"how_does"|"where_is"|"what_changed"}],
      sources: {claude_md: int, memory: int, indexes: int, git: int},
      total: int
    }"""

@mcp.tool()
async def neuraltree_score(
    predicted_changes: list[dict] | None = None
) -> dict:
    """Compute structural metrics (4 of 6).
    Computes: synapse_coverage, dead_neuron_ratio, freshness, trunk_pressure.
    Does NOT compute hop_efficiency or precision_at_3 (those need Viking/LLM,
    handled by the skill orchestrator).
    If predicted_changes provided, simulates their impact without file changes.
    
    Returns: {
      metrics: {
        synapse_coverage: float,    # 0.0-1.0
        dead_neuron_ratio: float,   # 0.0-1.0 (1.0 = no orphans)
        freshness: float,           # 0.0-1.0
        trunk_pressure: float       # 0.0-1.0
      },
      structural_score: float,      # weighted combo of above 4
      orphan_files: [str],          # files with zero inbound refs
      unwired_files: [str],         # files missing ## Related
      stale_files: [str],           # files with old last_verified
      trunk_lines: int
    }"""

@mcp.tool()
async def neuraltree_diagnose(failures: list[dict]) -> dict:
    """Classify query failures by gap type.
    
    Input schema: [{
      query: str,                   # the test query
      found_file: str | None,       # file that SHOULD answer it (None = unknown)
      hop_count: int,               # hops taken to find it (-1 = not found)
      viking_hit: bool,             # did Viking top-3 include the right file?
      viking_rank: int | None,      # rank in Viking results (1-3 or None)
      file_line_count: int | None   # line count of found_file
    }]
    
    Classification rules:
      - found_file=None + viking_hit=False           -> CONTENT_GAP
      - found_file exists + viking_hit=False          -> EMBEDDING_GAP  
      - found_file exists + hop_count > 2             -> SYNAPSE_GAP
      - found_file exists + last_verified > 30 days   -> FRESHNESS_GAP
      - found_file exists + file_line_count > 500     -> FOCUS_GAP
    
    Returns: {
      content_gaps: [{query, suggestion: str}],
      embedding_gaps: [{query, file: str, action: "re-index"}],
      synapse_gaps: [{query, file: str, missing_from_index: str}],
      freshness_gaps: [{query, file: str, last_verified: str}],
      focus_gaps: [{query, file: str, line_count: int, split_suggestion: str}]
    }"""

@mcp.tool()
async def neuraltree_wire(file_path: str, all_leaf_paths: list[str] | None = None) -> dict:
    """Auto-generate ## Related and ## Docs for a leaf file.
    
    Relatedness algorithm (no Viking needed — pure filesystem):
      1. Extract keywords from target file (split on whitespace, filter stopwords,
         keep words appearing 2+ times = topic words)
      2. For each other leaf file in all_leaf_paths:
         - Extract its keywords the same way
         - Compute Jaccard similarity: |intersection| / |union|
           Guard: if |union| == 0, similarity = 0.0 (both files empty after filtering)
         - Score > 0.15 = candidate for ## Related
      3. Boost score if files share ## Docs targets (same source file = strong signal)
      4. Boost score if files are in same branch (same _INDEX.md parent)
      5. Top 3 candidates become ## Related entries
    
    Docs algorithm:
      1. Extract file paths mentioned in content (backtick paths, markdown links)
      2. Grep project for references TO this file from source code
      3. Both directions = ## Docs candidates
    
    Returns: {
      related: [{file: str, score: float, reason: str}],
      docs: [{file: str, direction: "references"|"referenced_by"}],
      suggested_content: str   # ready-to-append ## Related + ## Docs markdown
    }"""

@mcp.tool()
async def neuraltree_predict(changes: list[dict]) -> dict:
    """Virtual backtest: predict score impact of proposed changes.
    Input: [{action: 'add_wire', target: 'file.md', value: '...'}]
    Uses calibration.json weights for accuracy adjustment.
    Confidence = f(simulatable_metrics_coverage, calibration_accuracy)
    Returns: {predicted_delta: +0.13, confidence: 0.87, breakdown: {...}}"""

@mcp.tool()
async def neuraltree_backup(files: list[str]) -> dict:
    """Backup files before autoloop changes. Dedicated backup dir, NOT git stash.
    Copies to .neuraltree/.tmp/backup/ with original paths preserved.
    Returns: {backed_up: [...], backup_dir: str}"""

@mcp.tool()
async def neuraltree_restore(files: list[str] | None = None) -> dict:
    """Restore files from backup after a DISCARD decision.
    If files=None, restores ALL backed up files.
    Returns: {restored: [...]}"""

@mcp.tool()
async def neuraltree_sandbox_create(method: str = "auto") -> dict:
    """Create isolated sandbox for autoloop backtesting.
    
    Fallback chain (method='auto'):
      1. Try git worktree add .neuraltree/sandbox (preferred, lightweight)
         - Fails if: no git, dirty index, detached HEAD, branch collision
      2. If worktree fails: rsync memory/ + docs/ + CLAUDE.md + .neuraltree/
         - Works without git, copies only organization-relevant files
      3. If rsync fails (permissions, disk space): abort with clear error
    
    TTL: Sandbox auto-cleaned after 24h if not explicitly destroyed.
    Also cleaned on next neuraltree invocation if previous sandbox exists.
    
    Returns: {sandbox_path: str, method: 'worktree'|'rsync', files_copied: int,
              ttl_expires: str}"""

@mcp.tool()
async def neuraltree_sandbox_diff() -> dict:
    """Compare sandbox state vs real project. File-by-file diff.
    Categorizes changes into: added, modified, deleted, moved.
    For each change, shows the actual diff content (first 50 lines).
    Returns: {
      added: [{path: str, lines: int}],
      modified: [{path: str, diff_preview: str, lines_changed: int}],
      deleted: [{path: str, reason: str}],
      moved: [{from: str, to: str}],
      summary: {total_changes: int, safe_count: int, pending_count: int}
    }"""

@mcp.tool()
async def neuraltree_sandbox_apply(actions: list[dict]) -> dict:
    """Apply approved changes from sandbox back to real project.
    Input: [{action: 'delete'|'move'|'archive'|'split', source: str, dest: str|None}]
    Only executes actions explicitly approved by user.
    Returns: {applied: [...], skipped: [...], errors: [...]}"""

@mcp.tool()
async def neuraltree_sandbox_destroy() -> dict:
    """Clean up sandbox after use.
    Removes git worktree or rsync'd copy.
    Returns: {cleaned: bool, space_freed: str}"""
```

### Viking Integration (IMPORTANT: Skill-only)

The MCP server does NOT call Viking. All Viking operations go through the Skill:

```
Skill orchestrates:
  1. Calls neuraltree_generate_queries() --> gets test queries
  2. Calls viking_search(query) for each query --> gets top-3 results
  3. Runs LLM-as-judge on each result --> Precision@3
  4. Calls neuraltree_score(viking_results=...) --> structural metrics
  5. Skill computes composite Flow Score from both

After fixes:
  6. Skill calls viking_add_resource() to re-index changed files

This keeps Viking ownership clean. One owner = no confusion.
```

---

## 10. Skill (SKILL.md) Outline

The skill file instructs the AI agent HOW to think. Key sections:

```
1. ACTIVATION
   - Detect state: .neuraltree/state.json exists? -> returning run
     No state.json? -> first run (bootstrap mode)
     state.json.flow_score < 0.60? -> critical mode
     state.json.last_run > 7 days? -> health check mode
     state.json.last_run < 7 days + flow_score > 0.90? -> spot-check
   - Verify Viking MCP: try viking_search("test") — if fails, enter degraded mode
   - Verify neuraltree-mcp: try neuraltree_scan(".") — if fails, abort with error
   - Acquire .neuraltree/.lock (abort if locked, auto-remove if >1hr stale)

2. ARTERY PRINCIPLE
   - The soul rules (flow > storage, trace before prune, both-sides reporting)
   - 0-1-2 hop rule
   - Perfect neuron format (frontmatter + content + ## Related + ## Docs)
   - Cleanup is a side effect, not the goal

3. PROGRESS PROTOCOL
   Emit status after each major step:
   - "Phase 1/4: Scanning project... 847 files found"
   - "Phase 1/4: Generating test queries... 28 queries from 4 sources"
   - "Phase 1/4: Benchmarking... 12/28 queries scored"
   - "Phase 2/4: Diagnosing... 8 failures classified"
   - "Phase 3/4: AutoLoop iteration 2/10... Flow Score 0.58 -> 0.71"
   - "Phase 4/4: Enforcing rules, re-indexing Viking..."
   Time estimate: First run ~8-15min (100 files, local LLM). Subsequent: ~1-3min.

4. BENCHMARK PROTOCOL
   - Call neuraltree_generate_queries() -> test queries
   - For each query: call viking_search() -> top 3 results
   - For each result: LLM-as-judge with rubric (see Section 5)
   - Call neuraltree_score() -> structural metrics
   - Compute composite Flow Score
   - If score > 0.90 and spot-check mode: "Tree healthy. 28 queries spot-checked."

5. INVESTIGATION PROTOCOL
   - For each diagnosed failure, spawn investigation agent with prompt:
     "INVESTIGATE: Is {target} still needed? Trace all references.
      Check: CI workflows, configs, imports, memory, docs.
      Report: what it is, who references it, recommendation (keep/archive/delete)."
   - Max 5 parallel agents
   - Skill synthesizes findings into unified KEPT + DELETED + MODIFIED report
   - For destructive actions: always verify with neuraltree_trace() before executing

6. KARPATHY AUTOLOOP
   - Priority queue: sort failures by predicted impact (confidence * predicted_delta)
   - Dedup guard: track {gap_type, target} pairs — skip if attempted before
   - For each: predict -> backup -> execute -> measure -> keep/hold/discard
   - HOLD items: kept in place, listed in "Needs Review" report section,
     auto-promoted to first check in next run
   - Exit conditions: flow_score > 0.85 OR 3 consecutive |delta| < 0.02 OR 10 iterations
   - Graduate training data after convergence (see Data Lifecycle)

7. ENFORCEMENT
   - Install .claude/rules/neuraltree.md (organization rules for this project)
   - Session-start protocol: "Scan _INDEX.md files before action"
   - Weekly hygiene checklist in the rule file
   - Re-index all changed files in Viking

8. REPORTING (Final Output)
   Flow Score: 0.58 -> 0.91 (+0.33)
   ┌─────────────────────────────────────────────┐
   │ Metric              Before  After   Delta   │
   │ Hop Efficiency       0.45    0.88   +0.43   │
   │ Precision@3          0.33    0.87   +0.54   │
   │ Synapse Coverage     0.61    0.97   +0.36   │
   │ Dead Neuron Ratio    0.70    1.00   +0.30   │
   │ Freshness            0.80    0.95   +0.15   │
   │ Trunk Pressure       0.80    1.00   +0.20   │
   └─────────────────────────────────────────────┘
   
   KEPT (5 items):
     .agents/skills/ — 18 active symlinks, .claude/skills/ depends on it
     ui-ux-pro-max/ — 14KB SKILL.md, git-tracked
     ...
   
   DELETED (12 items):
     .swarm/ — 0 refs, dead Ruflo artifact, 2.4MB
     ...
   
   MODIFIED (8 items):
     memory/reference/lan_auth.md — added ## Related (3 synapses)
     memory/reference/build_types.md — added ## Docs (2 axons)
     ...
   
   NEEDS REVIEW (1 item):
     .planning/ cleanup — HOLD: partial improvement, review next run
   
   Calibration accuracy: 87% (predictions were 13% optimistic)
   AutoLoop: 4 iterations, 3 KEEP, 0 DISCARD, 1 HOLD
   Next run ETA: ~2min (tree is healthy, mostly spot-checks)
```

---

## 11. Edge Cases and Error Handling

### Bootstrap: No CLAUDE.md / No Git / Empty Project

| Scenario | Behavior |
|----------|----------|
| **No CLAUDE.md** | Skill creates a minimal CLAUDE.md nav hub from README.md or project structure |
| **No MEMORY.md** | Skill creates memory/ structure from scratch (trunk + empty branches) |
| **No git** | Backup uses file copy (not git stash). Warn: "No git — changes are harder to revert" |
| **Empty project** | Generate queries from directory names + filenames only. Score = 0.0. Full bootstrap pipeline. |
| **Monorepo** | Detect multiple CLAUDE.md / package.json. Scope to current working directory. Warn about cross-boundary wiring. |

### Scale Limits

| Parameter | Limit | Behavior at Limit |
|-----------|-------|-------------------|
| File scan | 10,000 files | Stop scan, warn "Large project — sampling mode enabled" |
| Test queries | 50 max | Cap at 50 regardless of project size |
| Autoloop iterations | 10 max | Hard stop, report partial results |
| Leaf file size | 500 lines | Flag as FOCUS GAP (needs splitting) |
| Trunk size | 100 lines | Flag as TRUNK PRESSURE issue |

### Error Handling

| Error | Recovery |
|-------|----------|
| **Viking MCP down** | Degrade to structure-only mode. Disable Precision@3. Warn user. |
| **neuraltree-mcp crash** | Skill reports error, suggests restart. No data corruption (.lock prevents partial writes). |
| **Permission denied** on file | Report in trace() results as `permission_errors`. Skip file, don't crash. |
| **Dirty working tree** | neuraltree_backup() copies files to .tmp/backup/, never touches git state. |
| **Concurrent run** | .lock file detected → "Another neuraltree run is active. Aborting." |
| **Stale .lock** (crashed previous run) | If .lock older than 1 hour, auto-remove and warn. |

### Migration: Existing Organized Projects

If .neuraltree/state.json already exists (previous run):
- Skip bootstrap, load existing queries + calibration
- Run benchmark with existing + new queries (from recent git)
- Only fix new failures (veteran queries skip full scoring)

If project is already organized but no .neuraltree/ (manual org):
- Benchmark detects existing structure (indexes, cross-refs)
- Score likely starts at 0.60-0.80 (partial organization)
- Autoloop fills the gaps rather than rebuilding from scratch

---

## 12. Platform Compatibility

### Target Platforms (Phase 4 — deferred, not blocking)

| Platform | Skill Loading | MCP Support | Agent Spawning |
|----------|--------------|-------------|---------------|
| **Claude Code** | Skill tool | Full MCP | Agent tool |
| **Gemini CLI** | activate_skill | MCP via config | Subagent support |
| **Codex** | Skill equivalent | MCP support varies | Task spawning |
| **Copilot CLI** | skill tool | MCP via config | Agent equivalent |

### Platform Detection

```python
# In neuraltree-mcp or skill preamble
def detect_platform() -> str:
    if "CLAUDE_CODE" in env or skill loaded via Skill tool:
        return "claude-code"
    if "GEMINI_CLI" in env or skill loaded via activate_skill:
        return "gemini-cli"
    return "generic"  # fallback: sequential, no agent spawning
```

### Adaptation

- **Claude Code:** Agent tool for parallel investigation, MCP tools directly
- **Gemini CLI:** Equivalent agent spawning, adapted tool names per `references/copilot-tools.md`
- **Generic fallback:** Run investigations sequentially (slower but functional)

### Without Viking (Degraded Mode)

If Viking MCP is not detected:
- Skill warns: "Viking not found. Operating in structure-only mode (4 of 6 metrics)."
- Tree navigation works (indexes, cross-refs, filenames)
- Precision@3 metric disabled (no embeddings) — weight redistributed to structural metrics
- Hop Efficiency measured by structure only (not semantic search)
- Skill suggests Viking installation for full power
- In degraded mode, hop_efficiency is measured as "standardized tree walk WITHOUT
  semantic fallback": for each query, walk trunk -> _INDEX.md -> leaf using filename
  matching only. Count hops. Score same as normal mode (0=1.0, 1=0.9, 2=0.7, 3+=0.3).
  Without Viking, queries that rely on fuzzy semantic matching will score poorly —
  this correctly penalizes trees that depend on embeddings instead of clean structure.
- Since hop_efficiency and synapse_coverage both measure structure in this mode, they
  overlap. Merge into single "structure_reachability" metric at 0.45 weight:
  `structure_reachability = (hop_efficiency + synapse_coverage) / 2`
- Recalculated weights: structure_reachability 0.45, dead_neuron 0.25, freshness 0.20, trunk 0.10

---

## 13. Implementation Plan (High-Level)

### Phase 1: MCP Server Core (neuraltree-mcp) — ~3 days
Build the muscle. Python FastMCP server, filesystem tools first.
- Day 1: scan(), trace(), backup(), restore() — pure filesystem ops
- Day 2: wire() with Jaccard keyword similarity, generate_queries() with 5 extraction strategies
- Day 3: score() structural metrics, diagnose() gap classification
- Day 3 SPIKE: LLM-as-judge proof-of-concept (riskiest assumption)
  - Run 5 test queries against Viking, judge relevance with Qwen3/Haiku
  - Validate: does the rubric produce consistent YES/NO? Is latency acceptable?
  - If LLM-as-judge fails: design fallback (keyword overlap scoring)
- Test each tool independently against LocaNext project

### Phase 2: Sandbox + Prediction Engine — ~2 days
Build the virtualization layer and prediction tools.
- Day 1: Sandbox creation (git worktree or rsync), namespace isolation for Viking
  - `neuraltree_sandbox_create()` → creates isolated copy (fallback chain)
  - `neuraltree_sandbox_diff()` → compares sandbox vs real project
  - `neuraltree_sandbox_apply()` → merges approved changes back
  - `neuraltree_sandbox_destroy()` → cleanup (+ TTL auto-cleanup)
- Day 2: predict() with calibration weights, .neuraltree/ state persistence
  - calibration.json read/write, confidence formula implementation
  - Integration test: predict on sandbox, verify against actual

### Phase 3: Skill + Karpathy AutoLoop — ~4 days
Build the brain. The SKILL.md orchestrator + autoloop intelligence.
- Day 1: SKILL.md activation logic, state detection, Viking/MCP verification
  - Smart mode: first-run vs health-check vs spot-check vs critical
  - Lock file acquisition (atomic), progress protocol
- Day 2: Benchmark protocol
  - Query generation → Viking search → LLM-as-judge (Precision@3)
  - Structural scoring via neuraltree_score()
  - Composite Flow Score computation
- Day 3: Karpathy autoloop running in SANDBOX
  - Priority queue (confidence * predicted_delta)
  - Dedup guard, oscillation damping (3 consecutive |delta| < 0.02)
  - Keep/Hold/Discard decisions with proof collection
  - Sandbox iteration: modify sandbox → re-score → decide
- Day 4: Execution report generation + enforcement
  - SAFE ACTIONS (already done) + PENDING ACTIONS (need approval) format
  - KEPT/DELETED/MODIFIED/NEEDS REVIEW lists with proofs
  - User approval gate → execute → enforce rules → re-index Viking
  - Calibration graduation, query evolution, history compression

### Phase 4: Hardening — ~2 days
Edge cases, error handling, scale limits, security.
- Day 1: Bootstrap (no CLAUDE.md, no git, empty project, monorepo)
  - Permission handling, scale caps (10k files, 50 queries, 10 iterations)
  - Backup retention policy (kept until next run, 100MB cap)
- Day 2: Concurrent run protection, stale lock cleanup
  - trace() false-negative disclosure in reports
  - Degraded mode (no Viking): merged structure_reachability metric
  - End-to-end test: run on LocaNext, verify Flow Score matches manual audit

### Phase 5: Platform Adaptation — DEFERRED
Test on Gemini CLI, Codex. Add fallback modes.
Not blocking. Ship Claude Code + Viking first.

### Phase 6: Distribution — ~1 day
Package as installable skill.
- README with quick start (one-command install)
- Installation script (copies SKILL.md + registers MCP in ~/.claude.json)
- Example output from LocaNext case study (before/after proof)
- Viking setup guide link

### Total: ~12 days (Phases 1-4), Phase 5 deferred, Phase 6 = 1 day
### Tools: 13 (9 core + 4 sandbox)

---

## 14. Success Criteria

| Criteria | Target |
|----------|--------|
| Any project goes from unorganized to Flow Score >0.85 | In one `/neuraltree auto` session (sandbox + approval) |
| Information reachable in 0-2 hops | 95% of test queries |
| Zero breakage from cleanup | All deletes verified with trace() |
| Autoloop converges | Within 10 iterations |
| System gets faster over time | Run N+1 faster than Run N |
| Works on any AI agent | Claude Code + at least 1 other |

---

## 15. Proven Patterns (LocaNext Case Study)

This entire design was proven on the LocaNext project (2026-04-04):

- **Memory:** 154 flat files -> 28 in neural tree (82% reduction)
- **MEMORY.md:** 387 lines -> 70 lines (always fits in context)
- **Feedback rules:** 61 scattered -> 6 domain files
- **All leaves wired:** 28/28 have ## Related + ## Docs
- **5 _INDEX.md switchboards:** rules/, active/, reference/, archive/ + trunk
- **Viking indexed:** All files searchable, top result correct for test queries
- **Investigation agents:** 5 parallel agents audited 644+ files in .planning/, .claude/, archive/
- **Cleanup:** ~165MB freed, zero breakage, all deletes verified with grep
- **Before/after reporting:** KEPT + DELETED lists on every operation

---

---

## 16. Review History

### Round 1 (4 agents)
| Reviewer | Score | Key Fix Applied |
|----------|-------|----------------|
| Architecture | 7/10 | Split Viking ownership to skill-only. Split benchmark() into 3 tools. |
| Scoring | 6/10 | Added LLM-as-judge for Precision@3. Fixed dead zone. Added oscillation damping. |
| Feasibility | 7/10 | Merged Phase 2+3. Deferred Phase 4. Identified LLM-as-judge as critical. |
| Completeness | 7/10 | Added Section 11 (edge cases, error handling, bootstrap, scale limits). |

All 8 critical issues resolved in v2.

### Round 2 (5 agents)
| Reviewer | Score | Key Fix Applied |
|----------|-------|----------------|
| Architecture | 8/10 | Removed httpx dep. Fixed tool count 8→9. |
| Scoring | 7/10 | Added relevance rubric. HOLD resolution path. Defined confidence formula. Dedup guard. |
| Implementation | 6/10 | Full dict schemas for all tools. Wire() algorithm defined. Query generation strategies specified. |
| Karpathy Pattern | 8/10 | Added novelty/dedup guard. Pattern fidelity confirmed. |
| User Experience | 7/10 | Added progress protocol. MODIFIED list in report. Time estimates. HOLD resolution. |

15 fixes applied in v3.

### Round 3 (6 agents)
| Reviewer | Score | Key Fix Applied |
|----------|-------|----------------|
| Consistency | 8/10 | Fixed Phase 1 "8→9 tools". Added degraded weight redistribution rationale. |
| Security | 6/10 | **Major fix:** No auto-delete. Autoloop produces report, user approves before execution. Atomic lock. Backup retained until next run. trace() limitations disclosed. |
| Documentation | 8/10 | Added Karpathy footnote. Trimmed platform section. |
| Math | 9/10 | Added Jaccard division-by-zero guard. |
| Fix Verification | 9.87/10 | All 15 R1+R2 issues confirmed FIXED. |
| Devil's Advocate | 6/10 | Kept full autoloop (user wants ultra complex). Added sandbox virtualization for safe backtesting. v1/v2 split rejected — ship complete or don't ship. |

**Key v4 changes:**
- Two-phase execution: autoloop THINKS autonomously, user APPROVES destructive actions
- Sandbox virtualization: git worktree isolation for full backtesting safety
- Backup retained until next run (not wiped on convergence)
- trace() false-negative risk disclosed in execution report

---

### Round 4 (3 agents)
| Reviewer | Score | Key Fix Applied |
|----------|-------|----------------|
| Sandbox | 8/10 | Viking sandbox/ namespace prefix. Worktree→rsync→abort fallback chain. 24h TTL. Added sandbox_diff() tool. |
| Impl Plan | 7/10 | LLM-as-judge spike moved to Phase 1 Day 3. Tool count aligned (13). |
| Final Completeness | 9/10 | Degraded hop_efficiency defined. Zero TODOs. Artery Principle woven throughout. |

6 polish fixes applied in v5.

---

*Spec v5 — Final. 4 rounds, 18 agents, all issues resolved.*
