# SKILL.md Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `src/skill/SKILL.md` — the orchestration brain that instructs AI agents how to run the full NeuralTree pipeline: activation, benchmarking, diagnosis, Karpathy autoloop, enforcement, and reporting.

**Architecture:** SKILL.md is a markdown instruction file (not code). It tells the AI agent what to do step-by-step using the 16 MCP tools + Viking MCP. The Skill owns all state (`.neuraltree/`), bridges MCP + Viking, computes final Flow Score, and makes KEEP/HOLD/DISCARD decisions. The agent reading SKILL.md becomes the brain; the MCP server is the muscle.

**Tech Stack:** Markdown (skill instruction format), neuraltree-mcp (16 tools), Viking MCP (semantic search), LLM-as-judge (relevance scoring)

**Key constraint:** This is a SKILL FILE, not Python code. It's a set of instructions that an AI agent reads and follows. Write it like a detailed playbook with exact tool calls, decision trees, and output formats.

---

## File Structure

```
src/skill/
  SKILL.md              The main skill file (9 sections, ~800-1200 lines)
```

Single file. The skill is self-contained — all instructions in one document. The agent loads it and follows it top to bottom based on detected mode.

---

### Task 1: Section 1 — Activation & Mode Detection

**Files:**
- Create: `src/skill/SKILL.md` (initial file with Section 1)

**Context:** This section detects what state the project is in and routes to the correct pipeline. It's the entry point the agent reads first.

- [ ] **Step 1: Create SKILL.md with frontmatter and Section 1**

Write `src/skill/SKILL.md` with:

```markdown
---
name: neuraltree
description: Universal neural organization — transforms any project into a structured information system where any fact is reachable in 0-2 hops
version: 0.1.0
tools_required:
  - neuraltree-mcp (16 tools)
  - openviking (semantic search)
---

# /neuraltree — Universal Neural Organization Skill

> You are the brain. neuraltree-mcp is the muscle. Viking is the memory.
> Your job: orchestrate them to make information FLOW.

## 1. Activation

When invoked, determine your mode by checking project state:

### Step 1: Verify Tools

```tool_check
1. Call neuraltree_scan(path=".") — if error, ABORT: "neuraltree-mcp not available"
2. Call viking_search(query="test") — if error, set DEGRADED_MODE=true, warn user
```

### Step 2: Detect Mode

Read `.neuraltree/state.json`. Route based on what you find:

| Condition | Mode | Pipeline |
|-----------|------|----------|
| No `.neuraltree/state.json` | **bootstrap** | Full: Benchmark → Diagnose → AutoLoop → Enforce |
| `state.json` exists, `flow_score < 0.60` | **critical** | Full pipeline (same as bootstrap) |
| `state.json` exists, `last_run > 7 days` | **health-check** | Benchmark → Fix if score dropped → Enforce |
| `state.json` exists, `last_run < 7 days`, `flow_score > 0.90` | **spot-check** | Run critical queries only, report, done |
| `state.json` exists, `last_run < 7 days`, `flow_score 0.60-0.90` | **maintenance** | Benchmark → Fix degraded metrics → Enforce |

### Step 3: Acquire Lock

```lock_protocol
1. Check for `.neuraltree/.lock`
2. If exists and older than 1 hour: auto-remove, warn "Removed stale lock"
3. If exists and recent: ABORT "Another neuraltree run is active"
4. Create `.neuraltree/.lock` with current timestamp
5. ALL exits (success, error, abort) MUST release the lock
```

### Step 4: Handle Subcommands

If the user invoked a specific subcommand, skip mode detection:

| Command | Action |
|---------|--------|
| `/neuraltree audit` | Jump to Section 4 (Benchmark), read-only, no fixes |
| `/neuraltree fix` | Jump to Section 5 (Diagnose) → Section 6 (AutoLoop) |
| `/neuraltree enforce` | Jump to Section 7 (Enforce) only |
| `/neuraltree benchmark` | Jump to Section 4 (Benchmark), full report |
| `/neuraltree auto` | Full pipeline: Benchmark → Diagnose → AutoLoop → Enforce |

### Step 5: Emit Status

```
"NeuralTree activated — mode: {mode}"
"Tools: neuraltree-mcp ✓, Viking {'✓' if not degraded else '✗ (degraded mode)'}"
"Project: {scan.total_count} files across {len(scan.dirs)} directories"
```
```

- [ ] **Step 2: Verify the file renders correctly**

Run: `head -80 src/skill/SKILL.md` — confirm frontmatter, Section 1 structure, all tables present.

- [ ] **Step 3: Commit**

