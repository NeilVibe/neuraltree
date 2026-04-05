# Session 4 Handoff — 2026-04-06

## What Was Done

### 1. Project Cleanup (-3,344 lines of dead docs)
Deleted all completed plans, handoffs, and proof run logs:
- `docs/superpowers/plans/` (2 files, 1,726 lines)
- `docs/PHASE1_PLAN.md`, `docs/PHASE1_5_PLAN.md`, `docs/HANDOFF*.md` (5 files, 1,255 lines)
- `docs/AUTOLOOP_PROOF_RUN.md`, `docs/FEATURE_INCIDENT_MEMORY.md` (232 lines)
- Empty `tests/mock/` dir, all `__pycache__/`, `.ruff_cache/`, `.pytest_cache/`

### 2. Viking + Qwen3.5 Integration (THE BIG ONE)

**Problem:** SKILL.md told Claude to call `viking_search()` and use Qwen3.5 as LLM judge — but Claude had no MCP tools to reach either service. The skill was unexecutable.

**Fix:** Two new MCP tools that bring both services inside neuraltree-mcp:

- **`neuraltree_precision(queries, ...)`** — takes generated queries, searches Viking for top-3 results per query, reads content, asks Qwen3.5 (via Ollama) for YES/NO relevance judgments, returns `precision_at_3` and per-query results. One call replaces 50+ manual tool calls.

- **`neuraltree_viking_index(file_paths, ...)`** — batch-uploads local files to Viking via temp_upload + register API. Used by Enforce step to re-index modified files.

### 3. Code Review (3 agents, all findings fixed)
- ERROR verdicts now excluded from precision denominator (was corrupting score)
- Absolute path injection guard on viking_index
- XML delimiters in LLM prompt (anti-injection)
- Empty input / limit=0 / invalid root guards
- ValueError catch on HTTP JSON parsing
- 10 additional test cases covering all flagged gaps

### 4. Documentation Updates
- CLAUDE.md, README.md, install.sh all updated for 24 tools
- README now lists 3 prerequisites: neuraltree-mcp, Viking, Ollama+Qwen3.5
- SKILL.md Section 4 Steps 2-3 replaced with `neuraltree_precision` call
- SKILL.md Section 7 Step 2 replaced with `neuraltree_viking_index` call
- All `viking_add_resource()` references replaced throughout SKILL.md

## Current State

```
24 MCP tools, 316 tests passing
SKILL.md: 2,204 lines, 9 sections — ALL tool calls now go through neuraltree-mcp
```

### Tool Availability Audit (EVERY tool the skill references)

All 24 MCP tools: ✓ available via neuraltree-mcp
All 13 helper functions: ✓ Claude's native capabilities (Read, Write, Edit, Bash, ask user)
External service calls in SKILL.md: 0 (was 2 — Viking + Ollama now handled internally)

## What's Next — Testing on a Real Project

The skill has NEVER been tested end-to-end by actually invoking `/neuraltree` on a real project. All testing so far has been:
- Unit tests (316 passing, mocked)
- Manual pipeline runs via Python scripts
- Live Viking + Qwen3.5 API calls confirmed working

### To Test on NewFin (or any project):

1. Ensure neuraltree-mcp is registered in `~/.claude.json`
2. Ensure Viking is running (`~/.openviking/start_viking.sh`)
3. Ensure Ollama is running with Qwen3.5 (`ollama serve` + model pulled)
4. `cd` to the target project
5. Run `/neuraltree`

### What to Watch For:

1. **Does SKILL.md load as a skill?** — the frontmatter needs to be recognized by Claude Code
2. **Does Section 1 activation work?** — scan + precision health check
3. **Does Section 4 benchmark complete?** — queries + precision + structural score
4. **Does Section 5 diagnose produce useful gap classifications?**
5. **Does Section 6 AutoLoop actually improve the score?** — the Karpathy loop: propose → backup → execute → measure → keep/discard
6. **Does Section 7 enforce persist everything?** — state.json, queries.json, history/, Viking re-index
7. **Does Section 8 report look right?** — metric table, action lists, interactive pending actions

### Known Gaps / Risks:

- **Skill loading:** SKILL.md is 2,204 lines — heavy context load. If Claude truncates it, later sections may be lost.
- **Viking content:** Viking needs to have the target project indexed FIRST for precision_at_3 to be meaningful. On bootstrap, everything will be EMBEDDING_GAP. The enforce step should index everything afterward.
- **Sandbox on non-git repos:** `neuraltree_sandbox_create` uses git worktrees. Falls back to rsync if no git — but that fallback path is less tested.
- **`neuraltree_predict`** is built and tested but NOT used anywhere in SKILL.md (the AutoLoop uses score-based keep/discard instead of predictions). Consider wiring it in or removing it.
- **`neuraltree_shrink_and_wire`** and **`neuraltree_split_and_wire`** are built but NOT referenced in SKILL.md — the skill uses `neuraltree_plan_split` + manual execution instead. Could simplify Section 8 SPLIT handling.

## Files Changed This Session

```
NEW:
  src/neuraltree_mcp/tools/precision.py      — Viking search + LLM judge tool
  src/neuraltree_mcp/tools/viking_index.py   — batch Viking indexing tool
  tests/unit/test_precision.py               — 26 tests
  tests/unit/test_viking_index.py            — 20 tests
  docs/HANDOFF_2026-04-06_SESSION4.md        — this file

MODIFIED:
  src/neuraltree_mcp/server.py               — registers 2 new tools (24 total)
  src/skill/SKILL.md                         — replaced Viking/Ollama sections with MCP calls
  tests/integration/test_server.py           — tool count 22→24
  requirements.txt                           — added requests
  CLAUDE.md                                  — updated counts, deps, structure
  README.md                                  — updated counts, prereqs, architecture
  install.sh                                 — updated tool count check

DELETED:
  docs/superpowers/plans/* (2 files)
  docs/PHASE1_PLAN.md, PHASE1_5_PLAN.md
  docs/HANDOFF*.md (3 files)
  docs/AUTOLOOP_PROOF_RUN.md
  docs/FEATURE_INCIDENT_MEMORY.md
```

## Commit

`4711749` — `feat: Viking+Qwen integration — neuraltree_precision + neuraltree_viking_index`
