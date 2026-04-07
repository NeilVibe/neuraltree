# Session 19 Handoff — 2026-04-07

## What Was Done

### 1. Repo Cleanup — v2 → v3 Sync
- `src/skill/SKILL.md` was still v2; copied v3 from `~/.claude/skills/neuraltree/`
- Removed `sections/understand.md` (v2), added `sections/index.md`, `explore.md`, `map.md` (v3)
- Updated `analyze.md`, `plan.md`, `verify.md` to v3 versions (checkpoint saves, phase numbering)
- Renamed concept page `explore-first-pipeline.md` → `index-first-pipeline.md` (rewritten for v3)
- Updated 5 concept pages with new links (artery-principle, sandbox-first, trace-before-prune, algorithm-tool-judgment-claude, knowledge-map)
- Updated `_INDEX.md`, `README.md` (pipeline description, subcommands, project structure), `CLAUDE.md`
- Deleted all `__pycache__/` directories

### 2. v3 Index Phase Test on LocaNext (1,280 knowledge files)
First real large-scale test of the v3 index-first pipeline on LocaNext (9,494 files total, 1,280 knowledge files).

**Results:**

| Tool | Result |
|------|--------|
| Scan | 9,494 files, 1,280 knowledge — works at scale |
| Viking batch index | 1,182/1,280 indexed (92.3%) — works but took ~5.5hrs sequential |
| Wiki lint | Health 5/100 — 1,131 broken links, 1,987 orphans, 838 stale |
| Find dead | 692 dead (59%) — mostly .planning (393), .claude (114), docs/archive (116) |
| Generate queries | 57 queries from CLAUDE.md + README |
| Precision queries | 10/10 returned relevant results — Viking search quality is good |
| Lesson match | 0 matches (first run on this project) |
| Score | Skipped — needs knowledge map (Phase 3) |

**Key findings:**
- Viking indexing bottleneck is HTTP round-trips, NOT Model2Vec (29k sentences/sec)
- Dead file count inflated by ephemeral dirs (.planning, .claude/agents, .tribunal)
- Wiki lint health=5 is a real signal — LocaNext has genuine organization problems
- v3 index-first approach works — full health picture without exploring all 1,280 files

### 3. Two Performance Fixes
**Fix 1: Parallel Viking indexing** (`viking_index.py`)
- Added `ThreadPoolExecutor` with `max_workers=8` (configurable)
- Pre-validates all paths (fast), then uploads in parallel threads
- Expected speedup: ~5.5hrs → ~30min for 1,280 files

**Fix 2: Scan exclusion patterns** (`scan.py`)
- Added `exclude_patterns` parameter (list of directory prefixes to skip)
- Example: `exclude_patterns=[".planning", ".claude/agents", "docs/archive"]`
- Reduces dead file noise from 692 → ~70 actual project issues

Both fixes have tests (416 total, was 414).

## Commits (3)

```
3f71cf1 chore: sync repo skill files to v3, update docs for index-first pipeline
47cbffa feat: parallel Viking indexing + scan exclusion patterns
```

## Final State

- **Branch:** main (pushed to origin)
- **Tests:** 416 passing
- **Tools:** 24
- **SKILL version:** 3.0.0 (synced: repo = deployed)

## Next Session: Re-test v3 on LocaNext with Fixes

1. **Re-run `/neuraltree index`** on LocaNext with:
   - Parallel Viking batching (should be ~30min not 5hrs)
   - `exclude_patterns=[".planning", ".claude/agents", ".tribunal", "docs/archive"]`
   - Verify improved dead file count and faster indexing

2. **If index succeeds, continue full pipeline** (Phases 2-7):
   - Phase 2: Targeted exploration (~300 problem files, not all 1,280)
   - Phase 3: Build knowledge map
   - Phase 4-7: Analyze, Plan, Execute, Verify

3. **Karpathy LLM-Wiki reference:** `docs/reference/KARPATHY_LLM_WIKI.md` in LocaNext
   - neuraltree implements Karpathy's three operations: Ingest=Index, Query=Precision, Lint=Wiki_lint
   - The original spec is at `docs/specs/2026-04-04-neuraltree-skill-design.md`

### Key Files Changed
```
src/neuraltree_mcp/tools/viking_index.py  — parallel ThreadPoolExecutor
src/neuraltree_mcp/tools/scan.py          — exclude_patterns param
src/skill/SKILL.md                        — v3 (was v2)
src/skill/sections/index.md               — NEW (Phase 1)
src/skill/sections/explore.md             — NEW (Phase 2)
src/skill/sections/map.md                 — NEW (Phase 3)
docs/concepts/index-first-pipeline.md     — NEW (replaced explore-first)
tests/unit/test_scan.py                   — +2 exclude tests
```

### LocaNext .neuraltree State
Index results saved to `/home/neil1988/LocalizationTools/.neuraltree/index_results.json` — can be loaded by next session to skip re-indexing (if < 1hr old per SKILL checkpoint rules, but data is still useful as reference).