```bash
git add src/skill/SKILL.md
git commit -m "feat(skill): Section 1 — activation, mode detection, lock protocol"
```

---

### Task 2: Section 2 — Artery Principle (Soul Rules)

**Files:**
- Modify: `src/skill/SKILL.md` (append Section 2)

**Context:** This is the teaching section. It tells the agent HOW to think about organization — the philosophy that guides all decisions. No tool calls here, pure instruction.

- [ ] **Step 1: Append Section 2 to SKILL.md**

Append after Section 1:

```markdown
## 2. The Artery Principle

> **It's NOT about disk space. It's about FLOW.**

The neural tree is an artery system. Information (blood) must flow cleanly from heart to extremities. The metric is not "how many MB freed" — it's:

1. **Synapse Quality** — does every connection lead somewhere alive? Dead synapses are blood clots.
2. **Hop Synergy** — trunk → branch → leaf. Each hop ADDS specificity, never repeats or confuses.
3. **Electrical Flow** — when reading a leaf, do its ## Related synapses fire toward the RIGHT next neuron?
4. **Trunk Pressure** — the trunk is the heart. If bloated (>100 lines), pressure drops, context fills with noise.

### The 0-1-2 Hop Rule

```
HOP 0: Always in context (auto-loaded)
  MEMORY.md, CLAUDE.md, rules files

HOP 1: One tool call away
  _INDEX.md files, Viking search, Grep/Glob

HOP 2: Two calls max
  Leaf files, source code files

NEVER HOP 3+. If anything requires 3+ hops, the structure is broken.
```

### Perfect Neuron Format

Every leaf file MUST follow this format:

```markdown
---
name: [topic]
description: [one-line — used for relevance matching]
type: [user | feedback | project | reference]
last_verified: [YYYY-MM-DD]
---

[Content — 20-80 lines, single topic]

## Related
- [other_leaf.md](path) — why these fire together

## Docs
- `path/to/source.py` — what it implements
```

### Decision Rules

- **Cleanup is a side effect, not the goal.** You delete dead files because dead neurons block signal flow.
- **Trace before prune.** NEVER recommend delete/archive/move without calling `neuraltree_trace()` first.
- **Show both sides.** Every report shows KEPT (with proof) and DELETED (with proof). The KEPT list prevents anxiety.
- **User approves destructive actions.** You execute non-destructive fixes (wiring, indexing, freshness updates) automatically. Deletes, archives, moves, and splits require user approval.
```

- [ ] **Step 2: Commit**

```bash
git add src/skill/SKILL.md
git commit -m "feat(skill): Section 2 — Artery Principle, 0-1-2 hop rule, neuron format"
```

---

### Task 3: Section 3 — Progress Protocol

**Files:**
- Modify: `src/skill/SKILL.md` (append Section 3)

**Context:** Tells the agent how to communicate progress to the user during long-running operations.

- [ ] **Step 1: Append Section 3 to SKILL.md**

```markdown
## 3. Progress Protocol

Emit status after each major step. The user should never wonder "is it stuck?"

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

### Time Estimates

| Mode | Expected Duration |
|------|------------------|
| spot-check | ~30 seconds |
| health-check | ~1-3 minutes |
| maintenance | ~3-5 minutes |
| bootstrap/critical | ~8-15 minutes |
```

- [ ] **Step 2: Commit**

```bash
git add src/skill/SKILL.md
git commit -m "feat(skill): Section 3 — progress protocol with status messages"
```

---

### Task 4: Section 4 — Benchmark Protocol

**Files:**
- Modify: `src/skill/SKILL.md` (append Section 4)

**Context:** This is the first real tool-calling section. The agent generates queries, runs Viking search, judges relevance with LLM, calls neuraltree_score(), and assembles the composite Flow Score. This is where the 5 critical integration points from the handoff come alive.

- [ ] **Step 1: Append Section 4 to SKILL.md**

```markdown
## 4. Benchmark Protocol

### Step 1: Generate Queries

```tool
result = neuraltree_generate_queries(
    claude_md_path="CLAUDE.md",
    memory_md_path="memory/MEMORY.md",
    index_paths=[find all _INDEX.md files via neuraltree_scan()],
    git_log_lines=100,
    indexed_doc_count=[count from scan result]
)
queries = result["queries"]
```

For **spot-check mode**: filter to only queries tagged `category: "critical"` from `queries.json`. If no `queries.json` exists, run full benchmark instead.

### Step 2: Viking Search (Precision@3)

For each query, call Viking to get top 3 results:

```tool
for query in queries:
    viking_result = viking_search(query=query["text"], limit=3)
    query["viking_results"] = viking_result["results"]  # list of {uri, content, score}
