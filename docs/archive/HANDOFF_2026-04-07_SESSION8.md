# Session 8 Handoff — 2026-04-07

## What Was Done

### 1. Committed & Pushed Session 7 Work
- Commit `fda592d`: Viking semantic edges, value filter, usefulness gate, 385 tests
- Commit `671afec`: Fixed 4 pipeline issues (dead refs, buried lesson, lessons wiring, 46KB spec deleted)

### 2. Ran Full `/neuraltree` Pipeline on Itself
First complete end-to-end pipeline run with Viking semantic edges:
- **Phase 1 Explore:** 2 agents, 17 files read deeply
- **Phase 2 Map:** 59 edges (32 reference + 9 semantic + 18 co-location), 14 clusters
- **Phase 3 Analyze:** 0 issues (value filter correctly dropped all cosmetic findings)
- **Phase 4-5:** Skipped (no issues)
- **Phase 6 Verify:** Flow score 0.31 (bootstrap baseline)

Viking semantic edges confirmed working — `type: "semantic"` edges appear in the knowledge map.

### 3. Discovered Core Scoring Problem
The score (0.31) contradicted the analysis (0 issues). Root cause: scoring measured neuraltree-specific formatting (`## Related`, `last_verified` frontmatter, `_INDEX.md`) instead of actual organization quality. The skill is meant to organize ANY project — scoring formatting conventions is backwards.

### 4. Rewrote Entire Scoring System (13 files)

**Old metrics (neuraltree-specific, REMOVED):**
- `hop_efficiency` — counted `## Related` sections
- `synapse_coverage` — % of files with `## Related`
- `dead_neuron_ratio` — orphans based on `## Related` refs
- `freshness` — % of files with `last_verified` frontmatter
- `trunk_pressure` — trunk line count vs arbitrary cap

**New metrics (universal, knowledge-map-based):**
| Metric | Weight | What It Measures |
|--------|--------|------------------|
| `reachability` | 0.30 | BFS from entry points via ALL edge types (ref + semantic + co-loc) |
| `connectivity` | 0.25 | % of files with ≥1 edge in the knowledge graph |
| `cluster_coherence` | 0.20 | % of related file pairs sharing a parent directory |
| `size_balance` | 0.15 | % of files within 3× median size (no mega-files) |
| `discoverability` | 0.10 | precision@3 from Viking (computed by skill) |

**Key design decisions:**
- Knowledge map is REQUIRED for scoring — no more filesystem scanning for `## Related`
- Entry points auto-detected (README.md, CLAUDE.md, etc.)
- All edge types count equally for reachability
- `adaptive` parameter kept for API compat but is a no-op

**Diagnose gap types updated:**
- Removed: `SYNAPSE_GAP`, `FRESHNESS_GAP`
- Added: `ISOLATION_GAP` (file has no edges in graph)
- Kept: `CONTENT_GAP`, `EMBEDDING_GAP`, `FOCUS_GAP`

**Predict actions updated:**
- Removed: `wire`, `wire_orphans`, `re_wire`, `update_freshness`, `generate_index`, `index_dirs`
- Added: `connect` (add references), `relocate` (improve coherence)
- Kept: `split`, `split_large`, `delete`, `archive`, `viking_index`, `index`

### 5. Test Count
- **Before:** 385 tests
- **After:** 397 tests (rewrote 3 unit + updated 3 integration test files)
- **All passing.**

## Final State

- **Branch:** main (commit `88abf8c`)
- **Tests:** 397 passing
- **Tools:** 25 (scoring tools now read knowledge map)
- **Skill:** v2 with universal scoring, value filter, Viking semantic edges

## Files Changed

```
src/neuraltree_mcp/scoring/score.py        — FULL REWRITE: universal metrics from knowledge map
src/neuraltree_mcp/scoring/diagnose.py     — Removed SYNAPSE/FRESHNESS_GAP, added ISOLATION_GAP
src/neuraltree_mcp/scoring/predict.py      — New actions (connect, relocate), removed formatting actions
src/skill/sections/verify.md               — Updated to new metric names
src/skill/sections/report.md               — Updated report format with new metrics
CLAUDE.md                                  — Updated integration points
tests/unit/test_score.py                   — FULL REWRITE: 29 tests for new metrics
tests/unit/test_diagnose.py                — Updated gap types
tests/unit/test_predict.py                 — Updated actions and metric names
tests/integration/test_tool_calls.py       — Updated to create knowledge maps for score tests
tests/integration/test_degraded_mode.py    — Updated metric names, degraded cap 0.90
tests/integration/test_e2e_pipeline.py     — Updated predict/score to new metrics
tests/integration/test_knowledge_map.py    — Replaced adaptive tests with universal score tests
lessons/v2-design-decisions.md             — Created (extracted from SESSION6)
lessons/_INDEX.md                          — Added v2-design-decisions entry
lessons/autoloop.md                        — Updated dead spec reference
docs/HANDOFF_2026-04-06_SESSION6.md        — Fixed dead references
docs/specs/ (directory)                    — Deleted (46KB dead spec removed)
```

## What NEEDS TO BE DONE (Next Session)

### Priority 1: Restart MCP & Test New Scoring Live
MCP server must restart to pick up the new scoring code. Then:
1. Run `/neuraltree` on neuraltree itself
2. Verify the score now reflects actual organization quality (should be high — project is clean)
3. Confirm score + analysis agree (both should say "well organized")

### Priority 2: Test on a Larger Project
Run `/neuraltree` on LocaNext or another project with 100+ knowledge files to validate:
- Universal metrics at scale
- Viking semantic edge quality
- Value filter behavior
- Agent scaling (5-7 agents)

### Priority 3: Improve Explorer Prompt
Explorers still report "Missing frontmatter" and "Missing ## Related" on standard project files. These are now irrelevant to scoring but waste explorer time. Update `explore.md` to NOT flag formatting conventions.

### Priority 4: Viking Project Filtering
Viking returns results from ALL indexed projects (neuraltree, newfin, memory, sandbox). This dilutes discoverability scores. Options:
- Filter Viking results to target project URIs in `neuraltree_precision`
- Or accept as a Viking indexing concern, not a neuraltree concern

### Priority 5: Cluster Quality
14 clusters for 17 files (almost 1:1). The greedy algorithm needs 2+ shared concepts to expand clusters, but each file's concepts are too unique. Consider using Viking embeddings for cluster similarity instead of keyword overlap.

## Design Lessons Learned This Session

1. **Score what matters, not what's easy to measure.** The old scoring measured formatting conventions because they were easy to detect programmatically. But the skill's goal is organization — which requires understanding the knowledge graph, not scanning for `## Related` sections.

2. **Score and analysis must agree.** If the analysis says "0 issues" but the score says "0.31 (bad)", one of them is wrong. In this case the analysis was right and the score was measuring the wrong things.

3. **Knowledge map is the single source of truth.** Once you have a knowledge map with edges and clusters, scoring should read THAT — not re-scan the filesystem for different signals. The map already captures all the structural information needed.
