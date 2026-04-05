# NeuralTree Handoff — Session 3 (2026-04-05)

> **Status:** 22 tools, 270 tests, Claude-driven autoloop, proven on small + large projects. Ready for SKILL.md trim + ship.
> **Branch:** main
> **Last test run:** 270 passed, 0 failed

---

## What Was Built This Session

### 8 commits, 2,659 lines added, 654 removed

| Commit | What |
|--------|------|
| `7d14588` | Wired 4 reorganize tools into SKILL.md + 5-agent review hardening |
| `97dfa71` | find_dead perf fix (180s→0.1s) + 6-agent review hardening |
| `fe5edcb` | Strategy-level autoloop + VIKING_INDEX + multi-round cycling |
| `2b4d779` | 5-agent review: delete old loop, fix predictions, add strategy tests |
| `6f70255` | Claude-driven autoloop — no hardcoded strategies |
| `cd60f63` | Final review: delete stale loop, fix all Section 7/8 references |
| `428ce50` | neuraltree_shrink_and_wire — atomic extract+wire+index |
| `6798d06` | neuraltree_split_and_wire — atomic split+wire+index |

### Key Design Changes

1. **AutoLoop redesigned 3 times:**
   - v1: Per-file loop (wire 1 file → measure → KEEP/DISCARD) — too granular, noise not signal
   - v2: Hardcoded strategy list (SPLIT_LARGE, WIRE_ORPHANS, etc.) — too scripty, Claude not thinking
   - v3 (current): Claude-driven — Claude reads files, proposes action, tools measure, KEEP/DISCARD

2. **Two atomic reorganize tools added:**
   - `neuraltree_shrink_and_wire`: extract named sections, keep original smaller, wire everything
   - `neuraltree_split_and_wire`: split by ## headings, replace with index, wire all siblings

3. **Performance:** find_dead went from timeout (180s+) to 0.1s by restricting reference scan to .md+config files only

### MCP Server — 22 tools

```
src/neuraltree_mcp/
├── server.py                (22 tools via register() pattern)
├── validation.py            (validate_project_root + validate_within_root)
├── text_utils.py            (shared: extract_keywords, jaccard, is_referenced, walk_project_files)
├── tools/
│   ├── scan.py              (neuraltree_scan)
│   ├── trace.py             (neuraltree_trace)
│   ├── backup.py            (neuraltree_backup + neuraltree_restore)
│   ├── wire.py              (neuraltree_wire)
│   ├── generate_queries.py  (neuraltree_generate_queries)
│   ├── lesson.py            (neuraltree_lesson_match + neuraltree_lesson_add)
│   └── reorganize.py        (plan_move, plan_split, find_dead, generate_index, shrink_and_wire, split_and_wire)
├── scoring/
│   ├── score.py             (neuraltree_score)
│   ├── diagnose.py          (neuraltree_diagnose)
│   └── predict.py           (neuraltree_predict + neuraltree_update_calibration)
└── sandbox/
    └── sandbox.py           (sandbox_create, sandbox_diff, sandbox_apply, sandbox_destroy)
```

### SKILL.md — 2,262 lines, 9 sections

| Section | Lines | What |
|---------|-------|------|
| 1. Activation | 50-258 | Verify tools, detect mode, acquire lock |
| 2. Artery Principle | 258-482 | Design philosophy (reference material) |
| 3. Progress Protocol | 482-557 | File format standards (reference material) |
| 4. Benchmark | 557-834 | Scan, generate queries, Viking search, LLM judge, score |
| 5. Diagnose | 834-1080 | Classify failures into 5 gap types, build priority queue |
| 6. AutoLoop | 1080-1379 | Claude-driven: analyze → propose → execute → measure → KEEP/DISCARD |
| 7. Enforce | 1379-1735 | Graduate learnings, re-index Viking, save state, install rules |
| 8. Report | 1735-2155 | SAFE/PENDING/HELD report, user interaction for pending actions |
| 9. Degraded Mode | 2155-2262 | Edge cases, Viking unavailable fallback |

---

## Proof Runs

