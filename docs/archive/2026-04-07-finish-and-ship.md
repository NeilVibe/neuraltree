# NeuralTree Finish & Ship — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trim dead weight, wire orphaned tools, integrate autoresearch, ship a clean 24-tool / 5-phase neuraltree.

**Architecture:** Delete 2 unused tools (predict/calibration), relocate shared util, wire lessons + wiki_lint into pipeline phases, merge explore+map into "understand", update all docs and tests.

**Tech Stack:** Python 3.11, FastMCP, pytest

---

## File Structure — What Changes

**Delete:**
- `src/neuraltree_mcp/scoring/predict.py` — predict + update_calibration tools
- `tests/unit/test_predict.py` — predict unit tests

**Modify (production):**
- `src/neuraltree_mcp/text_utils.py` — add `_viking_uri_matches_file` (relocated from diagnose.py)
- `src/neuraltree_mcp/scoring/diagnose.py` — import `_viking_uri_matches_file` from text_utils
- `src/neuraltree_mcp/server.py` — remove predict import/registration, update docstring
- `src/skill/SKILL.md` — update tool count, remove predict/calibration refs, add autoresearch routing
- `src/skill/sections/understand.md` — NEW: merged explore + map phase
- `src/skill/sections/analyze.md` — add lesson_match step
- `src/skill/sections/verify.md` — add wiki_lint + lesson_add steps

**Delete (skill):**
- `src/skill/sections/explore.md` — merged into understand.md
- `src/skill/sections/map.md` — merged into understand.md

**Modify (tests):**
- `tests/unit/test_reorganize.py` — update import path for `_viking_uri_matches_file`
- `tests/integration/test_e2e_pipeline.py` — remove predict/diagnose/lesson/calibration/autoloop test classes
- `tests/integration/test_degraded_mode.py` — remove diagnose/lesson test classes
- `tests/integration/test_tool_calls.py` — remove diagnose/lesson test classes
- `tests/integration/test_server.py` — update expected tool list and count

**Modify (docs):**
- `CLAUDE.md` — update tool count, pipeline phases, remove false claims
- `README.md` — update tool count, pipeline description
- `docs/concepts/autoloop.md` — update to reference autoresearch integration

**Move:**
- `docs/HANDOFF_2026-04-06_SESSION*.md` + `docs/HANDOFF_2026-04-07_SESSION*.md` → `docs/archive/`

---

### Task 1: Relocate `_viking_uri_matches_file` to text_utils.py

**Files:**
- Modify: `src/neuraltree_mcp/text_utils.py`
- Modify: `src/neuraltree_mcp/scoring/diagnose.py`
- Modify: `tests/unit/test_reorganize.py`

This MUST happen before any deletions — test_reorganize.py imports this function from diagnose.py.

- [ ] **Step 1: Add function to text_utils.py**

Add at the end of `src/neuraltree_mcp/text_utils.py`:

```python
def viking_uri_matches_file(vuri: str, local_rel_path: str) -> bool:
    """Check if a Viking URI refers to a local file, using segment matching.

    Viking URIs look like:
      viking://resources/newfin/docs/GUIDE.md/Section_Title/chunk_hash.md
    We check if the local filename appears as an exact path segment,
    not just a substring (avoids GUIDE.md matching DEBUGGING_GUIDE.md).
    """
    uri_segments = vuri.split("/")
    basename = os.path.basename(local_rel_path)
    if basename in uri_segments:
        return True
    rel_segments = local_rel_path.split("/")
    for i in range(len(uri_segments) - len(rel_segments) + 1):
        if uri_segments[i:i + len(rel_segments)] == rel_segments:
            return True
    return False
```

Note: renamed from `_viking_uri_matches_file` to `viking_uri_matches_file` (public API now).

- [ ] **Step 2: Update diagnose.py to import from text_utils**

In `src/neuraltree_mcp/scoring/diagnose.py`, replace:
```python
from neuraltree_mcp.text_utils import extract_keywords, walk_project_files
```
with:
```python
from neuraltree_mcp.text_utils import extract_keywords, walk_project_files, viking_uri_matches_file
```

