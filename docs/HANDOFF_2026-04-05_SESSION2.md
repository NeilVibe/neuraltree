# NeuralTree Handoff — Session 2 (2026-04-05)

> **Status:** 20 tools, 256 tests, 4 review rounds (17 agents, 40 issues fixed). Ready for SKILL.md wiring + autoloop iteration 3.
> **Branch:** main
> **Last test run:** 256 passed, 0 failed (12.5s)

---

## What Exists Now

### MCP Server — 20 tools, fully tested

```
src/neuraltree_mcp/
├── __init__.py              (version 0.1.0)
├── server.py                (entry point — registers all 20 tools)
├── validation.py            (validate_project_root + validate_within_root)
├── text_utils.py            (shared: extract_keywords, jaccard, walk_project_files)
├── tools/
│   ├── scan.py              (neuraltree_scan — filesystem inventory, 10k file cap)
│   ├── trace.py             (neuraltree_trace — reference tracing via grep)
│   ├── backup.py            (neuraltree_backup + neuraltree_restore — 100MB cap)
│   ├── wire.py              (neuraltree_wire — Jaccard similarity, ## Related + ## Docs)
│   ├── generate_queries.py  (neuraltree_generate_queries — 8 strategies, heading/bold/table/git)
│   ├── lesson.py            (neuraltree_lesson_match + neuraltree_lesson_add)
│   └── reorganize.py        (NEW: 4 structural tools — see below)
├── scoring/
│   ├── score.py             (neuraltree_score — 5 metrics + partial Flow Score)
│   ├── diagnose.py          (neuraltree_diagnose — 5 gap types, segment-based Viking matching)
│   └── predict.py           (neuraltree_predict + neuraltree_update_calibration — imports WEIGHTS from score.py)
└── sandbox/
    └── sandbox.py           (4 sandbox tools: create, diff, apply, destroy)
```

### 4 NEW Reorganize Tools (built this session)

| Tool | What It Does | Key Design Choice |
|------|-------------|-------------------|
| `neuraltree_plan_move` | Plans file move + computes ALL reference rewrites | Word-boundary regex (prevents auth.md→oauth.md corruption) |
| `neuraltree_plan_split` | Proposes splits by ## heading, code-block aware | Includes preamble, skips fenced code blocks + frontmatter |
| `neuraltree_find_dead` | Finds orphan .md files nothing references | Strips #anchors and ?queries from refs, size=-1 for unreadable |
| `neuraltree_generate_index` | Auto-generates _INDEX.md for any directory | Extracts frontmatter name/description, reports subdirectories |

### Tests — 256 passing

```
tests/
├── conftest.py              (tmp_project, tmp_project_large, newfin_project fixtures)
├── unit/                    (6 test files)
│   ├── test_generate_queries.py   (37 tests — parsers, security, e2e tool call)
│   ├── test_reorganize.py         (30 tests — all 4 new tools + helpers)
│   ├── test_diagnose.py           (4 tests — gap classification basics)
│   ├── test_score.py              (15 tests — metrics, weights)
│   ├── test_text_utils.py         (12 tests — keywords, jaccard, walk)
│   └── ... (trace, wire, etc.)
└── integration/             (5 test files)
    ├── test_tool_calls.py         (all 20 tools via mcp.call_tool)
    ├── test_e2e_pipeline.py       (benchmark, predict, calibration)
    ├── test_sandbox_isolation.py  (create, diff, apply, destroy)
    ├── test_degraded_mode.py      (Viking unavailable)
    └── test_server.py             (tool count = 20, tool registration)
```

### SKILL.md — 2,350+ lines, 9 sections (NEEDS WIRING)

The SKILL.md is the brain. It was built before the 4 new reorganize tools existed. **It does NOT reference them yet.** This is the #1 priority for next session.

---

## What Was Proven (AutoLoop Proof Run)

