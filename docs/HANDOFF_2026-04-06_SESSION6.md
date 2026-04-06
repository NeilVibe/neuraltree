# Session 6 Handoff — 2026-04-06

## What Was Done

### 1. Tested v2 Skill Live (Pipeline Run on neuraltree itself)

Ran `/neuraltree` end-to-end on the neuraltree project (bootstrap mode, 15 knowledge files).

**Phases completed:**
- **Activate** — neuraltree-mcp PASS (25 tools), Viking PASS, mode=full, agents=2
- **Explore** — 2 parallel explorer agents launched, 17 files read deeply, structured JSON reports returned
- **Map** — PROBLEM FOUND (see below)
- **Analyze** — 5 issues identified (1 critical, 1 high, 2 medium, 1 low)
- **Plan** — traced 2 destructive targets (both dead orphans), presented 7 actions to user

**Pipeline was cancelled at Plan phase** to fix the Map phase design flaw.

### 2. Discovered Core Design Flaw: Claude Skips Algorithmic Steps

The Map phase had 190 lines of pseudocode instructing Claude to:
- Compute 136 pairwise Jaccard similarity scores
- Run a greedy clustering algorithm
- Build co-location edges for every directory group
- Detect orphans from the edge graph

**What actually happened:** Claude read the pseudocode, understood the intent, and produced an approximation by intuition — building ~5 edges by hand instead of computing all 136 pairs, clustering by gut feel instead of running the greedy algorithm.

**Root cause:** LLMs don't execute algorithms. They reason. Pseudocode in a skill file is a suggestion, not an enforcement mechanism.

**Design principle established:**
```
Algorithm → MCP tool (deterministic, can't be skipped)
Judgment  → Claude (reasoning, decisions)
```

### 3. Built `action="build"` on `neuraltree_knowledge_map` Tool

Added `_build_map(explorer_reports, project_root)` function that deterministically computes:
- **File merging** — union key_concepts, references_to, issues across multiple explorer agents (not last-writer-wins)
- **Reference edges** — from explicit `references_to` in each file report
- **Semantic edges** — pairwise Jaccard on `key_concepts` (threshold > 0.3, overlap >= 2)
- **Co-location edges** — files in same directory (only if no stronger edge exists)
- **Greedy concept clusters** — seed by most concepts (deterministic tie-breaking via sorted paths), expand by 2+ shared
- **Graph-derived issues** — orphan files (no edges), scattered clusters (3+ dirs)
- **Stats** — totals, averages, median, max depth (filtered for files that actually reported size)

The Map phase skill section (`map.md`) was rewritten from 190 lines of pseudocode to a single tool call:
```
result = neuraltree_knowledge_map(action="build", project_root=".", explorer_reports=reports)
```

### 4. Five-Agent Code Review (Round 1)

| Agent | Role | Findings |
|-------|------|----------|
| 1 | Code Quality | 4 issues: non-deterministic clustering, silent last-writer-wins, no-op co-location test, map.md missing error handling |
| 2 | Security | 3 issues: path traversal in explorer paths, O(n^2) unbounded, issues field not validated |
| 3 | Silent Failures | 10 issues: string key_concepts → char-level sets, broad except, missing schema validation, zero-size stats pollution |
| 4 | Test Coverage | 9 gaps: Jaccard boundary at 0.3, overlap=1 case, clustering determinism, duplicate file merge, no-op test |
| 5 | Architecture | Duplicate `_jaccard` (same as `text_utils.jaccard`), extract `_greedy_clusters()` suggestion, interface fit assessment |

### 5. Fixed All 9 Critical/High Review Findings

| # | Issue | Fix |
|---|-------|-----|
| 1 | Path traversal in explorer paths | `_has_path_traversal()` check in merge loop, skip + warn |
| 2 | String `key_concepts` → char-level sets | `_ensure_list()` coercion for key_concepts, references_to, issues |
| 3 | Non-deterministic clustering | `max(sorted(unclustered), ...)` for stable tie-breaking |
| 4 | Last-writer-wins merge loses data | Union merge for concepts/refs/issues, max for size_lines |
| 5 | Duplicate `_jaccard` function | Removed, imports `jaccard` from `text_utils` |
| 6 | Broad except misses TypeError/KeyError | Added second except clause for malformed reports |
| 7 | Missing boundary tests | Added: Jaccard=0.3 exact, overlap=1, determinism, single file, string coercion, path traversal |
| 8 | map.md no error handling | Added error + warnings guidance |
| 9 | size_lines=0 pollutes stats | Filtered to files with size_lines > 0 |

