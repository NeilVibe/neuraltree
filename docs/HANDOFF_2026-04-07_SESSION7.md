# Session 7 Handoff — 2026-04-07

## What Was Done

### 1. Cleaned Dead Files
- Deleted `.neuraltree/` (stale knowledge map + calibration from aborted Session 6 run)
- Deleted `docs/superpowers/plans/2026-04-06-neuraltree-v2-explore-first.md` (58KB dead plan, 1740 lines)
- Deleted `docs/HANDOFF_2026-04-06_SESSION4.md` (superseded v1 handoff)
- Removed empty `docs/superpowers/` directory tree

### 2. Ran Full Pipeline on Itself (2 runs)

**Run 1 (no value filter):** Produced 7 issues — 3 were busywork (wire all files, add frontmatter to README, pad index). Signal-to-noise: 57%.

**Run 2 (with value filter):** Produced 4 issues — all genuine. Signal-to-noise: 100%.

Both runs completed Phases 1-3 (Explore → Map → Analyze). Phases 4-6 (Plan → Execute → Verify → Report) were NOT executed.

### 3. Added Value Filter to Analyze Phase (`analyze.md`)
New Step 3 between assessment and issue production. Four filter rules:
- **DROP "unwired"** if files already have a working reference chain (e.g., pipeline section files)
- **DROP "missing frontmatter"** for standard project files (CLAUDE.md, README.md, LICENSE, etc.)
- **DROP any fix** where you can't name the beneficiary ("who fails to find what?")
- **DROP padding/expansion** for its own sake (short but complete files are fine)

### 4. Added Usefulness Gate to Plan Phase (`plan.md`)
New Step 2 before tracing/presenting actions. Decision table:
- "Someone can't find critical information" → KEEP
- "A metric improves but nothing practical changes" → DROP

### 5. Replaced Jaccard with Viking Semantic Edges

**Design decision:** Jaccard on agent-written `key_concepts` is a weak approximation of what Viking (Model2Vec) already does better. Jaccard misses synonyms, depends on agent word choice. Viking catches meaning.

**Changes:**
- `knowledge_map.py`: Removed internal Jaccard computation (lines 122-148). Added `semantic_edges` parameter to `_build_map()` and tool registration. The skill queries Viking, passes edges in. Tool assembles the graph.
- `map.md`: Rewritten. Step 1 queries Viking for each file's semantic neighbors. Step 2 passes results to build action.
- Import `jaccard` from `text_utils` removed from `knowledge_map.py` (still used by `wire.py` and `lesson.py`).

### 6. Three-Agent Code Review + Fixes

| # | Finding | Fix |
|---|---------|-----|
| 1 | Broad catch says "Malformed explorer report" for ALL errors | Changed to "Failed to build map" |
| 2 | No type validation on `semantic_edges` param | Added `isinstance(semantic_edges, list)` check |
| 3 | Non-numeric weight crashes `round()` | Validates type, skips with warning |
| 4 | `analyze.md` uses `km_result["map"]` but tool returns `"knowledge_map"` | Fixed key name |
| 5 | `map.md` references undefined `extract_path_from_viking_uri` | Inlined URI matching logic |
| 6 | Dedup keeps first edge, not highest weight | Best weight wins |
| 7 | `_ensure_list` drops tuples silently | Added tuple/set/frozenset support |
| 8 | Co-location suppression by semantic edges untested | New test |
| 9 | Malformed semantic_edges entries untested | 4 new tests |

### 7. Test Count
- **Before:** 384 tests
- **After:** 385 tests (removed 10 Jaccard tests, added 11 Viking/validation tests)
- **All passing.**

## Final State

- **Branch:** main (uncommitted — needs commit)
- **Tests:** 385 passing
- **Tools:** 25 (semantic edges now via `semantic_edges` param, not internal Jaccard)
- **Skill:** v2 with value filter, usefulness gate, Viking semantic edges

## Files Changed