```

**If DEGRADED_MODE** (no Viking): skip this step entirely. Set `precision_at_3 = None` for all queries.

### Step 3: LLM-as-Judge

For each Viking result, judge relevance:

```prompt
RELEVANCE JUDGMENT
Query: {query.text}
Result file: {result.uri}
Result content (first 50 lines): {result.content[:50_lines]}

Rubric: Would reading this file help answer the query?
- YES if the file contains information directly useful for answering
- NO if the file is unrelated or only tangentially mentions the topic

Reply YES or NO only.
```

Score: count YES answers / 3 = precision_at_3 for that query.
**Malformed response handling:** anything not starting with "YES" = NO (conservative).

Average across all queries = **Precision@3 metric** (0.0 - 1.0).

### Step 4: Structural Metrics

```tool
score_result = neuraltree_score(project_root=".")
structural_metrics = score_result["metrics"]
# Returns: hop_efficiency, synapse_coverage, dead_neuron_ratio, freshness, trunk_pressure
# precision_at_3 is null — we computed it in Step 3
```

### Step 5: Assemble Flow Score

```formula
Flow Score = (
    hop_efficiency     * 0.25 +
    precision_at_3     * 0.25 +
    synapse_coverage   * 0.20 +
    dead_neuron_ratio  * 0.15 +
    freshness          * 0.10 +
    trunk_pressure     * 0.05
)
```

Fill `precision_at_3` from Step 3 into `score_result["metrics"]`.
Compute: `final_flow_score = score_result["flow_score_partial"] + (precision_at_3 * 0.25)`

### Step 6: Record Baseline

Store the complete metric snapshot as `baseline` for before/after comparison.

```state
baseline = {
    "flow_score": final_flow_score,
    "metrics": {all 6 metrics},
    "query_results": [{query, viking_results, precision_at_3, relevant_count}],
    "timestamp": now()
}
```

### Step 7: Route by Score

| Flow Score | Status | Next Step |
|------------|--------|-----------|
| > 0.90 | Excellent | If spot-check: report and done. Otherwise: continue to diagnose. |
| 0.75 - 0.90 | Healthy | Continue to Section 5 (Diagnose) |
| 0.60 - 0.74 | Degraded | Continue to Section 5 (Diagnose) |
| < 0.60 | Critical | Continue to Section 5 (Diagnose) — full pipeline |

### Degraded Mode (No Viking)

When DEGRADED_MODE is true:
- Skip Steps 2-3 entirely (no Viking search, no LLM judge)
- precision_at_3 = None
- Merge hop_efficiency + synapse_coverage into `structure_reachability`:
  `structure_reachability = (hop_efficiency + synapse_coverage) / 2`
- Recalculate weights: structure_reachability 0.45, dead_neuron 0.25, freshness 0.20, trunk 0.10
- Warn user: "Operating in structure-only mode (4 of 6 metrics). Install Viking for full power."
```

- [ ] **Step 2: Commit**

```bash
git add src/skill/SKILL.md
git commit -m "feat(skill): Section 4 — benchmark protocol, Viking + LLM judge, Flow Score assembly"
```

---

### Task 5: Section 5 — Diagnose Protocol

**Files:**
- Modify: `src/skill/SKILL.md` (append Section 5)

**Context:** Takes failed queries from benchmark and classifies them by gap type. This is where the Skill passes `viking_results` to the MCP's diagnose tool — integration point #2 from the handoff.

- [ ] **Step 1: Append Section 5 to SKILL.md**

```markdown
## 5. Diagnose Protocol

### Step 1: Identify Failed Queries

A query "fails" if:
- `precision_at_3 < 0.67` (fewer than 2 of 3 Viking results were relevant), OR
- The correct file was not in Viking's top 3 at all

Collect all failed queries from the benchmark.

### Step 2: Classify Failures

```tool
# Build viking_results for the diagnose tool (integration point #2)
viking_results_for_diagnose = []
for query in failed_queries:
    viking_results_for_diagnose.append({
        "query": query["text"],
        "results": [r["uri"] for r in query["viking_results"]]
    })