And delete the `_viking_uri_matches_file` function definition (lines 24-40).

Replace the call site inside `register()` — change `_viking_uri_matches_file(` to `viking_uri_matches_file(`.

- [ ] **Step 3: Update test_reorganize.py import**

In `tests/unit/test_reorganize.py`, change line 12:
```python
from neuraltree_mcp.scoring.diagnose import _viking_uri_matches_file
```
to:
```python
from neuraltree_mcp.text_utils import viking_uri_matches_file as _viking_uri_matches_file
```

- [ ] **Step 4: Run tests to verify**

Run: `PYTHONPATH=src python3.11 -m pytest tests/unit/test_reorganize.py tests/unit/test_diagnose.py tests/unit/test_text_utils.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/neuraltree_mcp/text_utils.py src/neuraltree_mcp/scoring/diagnose.py tests/unit/test_reorganize.py
git commit -m "refactor: relocate viking_uri_matches_file to text_utils"
```

---

### Task 2: Delete predict.py and its tests

**Files:**
- Delete: `src/neuraltree_mcp/scoring/predict.py`
- Delete: `tests/unit/test_predict.py`
- Modify: `src/neuraltree_mcp/server.py`

- [ ] **Step 1: Remove predict from server.py**

In `src/neuraltree_mcp/server.py`:

Remove line 28:
```python
from neuraltree_mcp.scoring.predict import register as register_predict
```

Remove line 44:
```python
register_predict(mcp)
```

Update the docstring (lines 1-11) to:
```python
"""NeuralTree MCP Server — The Muscle.

24 tools for neural tree organization:
  Filesystem: scan, trace, backup, restore
  Intelligence: wire, generate_queries
  Reorganize: plan_move, plan_split, find_dead, generate_index, shrink_and_wire, split_and_wire
  Lessons: lesson_match, lesson_add
  Scoring: score, diagnose
  Semantic: precision (Viking search + LLM judge), viking_index (batch indexing)
  Knowledge Map: knowledge_map (save/load/query)
  Wiki: wiki_lint
  Sandbox: sandbox_create, sandbox_diff, sandbox_apply, sandbox_destroy
"""
```

- [ ] **Step 2: Delete predict.py**

```bash
rm src/neuraltree_mcp/scoring/predict.py
```

- [ ] **Step 3: Delete test_predict.py**

```bash
rm tests/unit/test_predict.py
```

- [ ] **Step 4: Remove predict tests from integration files**

In `tests/integration/test_e2e_pipeline.py`, delete these classes entirely:
- `TestCalibration` (class at line 289)
- `TestAutoLoopCycle` (class at line 344)

And delete `test_predict_impact` (method at line 101) from `TestBenchmarkPipeline`.

In `tests/integration/test_tool_calls.py`, there are no predict-specific classes — nothing to remove.

- [ ] **Step 5: Update test_server.py**

In `tests/integration/test_server.py`:

Remove from the `expected` list (lines 35-36):
```python
            "neuraltree_predict",
            "neuraltree_update_calibration",
```

Change `test_tool_count` (line 52):
```python
        assert len(tools) == 24
```

Update docstring in `test_all_tools_registered` (line 13):
```python
    def test_all_tools_registered(self):
        """All 24 tools should be registered."""
```

- [ ] **Step 6: Run full test suite**

