# CLAUDE.md — NeuralTree

> Universal Neural Organization Skill for AI Coding Agents

## What Is This

`/neuraltree` is a skill + MCP server that transforms any project into a neural tree — a structured information system where any fact is reachable in 0-2 hops, every node is wired to related nodes, and semantic search catches what structure misses.

## Current Status

**COMPLETE.** 25 MCP tools (308+ tests) + SKILL.md + install.sh + README.

## Architecture

```
Skill (SKILL.md) = THE BRAIN — explore-first orchestration
MCP Server (neuraltree-mcp) = THE MUSCLE — 25 tools, 308+ tests
Viking MCP = THE MEMORY — semantic search
Agent Swarm = THE EYES — 2-10 parallel explorers
Claude = THE JUDGE — reasoning-based analysis (no hardcoded formulas)
```

## Pipeline (v2)

```
Phase 1: EXPLORE  — N agents read project deeply in parallel
Phase 2: MAP      — synthesize into dual-layer knowledge map
Phase 3: ANALYZE  — Claude reasons about what's wrong  
Phase 4: PLAN     — propose reorganization, user approves
Phase 5: EXECUTE  — apply in sandbox
Phase 6: VERIFY   — adaptive scoring confirms improvement
```

## MCP Server — 25 Tools

| Category | Tools |
|----------|-------|
| Filesystem | scan, trace, backup, restore |
| Intelligence | wire, generate_queries |
| Knowledge Map | neuraltree_knowledge_map (save/load/query) |
| Reorganize | plan_move, plan_split, find_dead, generate_index, shrink_and_wire, split_and_wire |
| Lessons | lesson_match, lesson_add |
| Scoring | score, diagnose, predict, update_calibration |
| Semantic | precision (Viking search + content retrieval), viking_index (batch indexing) |
| Sandbox | sandbox_create, sandbox_diff, sandbox_apply, sandbox_destroy |

## Project Structure

```
neuraltree/
├── CLAUDE.md                    This file
├── src/
│   ├── neuraltree_mcp/          Python MCP server (FastMCP)
│   │   ├── __init__.py          Version 0.1.0
│   │   ├── server.py            Entry point — registers all 25 tools
│   │   ├── validation.py        Path traversal prevention (all tools use this)
│   │   ├── text_utils.py        Shared: extract_keywords, jaccard, walk_project_files
│   │   ├── tools/               7 tool modules (scan, trace, backup, wire, generate_queries, lesson, reorganize)
│   │   ├── scoring/             3 modules (score, diagnose, predict+update_calibration)
│   │   └── sandbox/             1 module (4 sandbox tools)
│   └── skill/
│       ├── SKILL.md             The skill router (v2, explore-first)
│       └── sections/            7 phase files
│           ├── explore.md       Phase 1: parallel agent exploration
│           ├── map.md           Phase 2: knowledge map synthesis
│           ├── analyze.md       Phase 3: Claude-driven analysis
│           ├── plan.md          Phase 4: reorganization proposals
│           ├── execute.md       Phase 5: sandbox execution
│           ├── verify.md        Phase 6: adaptive scoring
│           └── report.md        Output: before/after comparison
├── tests/                       308 tests passing
│   ├── conftest.py              Shared fixtures (tmp_project with memory/, docs/, lessons/)
│   ├── unit/                    11 test files
│   └── integration/             5 test files (e2e pipeline, sandbox, degraded, plus originals)
├── docs/
│   └── specs/                   Design spec v5 (reviewed by 25 agents)
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

1. `neuraltree_score()` returns `precision_at_3: null` — Skill fills it via Viking search + Claude judging
2. `neuraltree_diagnose()` receives `viking_results` param for EMBEDDING_GAP classification
3. `.neuraltree/state.json` is Skill-owned, not MCP-managed
4. Lesson recording happens after autoloop KEEP/HOLD/DISCARD decisions
5. Flow Score assembly: `flow_score_partial + (precision_at_3 * 0.25)`

## Dependencies

- Python 3.11+
- fastmcp>=2.0.0
- Viking MCP (OpenViking) — semantic search (required for full scoring)
- Sequential Thinking MCP — step-by-step reasoning for judging and autoloop

## Commands

```bash
# Run tests (308 passing)
PYTHONPATH=src python3.11 -m pytest tests/ -v

# Verify all 25 tools load
PYTHONPATH=src python3.11 -c "
import asyncio
from neuraltree_mcp.server import mcp
tools = asyncio.run(mcp.list_tools())
print(f'{len(tools)} tools: {[t.name for t in tools]}')
"

# Run MCP server
PYTHONPATH=src python3.11 -m neuraltree_mcp.server
```