diagnosis = neuraltree_diagnose(
    failed_queries=[{"text": q["text"], "expected_topic": q.get("source", "")} for q in failed_queries],
    project_root=".",
    viking_results=viking_results_for_diagnose
)
```

### Step 3: Enrich with Lessons

For each diagnosed failure, check if we've seen this pattern before:

```tool
symptoms = [d["query"] + " " + d["gap_type"] for d in diagnosis["diagnoses"]]
lesson_matches = neuraltree_lesson_match(symptoms=symptoms, project_root=".")
```

If a lesson matches with score > 0.5, attach it to the diagnosis:
- Show the agent: "Past lesson found: {lesson.fix}. Consider this approach."
- Past lessons inform fix strategy but don't override the autoloop's predict/measure cycle.

### Step 4: Build Priority Queue

Sort failures by predicted impact (cheapest fixes first):

```priority
1. SYNAPSE_GAP  — cheapest: just add ## Related / ## Docs wiring
2. FRESHNESS_GAP — cheap: update last_verified dates
3. EMBEDDING_GAP — medium: re-index in Viking
4. FOCUS_GAP     — medium: split large files
5. CONTENT_GAP   — expensive: create new files
```

### Step 5: Emit Diagnosis Summary

```
"Diagnosed {total} failures: {synapse} SYNAPSE, {embedding} EMBEDDING, {freshness} FRESHNESS, {focus} FOCUS, {content} CONTENT"
"Priority queue: {count} fixes ordered by cost (cheapest first)"
```

If no failures: "All queries passing. Tree is healthy." → Skip to Section 7 (Enforce).
```

- [ ] **Step 2: Commit**

```bash
git add src/skill/SKILL.md
git commit -m "feat(skill): Section 5 — diagnose protocol, lesson enrichment, priority queue"
```

---

### Task 6: Section 6 — Karpathy AutoLoop

**Files:**
- Modify: `src/skill/SKILL.md` (append Section 6)

**Context:** The core autoloop. This is the most complex section — predict, backup, execute, measure, decide (KEEP/HOLD/DISCARD), update calibration, dedup guard, oscillation damping, exit conditions.

- [ ] **Step 1: Append Section 6 to SKILL.md**

```markdown
## 6. Karpathy AutoLoop

### Overview

An iterative improvement loop inspired by Karpathy's autoresearch methodology. For each diagnosed failure, predict the impact, try the fix, measure the result, and decide whether to keep it.

**Exit conditions (check after EVERY iteration):**
1. `flow_score > 0.85` — tree is healthy
2. 3 consecutive iterations with `|delta| < 0.02` — converged (oscillation damping)
3. 10 iterations reached — hard cap
4. All diagnosed failures addressed (or skipped via dedup guard)

### Initialize

```state
autoloop_state = {
    "iteration": 0,
    "max_iterations": 10,
    "score_history": [baseline.flow_score],
    "attempted": set(),  # {(gap_type, target)} pairs for dedup
    "kept": [],
    "discarded": [],
    "held": [],
    "convergence_counter": 0  # consecutive iterations with |delta| < 0.02
}
```

### For Each Iteration

Process the next failure from the priority queue:

#### Step 1: Dedup Guard

```check
key = (failure.gap_type, failure.target_file)
if key in autoloop_state["attempted"]:
    skip this failure, move to next in queue
autoloop_state["attempted"].add(key)
```

#### Step 2: Predict

```tool
prediction = neuraltree_predict(
    current_metrics=current_metrics,
    proposed_changes=[{
        "action": gap_type_to_action(failure.gap_type),
        "target": failure.target_file,
        "details": failure.fix
    }],
    project_root="."
)
```

Action mapping:
| Gap Type | Action |
|----------|--------|
| SYNAPSE_GAP | `"wire"` |
| FRESHNESS_GAP | `"update_freshness"` |
| EMBEDDING_GAP | `"index"` |
| FOCUS_GAP | `"split"` |
| CONTENT_GAP | `"wire"` (create file + wire it) |

#### Step 3: Backup

```tool
neuraltree_backup(
    files=[failure.target_file],
    project_root="."
)
```

#### Step 4: Execute the Fix

Based on gap type, execute the appropriate fix:

**SYNAPSE_GAP:**
```tool
wire_result = neuraltree_wire(file_path=failure.target_file, project_root=".")
# Apply the suggested_content to the file (append ## Related + ## Docs)
```

**FRESHNESS_GAP:**
Update the `last_verified` date in the file's frontmatter to today.

**EMBEDDING_GAP:**
```tool
viking_add_resource(file=failure.target_file)
```

**FOCUS_GAP:**
Split the large file into focused leaves. For each new leaf:
1. Create the file with proper frontmatter
2. Wire it with `neuraltree_wire()`
3. Update the parent _INDEX.md
4. Add to Viking: `viking_add_resource()`

**CONTENT_GAP:**
Flag as PENDING ACTION in the report. Content creation requires user input.
Do NOT auto-generate content files — the user must provide or approve the content.

#### Step 5: Measure

Re-run the benchmark for the specific queries that failed:

```tool
# Re-score structural metrics
new_score = neuraltree_score(project_root=".")