Run: `PYTHONPATH=src python3.11 -m pytest tests/ -v --tb=short`
Expected: All pass (minus deleted tests)

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: delete predict + calibration tools (redundant with sandbox)"
```

---

### Task 3: Remove predict/lesson/diagnose tests from integration files

**Files:**
- Modify: `tests/integration/test_e2e_pipeline.py`
- Modify: `tests/integration/test_degraded_mode.py`
- Modify: `tests/integration/test_tool_calls.py`

Note: predict tests from test_e2e_pipeline.py were already removed in Task 2. This task cleans up the remaining integration test references to diagnose and lesson tools that are being tested outside their scope.

Wait — diagnose and lesson tools are KEPT. Their integration tests should stay. Only remove the tests for DELETED tools (predict, calibration, autoloop cycle).

Actually, re-reading the spec: we're keeping diagnose and lessons. So only the predict/calibration/autoloop tests get removed. Those were handled in Task 2.

- [ ] **Step 1: Verify test_e2e_pipeline.py is clean**

Check that `TestBenchmarkPipeline.test_diagnose_with_failures` still exists (line 76) — diagnose is kept.
Check that `TestLessonRoundTrip` still exists (line 260) — lessons are kept.

Run: `PYTHONPATH=src python3.11 -m pytest tests/integration/test_e2e_pipeline.py -v --tb=short`
Expected: All remaining tests pass

- [ ] **Step 2: Commit if any changes needed**

```bash
git add tests/integration/
git commit -m "test: clean up integration tests after predict removal"
```

---

### Task 4: Wire lesson_match into Analyze phase

**Files:**
- Modify: `src/skill/sections/analyze.md`

- [ ] **Step 1: Add lesson check before Claude analysis**

In `src/skill/sections/analyze.md`, add a new step between Step 1 (Load Knowledge Map) and Step 2 (Claude Analyzes). Insert after line 13:

```markdown
## Step 1b: Check Lessons for Past Patterns

Before reasoning about issues, check if the lesson system has relevant
experience from prior runs.

```
# Get the list of issue types from the knowledge map
issue_types = [issue["type"] for issue in km.get("issues", [])]

# For each issue type, check lessons
for issue_type in set(issue_types):
    lesson_result = neuraltree_lesson_match(
        symptom=issue_type,
        project_root=".",
    )
    if lesson_result.get("matches"):
        # Feed lesson context into Claude's analysis
        emit(f"  Lesson found for '{issue_type}': {lesson_result['matches'][0]['lesson']}")
```

These lessons inform your reasoning in Step 2. For example, if a lesson says
"splitting files 3+ hops from trunk made things worse," factor that into your
severity assessment for `too_large` issues on deeply nested files.
```

- [ ] **Step 2: Commit**

```bash
git add src/skill/sections/analyze.md
git commit -m "feat: wire lesson_match into analyze phase"
```

---

### Task 5: Wire wiki_lint + lesson_add into Verify phase

**Files:**
- Modify: `src/skill/sections/verify.md`

- [ ] **Step 1: Add wiki_lint health check after scoring**

In `src/skill/sections/verify.md`, add after Step 1 (Score from Knowledge Map), before Step 2:

```markdown
## Step 1b: Wiki Health Check

Run wiki_lint on the sandbox to catch structural issues the score metrics miss:

```
lint_result = neuraltree_wiki_lint(project_root=sandbox_root)

if lint_result.get("broken_links"):
    emit(f"  WARNING: {len(lint_result['broken_links'])} broken links found")
if lint_result.get("orphan_pages"):
    emit(f"  INFO: {len(lint_result['orphan_pages'])} orphan pages")

health_score = lint_result.get("health_score", 0)
emit(f"  Wiki health: {health_score}/100")
```

If broken links > 0, flag the sandbox changes as needing review before approval.
```

- [ ] **Step 2: Add lesson_add on discard**

In `src/skill/sections/verify.md`, modify Step 4 (Sandbox Approval). After the `else` branch (score did not improve), add:

```markdown
If the user rejects changes OR score decreased, record what failed:

```
if "reject" in response.lower() or delta <= 0:
    neuraltree_lesson_add(
        lesson_text=f"## {mode} run failed (delta={delta:+.3f})\n"
                    f"- Actions attempted: {len(approved_actions)}\n"
                    f"- Score before: {before:.3f}, after: {after:.3f}\n"
                    f"- Reason: {'user rejected' if 'reject' in response.lower() else 'score decreased'}",
        domain="autoloop",
        project_root=".",
    )
    emit("Lesson recorded for future runs.")
```
```

- [ ] **Step 3: Commit**

```bash
git add src/skill/sections/verify.md
git commit -m "feat: wire wiki_lint + lesson_add into verify phase"
```

---

### Task 6: Merge Explore + Map into Understand phase

**Files:**
- Create: `src/skill/sections/understand.md`
- Delete: `src/skill/sections/explore.md`
- Delete: `src/skill/sections/map.md`
- Modify: `src/skill/SKILL.md`

- [ ] **Step 1: Create understand.md**

Create `src/skill/sections/understand.md` that combines explore.md and map.md:

```markdown
# Understand Phase — Explore + Map

