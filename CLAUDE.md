# CLAUDE.md — NeuralTree

> Universal Neural Organization Skill for AI Coding Agents

## What Is This

`/neuraltree` is a skill + MCP server that transforms any project into a neural tree — a structured information system where any fact is reachable in 0-2 hops, every node is wired to related nodes, and semantic search catches what structure misses.

## Current Status

**COMPLETE.** 24 MCP tools (426 tests) + SKILL.md + install.sh + README.

## Architecture

```
Skill ([SKILL.md](src/skill/SKILL.md)) = THE BRAIN — explore-first orchestration
MCP Server (neuraltree-mcp) = THE MUSCLE — 24 tools, 426 tests
Viking MCP = THE MEMORY — semantic search
Agent Swarm = THE EYES — 2-10 parallel explorers
Claude = THE JUDGE — reasoning-based analysis (no hardcoded formulas)
```

## Pipeline (v2)

```
Phase 1: UNDERSTAND — N agents read project deeply in parallel, synthesize knowledge map
Phase 2: ANALYZE   — Check lessons, Claude reasons about what's wrong
Phase 3: PLAN      — propose reorganization, user approves
Phase 4: EXECUTE   — apply in sandbox
Phase 5: VERIFY    — wiki lint + universal organization scoring confirms improvement
```

## MCP Server — 24 Tools

| Category | Tools |
|----------|-------|
| Filesystem | scan, trace, backup, restore |
| Intelligence | wire, generate_queries |
| Knowledge Map | neuraltree_knowledge_map (save/load/query) |
| Reorganize | plan_move, plan_split, find_dead, generate_index, shrink_and_wire, split_and_wire |
| Lessons | lesson_match, lesson_add |
| Scoring | score, diagnose |
| Semantic | precision (Viking search + content retrieval), viking_index (batch indexing) |
| Wiki | wiki_lint (broken links, orphans, freshness, cross-ref density) |
| Sandbox | sandbox_create, sandbox_diff, sandbox_apply, sandbox_destroy |

## Project Structure

```
neuraltree/
├── CLAUDE.md                    This file
├── src/
│   ├── neuraltree_mcp/          Python MCP server (FastMCP)
│   │   ├── __init__.py          Version 0.1.0
│   │   ├── server.py            Entry point — registers all 24 tools
│   │   ├── validation.py        Path traversal prevention (all tools use this)
│   │   ├── text_utils.py        Shared: extract_keywords, jaccard, walk_project_files
│   │   ├── tools/               8 tool modules (scan, trace, backup, wire, generate_queries, lesson, reorganize, wiki_lint)
│   │   ├── scoring/             2 modules (score, diagnose)
│   │   └── sandbox/             1 module (4 sandbox tools)
│   └── skill/
│       ├── SKILL.md             The skill router (v2, explore-first)
│       └── sections/            6 phase files
│           ├── understand.md    Phase 1: explore + map
│           ├── analyze.md       Phase 2: Claude-driven analysis
│           ├── plan.md          Phase 3: reorganization proposals
│           ├── execute.md       Phase 4: sandbox execution
│           ├── verify.md        Phase 5: adaptive scoring + wiki lint
│           └── report.md        Output: before/after comparison
├── tests/                       426 tests passing
│   ├── conftest.py              Shared fixtures (tmp_project with memory/, docs/, lessons/)
│   ├── unit/                    12 test files
│   └── integration/             5 test files (e2e pipeline, sandbox, degraded, plus originals)
├── lessons/                     Design lessons (autoloop, v2 decisions)
├── docs/
│   ├── concepts/                11 concept pages (Karpathy LLM-Wiki style, one concept = one page)
│   └── archive/                 Session handoff docs (11 files)
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

See [concept index](docs/concepts/_INDEX.md) for deep-dive pages on each principle.

- **[Artery Principle](docs/concepts/artery-principle.md):** It's about FLOW, not storage. Every decision serves information retrieval.
- **[0-1-2 Hop Rule](docs/concepts/hop-rule.md):** Any information reachable in max 2 tool calls.
- **[Trace Before Prune](docs/concepts/trace-before-prune.md):** Investigate every connection before recommending deletion.
- **[User Approves Destructive Actions](docs/concepts/user-approves-destructive.md):** Autoloop thinks, user decides on deletes/moves.
- **[Sandbox First](docs/concepts/sandbox-first.md):** Autoloop runs in isolated git worktree, never touches real project.
- **[Algorithm → Tool, Judgment → Claude](docs/concepts/algorithm-tool-judgment-claude.md):** Deterministic logic lives in MCP tools. Reasoning lives in the Skill. See [lessons/v2-design-decisions.md](lessons/v2-design-decisions.md).

## Integration Points (all wired and verified)

1. `neuraltree_score()` returns `discoverability: null` — Skill fills it via Viking search + Claude judging
2. `neuraltree_score()` requires `.neuraltree/knowledge_map.json` — run understand phase first
3. `neuraltree_diagnose()` receives `viking_results` param for EMBEDDING_GAP classification
4. `.neuraltree/state.json` is Skill-owned, not MCP-managed
5. lesson_match is called in Analyze phase to check past experience; lesson_add records failures in Verify phase
6. Flow Score assembly: `flow_score_partial + (discoverability * 0.10)`

## Dependencies

- Python 3.11+
- fastmcp>=2.0.0
- Viking MCP (OpenViking) — semantic search (required for full scoring)
- Sequential Thinking MCP — step-by-step reasoning for judging and autoloop

## Commands

```bash
# Run tests (426 passing)
PYTHONPATH=src python3.11 -m pytest tests/ -v

# Verify all 24 tools load
PYTHONPATH=src python3.11 -c "
import asyncio
from neuraltree_mcp.server import mcp
tools = asyncio.run(mcp.list_tools())
print(f'{len(tools)} tools: {[t.name for t in tools]}')
"

# Run MCP server
PYTHONPATH=src python3.11 -m neuraltree_mcp.server
```