### 6. Updated Docs

- **README.md** — full v2 rewrite: architecture diagram (4 components), pipeline (7 steps), modes (4 instead of 5), subcommands (7), example output (knowledge map + clusters), manual install includes sections/
- **CLAUDE.md** — test count 345→384
- **install.sh** — tool count check 24→25

## Final State

- **Branch:** main (commit `8433094`)
- **Tests:** 384 passing (was 345)
- **Tools:** 25 (new `build` action on existing `neuraltree_knowledge_map` tool)
- **Skill:** v2 with deterministic Map phase, installed at `~/.claude/skills/neuraltree/`

## Next Session: Test Deterministic Pipeline

### Priority 1: Restart and test `/neuraltree` on neuraltree itself
1. **Restart session** — MCP server must reload to pick up the new `build` action (confirmed stale in this session — tool description still shows old `save/load/query` only)
2. **Run `/neuraltree`** — should now use `action="build"` for the Map phase instead of pseudocode
3. **Verify** the Map phase produces edges/clusters/orphans deterministically
4. **Complete the full pipeline** — Execute + Verify + Report phases were never tested

### Priority 2: Execute the pipeline actions from the aborted run
These were approved but never executed:
- **AUTO-FIX:** Wire CLAUDE.md, README.md, handoffs, lessons with `## Related` sections
- **APPROVE:** Delete 17k-line completed plan (dead orphan: `docs/superpowers/plans/2026-04-06-neuraltree-v2-explore-first.md`)
- **APPROVE:** Archive Session 4 handoff (stale v1 content)
- **APPROVE:** Create `lessons/v2-design-decisions.md`

### Priority 3: Test on a larger project
- Run `/neuraltree` on LocaNext or newfin (300+ knowledge files)
- Validates: agent scaling (5-7 agents), Jaccard performance at scale, cluster quality

### Priority 4: Audit other phases for pseudocode-that-gets-skipped
- Explore phase — currently relies on agents following the JSON report format. Should we validate the format in the tool?
- Analyze phase — judgment-based, probably fine
- Plan/Execute/Verify — mostly tool calls, probably fine

## Known Issues

1. **MCP server must be restarted** — `build` action is in the code but the running server is stale
2. **`.neuraltree/` directory exists** from the aborted pipeline run — contains `knowledge_map.json` (manually built, not deterministic) and `.lock` (already removed). The `knowledge_map.json` should be rebuilt by the deterministic tool on next run
3. **install.sh copies all section files** via `*.md` glob — this already works for v2 sections, no fix needed
4. **`docs/superpowers/plans/2026-04-06-neuraltree-v2-explore-first.md`** — 17,281 lines, dead orphan, should be deleted
5. **`docs/HANDOFF_2026-04-06_SESSION4.md`** — describes v1 architecture, superseded by v2, should be archived

## Key Files Changed This Session

```
src/neuraltree_mcp/tools/knowledge_map.py    — _build_map(), _ensure_list(), action="build", merged imports
src/skill/sections/map.md                    — 190 lines pseudocode → 1 tool call + error handling
tests/unit/test_knowledge_map.py             — +29 tests (Jaccard, build, edges, clusters, boundaries)
tests/integration/test_knowledge_map.py      — +11 tests (build action end-to-end)
README.md                                    — full v2 rewrite (pipeline, modes, subcommands, example)
CLAUDE.md                                    — test count 384
install.sh                                   — tool count 25
```

## Design Lesson Learned

> **Skills should not contain pseudocode for Claude to "follow."**
> Claude will understand the intent and approximate the output.
> Put algorithms in MCP tools. Put judgment calls in skills.
> The skill becomes an orchestrator that calls tools and makes decisions.