> Read deeply. Build the graph. Understand before fixing.

**Input:** `scan_result`, `agent_count`, `knowledge_files`, `dirs`.
**Output:** `knowledge_map` saved to `.neuraltree/knowledge_map.json`.

This phase combines exploration (parallel agent reading) with map synthesis
(knowledge graph construction) into a single "understand" step.

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
emit(f"Phase 1/5: Explored {total_files_explored} files with {agent_count} agents. {total_issues_found} issues found.")
```

## Step 4: Compute Semantic Edges via Viking

For each file in the explorer reports, query Viking with the file's topic
as search text. The top results that are OTHER known files (not itself)
become semantic edges.

```
semantic_edges = []
all_file_paths = set()
for report in explorer_reports:
    for f in report["files"]:
        all_file_paths.add(f["path"])

queries = []
for report in explorer_reports:
    for f in report["files"]:
        queries.append({"text": f["topic"], "source_file": f["path"]})

# Call Viking with all file topics as queries
precision_result = neuraltree_precision(
    queries=[{"text": q["text"]} for q in queries],
    project_root=".",
    limit=3,
)

# For each query result, find matches that are known project files
for i, qr in enumerate(precision_result["query_results"]):
    source_file = queries[i]["source_file"]
    for hit in qr.get("judgments", []):
        uri = hit["uri"]
        matched_path = None
        for known_path in all_file_paths:
            basename = known_path.split("/")[-1]
            if basename in uri and known_path != source_file:
                matched_path = known_path
                break
        if matched_path:
            semantic_edges.append({
                "source": source_file,
                "target": matched_path,
                "weight": round(hit["score"], 3),
                "reason": f"Viking similarity: {hit['score']:.3f}",
            })
```

**If Viking is unavailable (DEGRADED_MODE):** Skip this step. Pass
`semantic_edges=None` to the build action. The map will have reference
and co-location edges only.

## Step 5: Build the Knowledge Map

```
result = neuraltree_knowledge_map(
    action="build",
    project_root=".",
    explorer_reports=explorer_reports,
    semantic_edges=semantic_edges,
)
```

The tool saves the map to `.neuraltree/knowledge_map.json` automatically.

**If `result` contains an `"error"` key:** Stop and report the error to the user.

## Step 6: Emit Summary

```
stats = result["stats"]
emit(f"Phase 1/5: Understand complete — {stats['total_files']} files, "
     f"{stats['total_edges']} edges, {stats['total_clusters']} clusters, "
     f"{stats['total_issues']} issues")
```

**Proceed to Analyze (read `sections/analyze.md`).**
```

- [ ] **Step 2: Delete old phase files**

```bash
rm src/skill/sections/explore.md
rm src/skill/sections/map.md
```

- [ ] **Step 3: Update SKILL.md routing**

In `src/skill/SKILL.md`, replace the section file listing (lines 22-29):

```markdown
```
SKILL.md (this file)        — always loaded: activation + principles + routing
sections/understand.md      — Phase 1: explore + map (parallel agents + knowledge graph)
sections/analyze.md         — Phase 2: Claude-driven issue analysis
sections/plan.md            — Phase 3: reorganization proposals
sections/execute.md         — Phase 4: sandbox execution
sections/verify.md          — Phase 5: adaptive scoring verification
sections/report.md          — Output: before/after comparison
```
```

Update the Pipeline Routing section (lines 176-209) to 5 phases:

