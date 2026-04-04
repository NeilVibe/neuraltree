# CLAUDE.md — NeuralTree

> Universal Neural Organization Skill for AI Coding Agents

## What Is This

`/neuraltree` is a skill + MCP server that transforms any project into a neural tree — a structured information system where any fact is reachable in 0-2 hops, every node is wired to related nodes, and semantic search catches what structure misses.

## Architecture

```
Skill (SKILL.md) = THE BRAIN — orchestrates everything
MCP Server (neuraltree-mcp) = THE MUSCLE — 13 tools for filesystem ops
Viking MCP = THE MEMORY — semantic search (required dependency)
```

## Project Structure

```
neuraltree/
├── CLAUDE.md                    This file
├── src/
│   ├── neuraltree_mcp/          Python MCP server (FastMCP)
│   │   ├── __init__.py
│   │   ├── server.py            Main MCP server entry point
│   │   ├── tools/               Tool implementations (one file per tool)
│   │   ├── scoring/             Scoring engine (metrics, flow score)
│   │   └── sandbox/             Sandbox virtualization
│   └── skill/
│       └── SKILL.md             The skill instruction file
├── tests/
│   ├── unit/                    Unit tests per tool
│   ├── integration/             MCP server integration tests
│   └── mock/                    Mock tests with simulated projects
├── docs/
│   └── specs/                   Design specs
├── logs/                        Test run logs
├── requirements.txt             Python dependencies
└── README.md                    Public docs
```

## Development Protocol

1. **Plan before code** — write what you'll build, review it, then build
2. **Test after every tool** — unit test each MCP tool independently
3. **Mock test with simulated projects** — don't just test on LocaNext
4. **Review after building** — spawn review agents after each phase
5. **Log everything** — test results, review findings, decisions

## Key Principles

- **Artery Principle:** It's about FLOW, not storage. Every decision serves information retrieval.
- **0-1-2 Hop Rule:** Any information reachable in max 2 tool calls.
- **Trace Before Prune:** Investigate every connection before recommending deletion.
- **User Approves Destructive Actions:** Autoloop thinks, user decides on deletes/moves.
- **Sandbox First:** Autoloop runs in isolated git worktree, never touches real project.

## Spec

Full design spec: `docs/specs/2026-04-04-neuraltree-skill-design.md`
- 5 review rounds, 25 agents, 9/10 SHIP verdict

## Dependencies

- Python 3.11+
- fastmcp
- Viking MCP (OpenViking) — required for semantic search
- Model2Vec — powers Viking embeddings

## Commands

```bash
# Run MCP server
python -m neuraltree_mcp.server

# Run tests
pytest tests/

# Run specific tool test
pytest tests/unit/test_scan.py -v
```