# Re-run Viking search for affected queries (if not degraded)
if not DEGRADED_MODE:
    for query in affected_queries:
        viking_result = viking_search(query=query["text"], limit=3)
        # Re-judge relevance with LLM
        new_precision = judge_relevance(query, viking_result)

# Compute new Flow Score
new_flow_score = assemble_flow_score(new_score, new_precision_values)
actual_delta = new_flow_score - previous_flow_score
```

#### Step 6: Decide — KEEP / HOLD / DISCARD

```decision
predicted_delta = prediction["predicted_delta"]
actual_delta = new_flow_score - previous_flow_score
ratio = actual_delta / max(abs(predicted_delta), 0.001)

if ratio >= 0.8:
    # KEEP — actual improvement meets or exceeds 80% of prediction
    decision = "KEEP"
    autoloop_state["kept"].append({failure, predicted_delta, actual_delta})
    current_metrics = new_score["metrics"]
    current_flow_score = new_flow_score

elif ratio >= 0.5:
    # HOLD — partial improvement, keep in place but flag for review
    decision = "HOLD"
    autoloop_state["held"].append({failure, predicted_delta, actual_delta})
    current_metrics = new_score["metrics"]
    current_flow_score = new_flow_score

else:
    # DISCARD — improvement less than 50% of prediction, rollback
    decision = "DISCARD"
    neuraltree_restore(files=[failure.target_file], project_root=".")
    autoloop_state["discarded"].append({failure, predicted_delta, actual_delta})
```

#### Step 7: Update Calibration

```tool
neuraltree_update_calibration(
    predicted_delta=predicted_delta,
    actual_delta=actual_delta,
    project_root="."
)
```

#### Step 8: Record Lesson (Integration Point #3)

After a KEEP or DISCARD decision, record what we learned:

```tool
if decision == "KEEP":
    neuraltree_lesson_add(
        domain="autoloop",
        lesson={
            "symptom": f"{failure.gap_type} on {failure.target_file}",
            "root_cause": failure.fix,
            "fix": f"Applied {failure.gap_type_to_action} — delta {actual_delta:+.3f}",
            "lesson": f"Fix worked (ratio {ratio:.2f}). Calibration updated."
        },
        project_root="."
    )
elif decision == "DISCARD":
    neuraltree_lesson_add(
        domain="autoloop",
        lesson={
            "symptom": f"{failure.gap_type} on {failure.target_file}",
            "root_cause": failure.fix,
            "fix": f"DISCARDED — actual delta {actual_delta:+.3f} vs predicted {predicted_delta:+.3f}",
            "lesson": f"Fix didn't work (ratio {ratio:.2f}). Avoid this approach next time."
        },
        project_root="."
    )
```

#### Step 9: Check Exit Conditions

```check
autoloop_state["iteration"] += 1
autoloop_state["score_history"].append(current_flow_score)

# Oscillation damping
if abs(actual_delta) < 0.02:
    autoloop_state["convergence_counter"] += 1
else:
    autoloop_state["convergence_counter"] = 0

# Check alternating direction (up/down/up pattern)
if len(autoloop_state["score_history"]) >= 3:
    last_3 = autoloop_state["score_history"][-3:]
    if (last_3[1] > last_3[0] and last_3[2] < last_3[1]) or \
       (last_3[1] < last_3[0] and last_3[2] > last_3[1]):
        autoloop_state["convergence_counter"] += 1

# Exit?
if current_flow_score > 0.85:
    exit_reason = "healthy (score > 0.85)"
elif autoloop_state["convergence_counter"] >= 3:
    exit_reason = "converged (3 consecutive |delta| < 0.02)"
elif autoloop_state["iteration"] >= autoloop_state["max_iterations"]:
    exit_reason = "max iterations reached (10)"
elif priority_queue is empty:
    exit_reason = "all failures addressed"
else:
    continue to next iteration
```

### Emit AutoLoop Summary

```
"AutoLoop complete — {exit_reason}"
"Iterations: {iteration}, KEEP: {len(kept)}, DISCARD: {len(discarded)}, HOLD: {len(held)}"
"Flow Score: {baseline} → {current} ({delta:+.3f})"
```
```

- [ ] **Step 2: Commit**

```bash
git add src/skill/SKILL.md
git commit -m "feat(skill): Section 6 — Karpathy autoloop with predict/measure/decide cycle"
```

---

### Task 7: Section 7 — Enforcement

**Files:**
- Modify: `src/skill/SKILL.md` (append Section 7)