```markdown
### Phase 1: Understand
**Read `sections/understand.md` and execute all steps.**
Launch N explorer agents in parallel. Each reads a directory slice deeply.
Synthesize reports into dual-layer knowledge map.
Save to `.neuraltree/knowledge_map.json`.

### Phase 2: Analyze
**Read `sections/analyze.md` and execute all steps.**
Check lessons for past patterns. Claude reads the knowledge map and REASONS
about what's wrong. No formulas — understanding-driven issue identification.
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
Run wiki_lint health check. Score with adaptive mode. Compare before/after.
Record lessons on failure. Score VALIDATES the changes — it doesn't drive them.

### Report
**Read `sections/report.md` and execute.**
Before/after comparison. Knowledge map summary. Action log.
```

Update the MCP Tools Reference table — remove predict/calibration from Scoring row:
```markdown
| Scoring | `neuraltree_score`, `neuraltree_diagnose` |
```

Update tool count from 25 to 24 in the frontmatter and activation output.

Update the mode detection pipeline labels to use 5 phases:
```markdown
| No knowledge map | **full** | Understand → Analyze → Plan → Execute → Verify |
| Map exists, stale (>7 days) | **refresh** | Understand → Analyze → Plan → Execute → Verify |
| Map exists, recent, score < 0.60 | **fix** | Analyze → Plan → Execute → Verify |
| Map exists, recent, score >= 0.60 | **check** | Verify only (quick re-score) |
```

Update the subcommands table — add `auto` routing to autoresearch:
```markdown
| `/neuraltree auto` | Runs /autoresearch with flow_score sub-metrics as targets |
```

- [ ] **Step 4: Update phase numbers in analyze.md, plan.md, execute.md, verify.md, report.md**

In `analyze.md` line 121: change `Phase 3/6` to `Phase 2/5`
In `plan.md`: change any `Phase 4/6` to `Phase 3/5`
In `execute.md`: change any `Phase 5/6` to `Phase 4/5`
In `verify.md` line 48: change `Phase 6/6` to `Phase 5/5`

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH=src python3.11 -m pytest tests/ -v --tb=short`
Expected: All pass (skill files are not tested by pytest — they're markdown)

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: merge explore+map into understand phase (6→5 phases)"
```

---

### Task 7: Update CLAUDE.md and README.md

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `docs/concepts/autoloop.md`

- [ ] **Step 1: Update CLAUDE.md**

Key changes:
- Tool count: 26 → 24
- Pipeline: 6 phases → 5 phases (Understand → Analyze → Plan → Execute → Verify)
- Remove from MCP Tools table: `predict`, `update_calibration`
- Remove "Scoring" having predict/calibration
- Add "Wiki" category with `wiki_lint`
- Fix Integration Points section — remove false claims:
  - Remove: "Lesson recording happens after autoloop KEEP/HOLD/DISCARD decisions" → replace with: "lesson_match is called in Analyze phase, lesson_add records failures in Verify phase"
- Update Pipeline section to show 5 phases
- Update Project Structure section: remove explore.md and map.md, add understand.md

- [ ] **Step 2: Update README.md**

Key changes:
- Tool count references
- Pipeline description (5 phases)
- Remove predict/calibration from tool listings

- [ ] **Step 3: Update autoloop.md concept page**

Replace content to reflect autoresearch integration:

```markdown
# Autoloop

**Autonomous improvement via `/autoresearch` with flow_score sub-metrics.**

NeuralTree's autoloop mode delegates autonomous iteration to the
`/autoresearch` skill (Karpathy-inspired). Instead of a custom loop
with custom prediction and lesson recording, autoloop uses:

- **Metric:** Individual flow_score sub-metric (the lowest one)
- **Scope:** Project docs/markdown files
- **Verify:** `neuraltree_score` → parse targeted sub-metric
- **Each iteration:** One pipeline fix (wire/move/split/shrink)
- **Keep/Discard:** Autoresearch handles via git commit/revert
- **Learning:** `neuraltree_lesson_add` records failures in Verify phase

## Usage

```
/neuraltree auto
```

This routes to `/autoresearch` with the neuraltree pipeline as the
modification engine and the lowest flow_score sub-metric as the target.

## Why Autoresearch > Custom Loop

| Custom autoloop (never shipped) | /autoresearch (proven) |
|--------------------------------|----------------------|
| Custom predict tool | Sandbox + real measurement |
| Custom calibration | Git-based keep/discard |
| Custom lesson recording | lesson_add in verify phase |
| Had to be built and maintained | Already exists and works |

## Related

- [Flow Score](flow-score.md) — the metric autoresearch targets
- [Sandbox First](sandbox-first.md) — changes always in sandbox
- [Algorithm in Tool, Judgment in Claude](algorithm-tool-judgment-claude.md)
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md README.md docs/concepts/autoloop.md
git commit -m "docs: update for 24 tools, 5-phase pipeline, autoresearch integration"
```