### Iteration 1 (baseline → index files → re-score)
- **Target:** `/home/neil1988/newfin` (5,489 files, 436 markdown)
- **Baseline:** Flow Score 0.168 (CRITICAL)
- **Fix:** Indexed 27 files into Viking (14,647 embeddings)
- **After:** Flow Score 0.173 (+0.005) — **KEEP**
- **Lesson:** Indexing alone caps at ~0.25. Structural fixes needed.

### Iteration 2 (improved code → re-benchmark)
- **Flow Score:** 0.166 (slight noise regression)
- **BREAKTHROUGH:** Diagnosis went from 100% EMBEDDING_GAP (wrong) → 94% FOCUS_GAP (correct)
- **Root cause:** 46/49 failures are files >500 lines burying answers. Not missing indexes.
- **Next fix:** Split large files into focused neurons → improves synapse_coverage + hop_efficiency

### Key Performance Numbers
| Operation | Time |
|-----------|------|
| Full scan (5,489 files) | 0.5s |
| Query generation (50 queries) | 0.3s |
| Benchmark (50 queries × 3 × Viking + LLM) | ~50-70s |
| Full autoloop iteration | ~250s |
| LLM judge (Qwen3.5:4b, think=false) | 3.3s/call |

---

## What Needs To Be Done Next (Priority Order)

### 1. Wire 4 new tools into SKILL.md (CRITICAL)

The 4 reorganize tools are invisible to the SKILL. Without this, the autoloop can't do structural fixes.

| Where in SKILL.md | What to add |
|-------------------|-------------|
| Section 5 (Diagnose) | Use `neuraltree_find_dead()` to enrich dead neuron detection |
| Section 6 (AutoLoop) Step 1b | Call `neuraltree_plan_split()` for FOCUS_GAP proposals |
| Section 6 execute_pending_action | Call `neuraltree_plan_move()` BEFORE any file move/archive |
| Section 7 (Enforce) | Call `neuraltree_generate_index()` after splits create new files |
| Section 8 (Report) | Add the execution report format (SAFE/PENDING/APPROVE) |
| Frontmatter line 8 | Change `16 tools` → `20 tools` |
| Section 5 gap table line ~908 | Change FOCUS_GAP `>80 lines` → `>500 lines` |

### 2. Add execution report format to SKILL.md Section 8

The report the user sees after autoloop:
```
╔═══════════════════════════════════════╗
║  NeuralTree Report — {project}        ║
║  Flow Score: {before} → {after}       ║
╠═══════════════════════════════════════╣
║  SAFE (auto-applied):                 ║
║    ✓ Wired N files with ## Related    ║
║    ✓ Re-indexed N files in Viking     ║
║  PENDING (needs approval):            ║
║    1. Split X.md → N files            ║
║    2. Archive N dead files            ║
║  APPROVE? [yes / review-each / reject]║
╚═══════════════════════════════════════╝
```

### 3. Update CLAUDE.md + README.md tool counts (16 → 20)

### 4. Run autoloop iteration 3 with structural fixes
- Use `neuraltree_plan_split` on the 46 FOCUS_GAP files
- Execute splits in sandbox
- Re-score and show before/after delta
- This should break Flow Score past 0.25

### 5. Known remaining issues (from 7-agent review, MEDIUM severity)
- `_load_calibration` silently returns defaults on corrupt JSON (predict.py)
- Sandbox degrades to copy silently when git worktree fails (no stderr logging)
- `sandbox_destroy` reports "destroyed" even when cleanup failed
- `neuraltree_score` reads .md files 3x (should cache in single pass)
- `generate_queries` lesson parsing duplicates logic from lesson.py
- `find_dead` vs `score.py` orphan detection use different reference scanning
- SKILL.md ACTION_MAP "index" predicts wrong metric (hop_efficiency instead of precision_at_3)

---

## Infrastructure