### neuraltree on itself (13 .md files, 1 second)
```
Flow Score: 0.184 → 0.426 (+0.242, +131%)
Iteration 1: Wire all docs               ✓ KEEP +0.144
Iteration 2: Shrink CLAUDE.md            ✓ KEEP +0.022
Iteration 3: Add docs/_INDEX.md          ✓ KEEP +0.076
```

### newfin (5,489 files, 95 seconds)
```
Flow Score: 0.130 → 0.232 (+0.102, +78%)
Round 1: SPLIT +0.063, WIRE +0.015, INDEX -0.012 (DISCARD), RE_WIRE +0.021
Round 2: SPLIT marginal, WIRE done, RE_WIRE +0.003 → CONVERGED
```

### Autoresearch pattern test (per-file granularity)
```
Flow Score: 0.130 → 0.188 (+0.058)
4 iterations: SPLIT KEEP, Wire DISCARD, Wire DISCARD, Wire DISCARD → CONVERGED
Lesson: per-file wiring is noise. Strategy-level batching is signal.
```

---

## What Needs To Be Done Next

### 1. SKILL.md Trim Pass (RECOMMENDED before ship)

2,262 lines is large. Sections 2-3 (400 lines of philosophy/format specs) could be compressed to ~100 lines. Pseudocode in Sections 7-8 could be tightened. Target: ~1,500 lines without losing functionality. This makes it easier for Claude to follow.

### 2. Test the Skill as a Real Skill

We tested by running Python scripts that call MCP tools directly. Never tested Claude actually reading SKILL.md and following the instructions in a real session with neuraltree-mcp configured as an MCP server. This is the #1 validation gap.

### 3. Viking Integration

VIKING_INDEX strategy is wired in SKILL.md and predict.py but was never tested with Viking because Viking uses MCP protocol (not HTTP). When run as a real skill session with Viking MCP connected, the `viking_add_resource` and `viking_search` calls should work natively. This would unlock precision_at_3 (+0.25 weight = potential score boost to 0.45+).

### 4. Known Issues (MEDIUM, not blocking)

- Prediction model accuracy: 13.7% after 10 runs — needs more runs to calibrate
- predict.py strategy deltas are still proportional-headroom guesses, not project-aware
- `apply_suggested_content` referenced in SKILL.md is not an MCP tool — Claude must do it manually (read file, append wire content, write file)
- Score ceiling without Viking is ~0.23 for large projects (structural metrics only)

### 5. Ship

- install.sh exists and works
- README.md is comprehensive
- 270 tests all pass
- 22 tools all load
- MIT license

---

## How To Verify

```bash
cd /home/neil1988/neuraltree

# All 270 tests
PYTHONPATH=src python3.11 -m pytest tests/ -v

# All 22 tools load
PYTHONPATH=src python3.11 -c "
import asyncio
from neuraltree_mcp.server import mcp
tools = asyncio.run(mcp.list_tools())
print(f'{len(tools)} tools: {[t.name for t in tools]}')
"

# Quick proof run on any project
PYTHONPATH=src python3.11 -c "
import asyncio, json
from neuraltree_mcp.server import mcp
async def run():
    score = json.loads((await mcp.call_tool('neuraltree_score', {'project_root': '.'})).content[0].text)
    print(f'Flow Score: {score[\"flow_score_partial\"]}')
    for k,v in score['metrics'].items(): print(f'  {k}: {v}')
asyncio.run(run())
"
```

## Infrastructure

| Component | Status | Notes |
|-----------|--------|-------|
| Python | 3.11 | PYTHONPATH=src |
| Viking MCP | :1933 | Optional (DEGRADED_MODE if unavailable) |
| Model2Vec | :8100 | Powers Viking embeddings |
| Tests | 270 passing | `PYTHONPATH=src python3.11 -m pytest tests/ -v` |

## Session Stats

- 8 commits, 21 files changed
- 4 review rounds (11+ agents total)
- 3 autoloop redesigns (per-file → strategy → Claude-driven)
- 2 new atomic tools (shrink_and_wire, split_and_wire)
- 1 critical perf fix (find_dead 180s → 0.1s)