---

### Task 8: Archive handoff docs

**Files:**
- Move: 11 `docs/HANDOFF_*.md` files → `docs/archive/`

- [ ] **Step 1: Create archive directory and move files**

```bash
mkdir -p docs/archive
mv docs/HANDOFF_2026-04-06_SESSION5.md docs/archive/
mv docs/HANDOFF_2026-04-06_SESSION6.md docs/archive/
mv docs/HANDOFF_2026-04-07_SESSION7.md docs/archive/
mv docs/HANDOFF_2026-04-07_SESSION8.md docs/archive/
mv docs/HANDOFF_2026-04-07_SESSION9.md docs/archive/
mv docs/HANDOFF_2026-04-07_SESSION10.md docs/archive/
mv docs/HANDOFF_2026-04-07_SESSION11.md docs/archive/
mv docs/HANDOFF_2026-04-07_SESSION12.md docs/archive/
mv docs/HANDOFF_2026-04-07_SESSION13.md docs/archive/
mv docs/HANDOFF_2026-04-07_SESSION14.md docs/archive/
mv docs/HANDOFF_2026-04-07_SESSION15.md docs/archive/
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "chore: archive 11 handoff docs (fixes reachability)"
```

---

### Task 9: Rebuild knowledge map + re-score

**Files:**
- Runtime only (no file edits — MCP tool calls)

- [ ] **Step 1: Rebuild knowledge map**

After all file changes, the knowledge map is stale. Rebuild it:

```
neuraltree_knowledge_map(action="build", project_root="/home/neil1988/neuraltree", explorer_reports=<fresh reports>)
```

This requires running the understand phase (explorer agents → build).

- [ ] **Step 2: Re-score**

```
neuraltree_score(project_root="/home/neil1988/neuraltree")
```

Expected: reachability should jump from 0.882 → ~0.98 (handoffs archived).

- [ ] **Step 3: Re-run precision**

```
queries = neuraltree_generate_queries(project_root="/home/neil1988/neuraltree")
precision = neuraltree_precision(queries=queries["queries"], project_root="/home/neil1988/neuraltree")
# Judge and compute precision@3
```

Expected: precision@3 should improve (handoff noise removed from Viking results).

- [ ] **Step 4: Run full test suite one final time**

Run: `PYTHONPATH=src python3.11 -m pytest tests/ -v --tb=short`
Expected: All pass. Count should be ~345 (was 429, minus ~84 deleted).

---

## Execution Order and Dependencies

```
Task 1 (relocate util)      — MUST be first (unblocks Task 2)
Task 2 (delete predict)     — depends on Task 1
Task 3 (verify integration) — depends on Task 2
Task 4 (wire lessons)       — independent
Task 5 (wire wiki_lint)     — independent
Task 6 (merge phases)       — independent
Task 7 (update docs)        — depends on Tasks 2, 4, 5, 6
Task 8 (archive handoffs)   — independent
Task 9 (rebuild + re-score) — MUST be last (after all changes)
```

**Parallelizable groups:**
- Wave 1: Task 1
- Wave 2: Tasks 2, 4, 5, 6, 8 (all independent after Task 1)
- Wave 3: Tasks 3, 7 (depend on wave 2)
- Wave 4: Task 9 (final verification)