**Context:** After the autoloop, enforce organization rules, re-index Viking, graduate training data, compress history.

- [ ] **Step 1: Append Section 7 to SKILL.md**

```markdown
## 7. Enforce

### Step 1: Graduation Protocol

After autoloop convergence, graduate training data:

1. **Merge calibration:** `.tmp/predictions_buffer.json` accuracy data is already merged by `neuraltree_update_calibration()` during the loop.

2. **Evolve queries:**
   - Queries that passed in ALL iterations → demote to `status: "spot-check"` (cheaper next run)
   - Queries that caught real issues → promote to `status: "critical"` (always run)
   - New project areas (from recent git log) → generate fresh queries

3. **Compress to history:**
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
     "fixes": ["wire: 2", "index: 1", "freshness: 0"],
     "exit_reason": "healthy",
     "calibration_accuracy": 0.87,
     "duration_seconds": 480
   }
   ```

4. **Update state.json:**
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

5. **Save evolved queries:**
   ```json
   // .neuraltree/queries.json
   {
     "queries": [
       {"text": "...", "source": "claude_md", "category": "what_is", "status": "critical"},
       {"text": "...", "source": "git_log", "category": "what_changed", "status": "spot-check"}
     ],
     "last_updated": "2026-04-05"
   }
   ```

6. **Delete .tmp/ entirely** — all ephemeral autoloop state.

### Step 2: Re-index Viking

For every file that was modified, created, or wired during the autoloop:

```tool
for file in modified_files:
    viking_add_resource(file=file)
```

### Step 3: Install Organization Rule

Create `.claude/rules/neuraltree.md` (or equivalent for the platform):

```markdown
# NeuralTree Organization Rule

## Session Start Protocol
1. Scan _INDEX.md files before taking action on memory/docs
2. Check MEMORY.md trunk (<100 lines) before adding new memories
3. New files MUST include: frontmatter (name, description, type, last_verified), ## Related, ## Docs

## File Standards
- Leaf files: 20-80 lines, single topic
- _INDEX.md per branch directory
- ## Related: 1-3 lateral connections to related leaves
- ## Docs: links to source code files

## Weekly Hygiene
- Run `/neuraltree` for health check
- Delete __pycache__/, htmlcov/, stale logs
- Archive completed plans
```

### Step 4: Cleanup

```check
1. Remove .neuraltree/.lock
2. Remove .neuraltree/.tmp/ (entire directory)
3. Verify .neuraltree/state.json was written
4. Verify .neuraltree/history/ entry was created
```
```

- [ ] **Step 2: Commit**

```bash
git add src/skill/SKILL.md
git commit -m "feat(skill): Section 7 — enforce, graduation, history, Viking re-index"
```

---

### Task 8: Section 8 — Execution Report

**Files:**
- Modify: `src/skill/SKILL.md` (append Section 8)

**Context:** The final output the user sees. Before/after metrics, what was kept, what needs review, what needs approval.

- [ ] **Step 1: Append Section 8 to SKILL.md**

```markdown
## 8. Execution Report

After enforcement, present the complete report to the user.

### Report Format

```
═══════════════════════════════════════════════════
  NeuralTree Report — {project_name}
  Mode: {mode} | Duration: {duration}
═══════════════════════════════════════════════════

Flow Score: {before} → {after} ({delta:+.2f})

┌──────────────────────────────────────────────────┐
│ Metric              Before   After    Delta      │
│ ──────────────────────────────────────────────── │
│ Hop Efficiency       {:.2f}    {:.2f}   {:+.2f}  │
│ Precision@3          {:.2f}    {:.2f}   {:+.2f}  │
│ Synapse Coverage     {:.2f}    {:.2f}   {:+.2f}  │
│ Dead Neuron Ratio    {:.2f}    {:.2f}   {:+.2f}  │
│ Freshness            {:.2f}    {:.2f}   {:+.2f}  │
│ Trunk Pressure       {:.2f}    {:.2f}   {:+.2f}  │
└──────────────────────────────────────────────────┘

SAFE ACTIONS (already executed — non-destructive, reversible):
  ✓ {file} — added ## Related ({n} synapses)
  ✓ {file} — added ## Docs ({n} axons)
  ✓ {file} — updated last_verified
  ✓ {file} — re-indexed in Viking

PENDING ACTIONS (require your approval — destructive):
  ⚠ DELETE {file} — {reason} (trace: {ref_count} refs)
  ⚠ ARCHIVE {file} → archive/{file} — {reason}
  ⚠ MOVE {file} → {new_path} — {reason}
  ⚠ SPLIT {file} into {n} leaves — {reason} ({line_count} lines)

NEEDS REVIEW (HOLD items — partial improvement):
  ? {file} — {description} (kept in place, review next run)

KEPT (verified alive — not touched):
  ✓ {file} — {reason}

AutoLoop: {iterations} iterations, {kept} KEEP, {discarded} DISCARD, {held} HOLD
Calibration accuracy: {accuracy}%
Exit reason: {exit_reason}
Next run ETA: ~{estimate} ({reason})
═══════════════════════════════════════════════════
```