```
src/neuraltree_mcp/tools/knowledge_map.py    — Jaccard removed, semantic_edges param added, validation, best-weight dedup
src/skill/sections/analyze.md                — +36 lines: value filter (Step 3)
src/skill/sections/plan.md                   — +17 lines: usefulness gate (Step 2)
src/skill/sections/map.md                    — rewritten: Viking semantic edges instead of Jaccard
tests/unit/test_knowledge_map.py             — -10 Jaccard tests, +11 Viking/validation tests
tests/integration/test_knowledge_map.py      — replaced Jaccard test with 2 Viking tests
CLAUDE.md                                    — test count 385
docs/HANDOFF_2026-04-06_SESSION4.md          — deleted (superseded v1)
docs/superpowers/plans/...                   — deleted (58KB dead plan)
```

## What NEEDS TO BE DONE (Next Session)

### Priority 1: Commit This Work
All changes are uncommitted. Review the diff and commit.

### Priority 2: Finish the Pipeline (Plan → Execute → Verify → Report)
The pipeline found 4 genuine issues but never executed fixes:

| # | Issue | What to Do |
|---|-------|------------|
| 1 | **SESSION6 dead refs** (HIGH) | Edit `docs/HANDOFF_2026-04-06_SESSION6.md`: remove references to SESSION4, plans dir, and `lessons/v2-design-decisions.md` that don't exist |
| 2 | **Design lesson buried** (HIGH) | Extract "algorithms in tools, judgment in skills" from SESSION6 bottom → create `lessons/v2-design-decisions.md`, update `lessons/_INDEX.md` |
| 3 | **lessons/ dead zone** (MEDIUM) | Ensure CLAUDE.md or README.md has a path to lessons/ (will happen naturally when lesson file is created and indexed) |
| 4 | **46KB spec dead weight** (MEDIUM) | Trace `docs/specs/2026-04-04-neuraltree-skill-design.md` (referenced by `lessons/autoloop.md` 3 times), update refs, then delete |

### Priority 3: Test Viking Semantic Edges Live
The Viking integration in `map.md` was written but never tested in a live pipeline run. The MCP server needs restart to pick up the new `semantic_edges` parameter. Then:
1. Restart session (MCP reload)
2. Run `/neuraltree` — Map phase should now query Viking and pass semantic edges
3. Verify the knowledge map has `type: "semantic"` edges from Viking (not Jaccard)

### Priority 4: Test on a Larger Project
Run `/neuraltree` on LocaNext or another project with 100+ knowledge files to validate:
- Viking semantic edge quality at scale
- Value filter behavior with more complex file relationships
- Agent scaling (5-7 agents)

### Priority 5: Improve Explorer Prompt
Explorers still report "Missing frontmatter" and "Missing ## Related" on standard project files. The value filter catches this, but it's wasted work. Update the explorer prompt in `explore.md` to NOT flag these on standard files (CLAUDE.md, README.md, LICENSE, requirements.txt, etc.).

## Design Lessons Learned This Session

1. **Value filter is essential.** Without it, the pipeline proposes busywork (wire everything, add frontmatter everywhere). The filter asks "who benefits?" and drops metric-only actions. Signal-to-noise went from 57% to 100%.

2. **Viking > Jaccard for semantic similarity.** Jaccard on agent-written tags is a weak approximation. Viking (Model2Vec embeddings) catches synonyms, paraphrases, and conceptual similarity. Drop Jaccard, use Viking.

3. **Review agents catch real bugs.** The 3-agent review found a key name bug in analyze.md that would have crashed the pipeline at runtime. Also caught the misleading error message pattern that would have made debugging impossible.

## Known Issues

1. **`.neuraltree/knowledge_map.json` exists** from the pipeline run — built with old Jaccard logic, not Viking. Will be rebuilt on next run.
2. **`docs/specs/2026-04-04-neuraltree-skill-design.md`** — 46KB, referenced by lessons/autoloop.md. Approved for deletion but not yet executed.
3. **install.sh** — still says 25 tools (correct). No change needed.
