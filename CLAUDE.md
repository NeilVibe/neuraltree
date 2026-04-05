# CLAUDE.md — NeuralTree

> Universal Neural Organization Skill for AI Coding Agents

## What Is This

`/neuraltree` is a skill + MCP server that transforms any project into a neural tree — a structured information system where any fact is reachable in 0-2 hops, every node is wired to related nodes, and semantic search catches what structure misses.

## Current Status

**Phases 1-3 COMPLETE.** MCP server + SKILL.md built, tested, reviewed.
**Phase 5 COMPLETE.** Ready to install and use.
**What's built:** 16 MCP tools (200 tests) + 2,350-line SKILL.md (5 review rounds, 28 agents, 63 issues fixed) + install.sh + README.
**Phase 6 DEFERRED:** Platform adaptation (Gemini CLI, Codex) — not needed to ship.

## Architecture

```
Skill (SKILL.md) = THE BRAIN — 2,350 lines, 9 sections (BUILT, 5 REVIEW ROUNDS)
MCP Server (neuraltree-mcp) = THE MUSCLE — 16 tools (BUILT, 200 TESTS)
Viking MCP = THE MEMORY — semantic search (required dependency)
```

## MCP Server — 16 Tools

| Category | Tools |
|----------|-------|
| Filesystem | scan, trace, backup, restore |
| Intelligence | wire, generate_queries |
| Lessons | lesson_match, lesson_add |
| Scoring | score, diagnose, predict, update_calibration |
| Sandbox | sandbox_create, sandbox_diff, sandbox_apply, sandbox_destroy |

## Project Structure

```
neuraltree/
├── CLAUDE.md                    This file
├── src/
│   ├── neuraltree_mcp/          Python MCP server (FastMCP)
│   │   ├── __init__.py          Version 0.1.0
│   │   ├── server.py            Entry point — registers all 16 tools
│   │   ├── validation.py        Path traversal prevention (all tools use this)
│   │   ├── text_utils.py        Shared: extract_keywords, jaccard, walk_project_files
│   │   ├── tools/               6 tool modules (scan, trace, backup, wire, generate_queries, lesson)
│   │   ├── scoring/             3 modules (score, diagnose, predict+update_calibration)
│   │   └── sandbox/             1 module (4 sandbox tools)
│   └── skill/
│       └── SKILL.md             The skill instruction file (2,350 lines, 9 sections — BUILT)
├── tests/                       200 tests passing
│   ├── conftest.py              Shared fixtures (tmp_project with memory/, docs/, lessons/)
│   ├── unit/                    11 test files
│   └── integration/             5 test files (e2e pipeline, sandbox, degraded, plus originals)
├── docs/
│   ├── specs/                   Design spec v5 (reviewed by 25 agents)
│   ├── FEATURE_INCIDENT_MEMORY.md  Lesson feature design
│   ├── PHASE1_PLAN.md           Phase 1 plan (COMPLETED)
│   ├── PHASE1_5_PLAN.md         Phase 1.5 plan (COMPLETED)
│   └── HANDOFF.md               Full Phase 2 handoff with integration points
├── requirements.txt             Python dependencies
└── README.md                    Public docs
```

## Development Protocol

1. **Plan before code** — write what you'll build, review with agents, then build
2. **Test after every tool** — unit test + integration test via mcp.call_tool()
3. **Review after building** — spawn 5-6 review agents (code quality, security, silent failures, tests, spec compliance, architecture)
4. **Multiple review rounds** — 3-4 rounds until all agents say SHIP/CLEAN
5. **Security first** — all tools validate project_root, all file writes use validate_within_root

## Key Principles

- **Artery Principle:** It's about FLOW, not storage. Every decision serves information retrieval.
- **0-1-2 Hop Rule:** Any information reachable in max 2 tool calls.
- **Trace Before Prune:** Investigate every connection before recommending deletion.
- **User Approves Destructive Actions:** Autoloop thinks, user decides on deletes/moves.
- **Sandbox First:** Autoloop runs in isolated git worktree, never touches real project.

## Integration Points (all wired and verified)

1. `neuraltree_score()` returns `precision_at_3: null` — Skill fills it via Viking + LLM judge
2. `neuraltree_diagnose()` receives `viking_results` param for EMBEDDING_GAP classification
3. `.neuraltree/state.json` is Skill-owned, not MCP-managed
4. Lesson recording happens after autoloop KEEP/HOLD/DISCARD decisions
5. Flow Score assembly: `flow_score_partial + (precision_at_3 * 0.25)`

## Specs & Plans

- Full design spec: `docs/specs/2026-04-04-neuraltree-skill-design.md`
- Lesson feature: `docs/FEATURE_INCIDENT_MEMORY.md`
- Phase 2 handoff: `docs/HANDOFF.md` (historical — Phase 2 complete)
- Phase 2 plan: `docs/superpowers/plans/2026-04-05-skill-md-phase2.md` (historical — executed)

## Dependencies

- Python 3.11+
- fastmcp>=2.0.0
- Viking MCP (OpenViking) — required for semantic search
- Model2Vec — powers Viking embeddings

## Commands

```bash
# Run tests (200 passing)
PYTHONPATH=src python3.11 -m pytest tests/ -v

# Verify all 16 tools load
PYTHONPATH=src python3.11 -c "
import asyncio
from neuraltree_mcp.server import mcp
tools = asyncio.run(mcp.list_tools())
print(f'{len(tools)} tools: {[t.name for t in tools]}')
"

# Run MCP server
PYTHONPATH=src python3.11 -m neuraltree_mcp.server
```