| Component | Status | Notes |
|-----------|--------|-------|
| Viking MCP | Running :1933 | 23,236 embeddings from newfin |
| Model2Vec | Running :8100 | Model loaded |
| Qwen3.5:4b | Ollama | **MUST use think=false** (17x speedup) |
| Qwen3-VL:8b | Ollama | For vision review only |
| Python | 3.11 | PYTHONPATH=src |
| Tests | 256 passing | `PYTHONPATH=src python3.11 -m pytest tests/ -v` |

## Review History

| Round | Agents | Issues | Result |
|-------|--------|--------|--------|
| Round 1 | code-reviewer, silent-failure-hunter, SKILL reviewer | 8 | All fixed |
| Round 2 | code-reviewer, test-analyzer | 4 + test gaps | All fixed |
| Round 3 | 5 agents (code, security, silent, test, SKILL) | 10 | All fixed |
| Round 4 | 7 agents (full codebase) | 18 critical+high | All fixed |
| **Total** | **17 agents** | **40 issues** | **40 fixed** |

---

## How To Verify Everything Works

```bash
cd /home/neil1988/neuraltree

# Run all 256 tests
PYTHONPATH=src python3.11 -m pytest tests/ -v

# Verify 20 tools load
PYTHONPATH=src python3.11 -c "
import asyncio
from neuraltree_mcp.server import mcp
tools = asyncio.run(mcp.list_tools())
print(f'{len(tools)} tools: {[t.name for t in tools]}')
"

# Quick test new reorganize tools against newfin
PYTHONPATH=src python3.11 -c "
import asyncio, json
from neuraltree_mcp.server import mcp
async def test():
    r = json.loads((await mcp.call_tool('neuraltree_find_dead', {'project_root': '/home/neil1988/newfin'})).content[0].text)
    print(f'Dead files: {r[\"total_dead\"]}/{r[\"total_knowledge\"]} ({r[\"dead_ratio\"]:.1%})')
    r = json.loads((await mcp.call_tool('neuraltree_plan_split', {'target': 'CLAUDE.md', 'project_root': '/home/neil1988/newfin'})).content[0].text)
    print(f'CLAUDE.md: {r[\"total_lines\"]} lines, {r[\"section_count\"]} sections → {len(r[\"splits\"])} split files')
asyncio.run(test())
"
```

## Key Files Changed This Session

| File | Changes |
|------|---------|
| `src/neuraltree_mcp/server.py` | 20 tools (was 16), added reorganize import |
| `src/neuraltree_mcp/tools/reorganize.py` | **NEW** — 4 tools, word-boundary matching, code-block aware |
| `src/neuraltree_mcp/tools/generate_queries.py` | Path fix, heading cleanup, bold terms, per-strategy cap, sources recount |
| `src/neuraltree_mcp/tools/wire.py` | Added validate_project_root |
| `src/neuraltree_mcp/scoring/diagnose.py` | Segment URI matching, scored best_match, FRESHNESS date math, case-insensitive lookup |
| `src/neuraltree_mcp/scoring/predict.py` | Import WEIGHTS from score.py (no more duplication) |
| `src/skill/SKILL.md` | think=false docs, viking_read in benchmark, re-score path fix, temperature |
| `install.sh` | Tool count 16→20 |
| `tests/unit/test_generate_queries.py` | 37 tests (was 11) |
| `tests/unit/test_reorganize.py` | **NEW** — 30 tests |
| `tests/unit/test_diagnose.py` | Fixed wrong priority order |
| `tests/integration/test_server.py` | Tool count 20 |
| `docs/AUTOLOOP_PROOF_RUN.md` | **NEW** — full proof run documentation |

## User Profile

Neil — senior dev, wants ultra-complex ultra-powerful builds, full auto. Runs 5-7 agent reviews, multiple rounds until clean. Trusts the process but demands proof (before/after metrics). Current focus: making NeuralTree a production-ready project organization autopilot.