### Handling User Response

After presenting the report:

1. If PENDING ACTIONS exist, ask: "Which actions should I execute? (all / none / pick by number)"
2. If user says "all": execute all pending actions, then re-score and report final state.
3. If user picks specific actions: execute only those, re-score, report.
4. If user says "none": done. Pending actions saved for next run.

### Spot-Check Report (Short Form)

For spot-check mode (score > 0.90, < 7 days since last run):

```
NeuralTree spot-check — {project_name}
Score: {score} (Excellent) | {query_count} queries checked | 0 failures
Last full run: {days} days ago | Next recommended: {date}
```
```

- [ ] **Step 2: Commit**

```bash
git add src/skill/SKILL.md
git commit -m "feat(skill): Section 8 — execution report format, pending actions, user approval"
```

---

### Task 9: Section 9 — Degraded Mode & Edge Cases

**Files:**
- Modify: `src/skill/SKILL.md` (append Section 9)

**Context:** What happens when Viking is down, when there's no git, no CLAUDE.md, empty project, monorepo, concurrent runs.

- [ ] **Step 1: Append Section 9 to SKILL.md**

```markdown
## 9. Degraded Mode & Edge Cases

### Without Viking (DEGRADED_MODE)

When Viking MCP is not available:

1. **Warn user:** "Viking not found. Operating in structure-only mode (4 of 6 metrics). Install Viking for full power."
2. **Skip:** Precision@3 (no embeddings), Viking re-indexing
3. **Merge metrics:** `structure_reachability = (hop_efficiency + synapse_coverage) / 2`
4. **Recalculate weights:** structure_reachability 0.45, dead_neuron 0.25, freshness 0.20, trunk 0.10
5. **EMBEDDING_GAP → SYNAPSE_GAP:** Without Viking, all embedding gaps become synapse gaps (fix via wiring instead of re-indexing)

### Bootstrap: No CLAUDE.md

