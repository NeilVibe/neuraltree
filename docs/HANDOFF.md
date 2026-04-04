> **STATUS: HISTORICAL** — Phase 2 completed 2026-04-05. This document preserved for reference.

# NeuralTree Handoff — Phase 2 Ready

> **Date:** 2026-04-05
> **Status:** Phase 1 + 1.5 COMPLETE. Phase 2 (SKILL.md) is next.
> **Branch:** main
> **Last commit:** `feat: Phase 1 + 1.5 complete — 16 MCP tools, 175 tests, 4 rounds of review`

---

## What Exists

### MCP Server — 16 tools, fully tested, security-hardened

```
src/neuraltree_mcp/
├── __init__.py              (version 0.1.0)
├── server.py                (entry point — registers all 16 tools via register() pattern)
├── validation.py            (validate_project_root + validate_within_root — ALL tools use this)
├── text_utils.py            (shared: extract_keywords, jaccard, walk_project_files, SKIP_DIRS, STOPWORDS, NON_LESSON_HEADINGS)
├── tools/
│   ├── scan.py              (neuraltree_scan — filesystem inventory, 10k file cap)
│   ├── trace.py             (neuraltree_trace — reference tracing via grep)
│   ├── backup.py            (neuraltree_backup + neuraltree_restore — 100MB cap, integrity check)
│   ├── wire.py              (neuraltree_wire — Jaccard similarity, ## Related + ## Docs suggestions)
│   ├── generate_queries.py  (neuraltree_generate_queries — 6 strategies including lesson regression)
│   └── lesson.py            (neuraltree_lesson_match + neuraltree_lesson_add — incident memory)
├── scoring/
│   ├── score.py             (neuraltree_score — 5 metrics + partial Flow Score, precision_at_3=null)
│   ├── diagnose.py          (neuraltree_diagnose — 5 gap types, keyword matching)
│   └── predict.py           (neuraltree_predict + neuraltree_update_calibration — virtual backtest)
└── sandbox/
    └── sandbox.py           (4 tools: create, diff, apply, destroy — git worktree + copy fallback)
```

### Tests — 175 passing

```
tests/
├── conftest.py              (tmp_project fixture with CLAUDE.md, memory/, docs/, lessons/, server/)
├── unit/                    (11 test files — helpers, validators, parsers)
└── integration/             (2 test files — mcp.call_tool() end-to-end for all tools)
```

Run: `PYTHONPATH=src python3.11 -m pytest tests/ -v`

### Docs

```
docs/
├── specs/2026-04-04-neuraltree-skill-design.md   (THE spec — architecture, scoring, autoloop, data lifecycle)
├── FEATURE_INCIDENT_MEMORY.md                     (lesson feature design)
├── PHASE1_PLAN.md                                 (Phase 1 build plan — COMPLETED)
└── PHASE1_5_PLAN.md                               (Phase 1.5 build plan — COMPLETED)
```

---

## What Phase 2 Must Build

**Phase 2 = `src/skill/SKILL.md`** — the brain that orchestrates all 16 MCP tools.

### 5 Critical Integration Points

1. **`precision_at_3` is null** — `neuraltree_score()` returns it as `None`. The Skill OWNS this metric: call Viking search per query, run LLM-as-judge, fill in the value, compute final Flow Score as `flow_score_partial + (precision_at_3 * 0.25)`.

2. **`neuraltree_diagnose` needs `viking_results`** — to classify EMBEDDING_GAP (file exists, Viking missed it), the Skill must pass `viking_results=[{"query": q, "results": [f1, f2, f3]}]` from its Viking search step. Without it, all misses classify as SYNAPSE_GAP.

3. **Lesson integration in autoloop** — after KEEP/HOLD/DISCARD decisions, the Skill should call `neuraltree_lesson_add()` to record what was tried and why it worked/failed.

4. **`.neuraltree/state.json` is NOT managed by MCP** — the MCP only persists `calibration.json`. The Skill must own `state.json` (Flow Score history, last run timestamp, mode detection), `queries.json`, `history/`, and `.lock`.

5. **Two-phase scoring assembly:**
   ```
   MCP: neuraltree_score() → metrics (5 of 6, precision_at_3=null, flow_score_partial)
   Skill: Viking + LLM judge → precision_at_3 = X
   Skill: final flow_score = flow_score_partial + (X * 0.25)
   ```

### SKILL.md Build Sequence

1. Section 1: Activation — detect mode (bootstrap/health-check/spot-check/critical)
2. Section 2: Artery Principle — soul rules, 0-1-2 hop rule (teaching, no tool calls)
3. Section 3: Benchmark phase — generate_queries + Viking + LLM judge + score assembly
4. Section 4: Diagnose phase — diagnose with viking_results + lesson_match enrichment
5. Section 5: Karpathy AutoLoop — predict → backup → execute → score → KEEP/HOLD/DISCARD → lesson_add → update_calibration
6. Section 6: Execution Report — safe vs pending vs needs-review actions
7. Section 7: Enforce — state.json, Viking re-index, .tmp cleanup, graduation
8. Section 8: Subcommand routing (audit, fix, enforce, benchmark, auto)
9. Section 9: Degraded mode (Viking unavailable, MCP unavailable fallbacks)

---

## Known Spec Divergences (Intentional, Documented)

| What | Spec Says | Implementation Does | Why |
|------|-----------|-------------------|-----|
| `neuraltree_score` | Doesn't compute hop_efficiency | Computes it as reachability ratio | Useful data, Skill can use or ignore |
| `neuraltree_diagnose` input | Rich structured objects with hop_count, viking_hit | Simple {text, expected_topic} + optional viking_results | More autonomous, less Skill coupling |
| `neuraltree_sandbox_apply` | Action-based dict list (delete/move/archive/split) | Flat file copy list | Simpler, safer for Phase 1 |

## Known Technical Debt

| Item | Priority | Notes |
|------|----------|-------|
| `WEIGHTS` dict duplicated in score.py + predict.py | Low | Must keep in sync manually |
| `predict.py` `_load_calibration` has `except: pass` | Low | Accepted — returns defaults on corrupt file |
| `score.py` reads .md files 3 times | Medium | Cache in single pass for performance |
| `test_scan.py` re-implements scan logic | Low | Integration tests cover the real tool |
| `neuraltree_update_calibration` has zero dedicated tests | Medium | Works but untested edge cases |

---

## How to Verify Everything Works

```bash
cd /home/neil1988/neuraltree
PYTHONPATH=src python3.11 -m pytest tests/ -v          # 175 tests
PYTHONPATH=src python3.11 -c "
import asyncio
from neuraltree_mcp.server import mcp
tools = asyncio.run(mcp.list_tools())
print(f'{len(tools)} tools: {[t.name for t in tools]}')
"                                                       # 16 tools listed
```

## User Profile

Neil — senior dev, wants ultra-complex ultra-powerful builds, full auto. Prefers agents review everything multiple times. Uses review rounds (3-4 until clean). Trusts the process but verifies thoroughly. Working on multiple projects (LocaNext, newfin, neuraltree).