1. Check for README.md — use it as initial trunk context
2. If no README.md: use directory structure + filenames as context
3. Create minimal CLAUDE.md nav hub from discovered structure
4. Proceed with full pipeline (score will start low, that's expected)

### Bootstrap: No Git

1. `neuraltree_backup()` uses file copy (not git stash) — this already works
2. `neuraltree_sandbox_create()` falls back to rsync — this already works
3. Warn: "No git detected — changes are harder to revert. Consider initializing git."

### Bootstrap: Empty Project

1. `neuraltree_scan()` returns minimal files
2. `neuraltree_generate_queries()` generates queries from filenames only
3. Score = ~0.0 (expected for empty project)
4. AutoLoop creates the initial structure: MEMORY.md, _INDEX.md files, wiring

### Monorepo Detection

1. If `neuraltree_scan()` finds multiple CLAUDE.md or package.json files at different depths
2. Scope to current working directory only
3. Warn: "Monorepo detected. Scoping to {cwd}. Cross-boundary wiring may be incomplete."

### Concurrent Run Protection

1. `.neuraltree/.lock` check at activation (Section 1)
2. Stale lock (>1 hour): auto-remove with warning
3. Active lock: abort immediately
4. ALL code paths release the lock on exit (success, error, or abort)

### Scale Limits

| Parameter | Limit | At Limit |
|-----------|-------|----------|
| File scan | 10,000 files | "Large project — sampling mode" |
| Test queries | 50 max | Cap regardless of project size |
| AutoLoop iterations | 10 max | Hard stop, report partial |
| Leaf file size | 500 lines | Flag as FOCUS_GAP |
| Trunk size | 100 lines | Flag as TRUNK_PRESSURE |
| Backup dir | 100 MB | Skip large files with warning |

### Error Recovery

| Error | Recovery |
|-------|----------|
| MCP tool crashes mid-loop | Release lock, report partial results, suggest restart |
| Viking timeout | Retry once, then enter DEGRADED_MODE for remaining queries |
| File permission denied | Report in warnings, skip file, continue |
| Disk full during backup | Abort autoloop, release lock, report error |
| LLM judge returns garbage | Default to NO (conservative), log warning |
```

- [ ] **Step 2: Commit**

```bash
git add src/skill/SKILL.md
git commit -m "feat(skill): Section 9 — degraded mode, bootstrap, edge cases, error recovery"
```

---

### Task 10: Final Assembly & Self-Review

**Files:**
- Modify: `src/skill/SKILL.md` (final review pass)

**Context:** Read the complete SKILL.md end-to-end, verify internal consistency, check all integration points are covered, verify all MCP tool calls match actual tool signatures.

- [ ] **Step 1: Read complete SKILL.md and verify**

Check:
1. All 16 MCP tools referenced where needed (scan, trace, backup, restore, wire, generate_queries, lesson_match, lesson_add, score, diagnose, predict, update_calibration, sandbox_create, sandbox_diff, sandbox_apply, sandbox_destroy)
2. All 5 integration points from HANDOFF.md addressed:
   - `precision_at_3` assembly (Section 4, Steps 3-5) ✓
   - `viking_results` passed to diagnose (Section 5, Step 2) ✓
   - Lesson recording after KEEP/DISCARD (Section 6, Step 8) ✓
   - `.neuraltree/state.json` owned by Skill (Section 7) ✓
   - Two-phase scoring (Section 4, Steps 4-5) ✓
3. Tool call signatures match actual MCP tool signatures from `server.py`
4. All modes (bootstrap/critical/health-check/spot-check/maintenance) have clear pipelines
5. Section references are correct (e.g., "Jump to Section 5" actually matches Section 5)
6. No TODOs, TBDs, or placeholder text

- [ ] **Step 2: Fix any issues found**

Apply fixes directly to SKILL.md.

- [ ] **Step 3: Final commit**

```bash
git add src/skill/SKILL.md
git commit -m "feat(skill): SKILL.md Phase 2 complete — 9 sections, full orchestration brain"
```

---

### Task 11: Verification — Run Against Test Project

**Files:**
- Read only: `tests/conftest.py` (for tmp_project fixture structure)

**Context:** Verify the SKILL.md instructions are coherent by tracing through a simulated run mentally. Check that the tool call sequences would actually work with the real MCP server.

- [ ] **Step 1: Trace a bootstrap run through SKILL.md**

Walk through each section as if you were an agent executing it:
1. Section 1: Activation → mode = bootstrap (no state.json)
2. Section 3: Progress → emit "Phase 1/5: Scanning..."
3. Section 4: Benchmark → generate queries, Viking search, LLM judge, score assembly
4. Section 5: Diagnose → classify failures, enrich with lessons
5. Section 6: AutoLoop → predict, backup, execute, measure, KEEP/HOLD/DISCARD
6. Section 7: Enforce → graduate, history, state.json, Viking re-index
7. Section 8: Report → full report with before/after

Verify: every tool call uses the correct parameter names from the actual tool signatures.

- [ ] **Step 2: Trace a spot-check run**

1. Section 1: Activation → mode = spot-check (state.json exists, score > 0.90, < 7 days)
2. Section 4: Benchmark → load queries.json, run critical queries only
3. Section 8: Report → short form report

- [ ] **Step 3: Trace a degraded mode run**

1. Section 1: Activation → Viking check fails, DEGRADED_MODE = true
2. Section 4: Benchmark → skip Viking steps, merged weights
3. Section 5: Diagnose → EMBEDDING_GAP → SYNAPSE_GAP
4. Section 6: AutoLoop → no Viking re-index in execute step

- [ ] **Step 4: Document any issues found, fix them**

- [ ] **Step 5: Final commit if changes were needed**

```bash
git add src/skill/SKILL.md
git commit -m "fix(skill): verification fixes from simulated run traces"
```

---

## Summary

| Task | Section | Description | Est. Size |
|------|---------|-------------|-----------|
| 1 | Activation | Mode detection, lock, subcommands | ~80 lines |
| 2 | Artery Principle | Soul rules, 0-1-2 hop, neuron format | ~60 lines |
| 3 | Progress Protocol | Status messages, time estimates | ~30 lines |
| 4 | Benchmark | Queries, Viking, LLM judge, Flow Score | ~120 lines |
| 5 | Diagnose | Gap classification, lessons, priority | ~70 lines |
| 6 | AutoLoop | Predict/measure/decide cycle | ~200 lines |
| 7 | Enforce | Graduation, history, state, Viking | ~100 lines |
| 8 | Report | Final output, user approval | ~80 lines |
| 9 | Edge Cases | Degraded, bootstrap, errors | ~80 lines |
| 10 | Self-Review | Internal consistency check | review only |
| 11 | Verification | Simulated run traces | review only |
| **Total** | | | **~820 lines** |
