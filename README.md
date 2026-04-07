# NeuralTree

**Universal neural organization for AI coding agents.**

NeuralTree transforms any project into a structured information system where any fact is reachable in 0-2 hops, every node is wired to related nodes, and semantic search catches what structure misses. It measures information flow with a single composite metric (Flow Score), diagnoses retrieval failures, and auto-repairs them in a sandboxed loop — so your AI agent can always *find* what it needs.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    /neuraltree                           │
│                THE BRAIN (Skill)                         │
│   Orchestrator — explores, maps, analyzes, reorganizes.  │
│   You invoke it, it drives.                              │
├──────────────┬──────────────┬──────────────┬────────────┤
│ neuraltree   │ Viking MCP   │ Agent Swarm  │ Claude     │
│ THE MUSCLE   │ THE MEMORY   │ THE EYES     │ THE JUDGE  │
│ 24 tools     │ Semantic     │ 2-10 parallel│ Reasoning  │
│ scan, score, │ search all   │ explorers    │ analysis   │
│ wire, map,   │ indexed      │ read project │ (no hard-  │
│ sandbox...   │ content      │ deeply       │ coded math)│
└──────────────┴──────────────┴──────────────┴────────────┘
```

**Brain** orchestrates everything. **Muscle** does computation (filesystem scans, scoring, wiring, knowledge maps). **Memory** provides semantic search. **Eyes** are explorer agents that read the project deeply in parallel. **Judge** reasons about what's wrong — no hardcoded formulas.

---

## Quick Start

### One-command install

```bash
git clone https://github.com/NeilVibe/neuraltree.git
cd neuraltree
./install.sh
```

The install script will:
1. Verify Python 3.11+ is available
2. Install Python dependencies
3. Copy the skill to `~/.claude/skills/neuraltree/`
4. Register the MCP server in `~/.claude.json`

### First run

```
/neuraltree
```

That's it. NeuralTree detects it's a first run (full mode), launches parallel explorer agents to understand your project deeply, builds a knowledge map, reasons about what's wrong, proposes fixes, executes them in a sandbox, and produces a before/after report.

---

## Prerequisites

| Dependency | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | MCP server runtime |
| [FastMCP](https://github.com/jlowin/fastmcp) | 2.0.0+ | MCP server framework |
| [Viking MCP](https://github.com/openviking) | any | Semantic search — the memory layer. Indexes all project docs for embedding-powered retrieval. |
| Claude Code | any | AI coding agent that runs the skill — also serves as the judge for Precision@3 via sequential thinking |
| Sequential Thinking MCP | any | Step-by-step reasoning for relevance judging and autoloop decisions |

---

## MCP Tools (24)

NeuralTree's MCP server provides 24 tools across 8 categories:

| Category | Tool | Description |
|----------|------|-------------|
| **Filesystem** | `neuraltree_scan` | Fast project inventory — file counts, types, structure |
| | `neuraltree_trace` | Reference tracing — find every connection to/from a file |
| | `neuraltree_backup` | Snapshot current state for safe rollback |
| | `neuraltree_restore` | Restore from backup if something goes wrong |
| **Intelligence** | `neuraltree_wire` | Auto-generate `## Related` and `## Docs` cross-references |
| | `neuraltree_generate_queries` | Create test queries from project context for benchmarking |
| **Reorganize** | `neuraltree_plan_move` | Plan file move with all reference rewrites (word-boundary safe) |
| | `neuraltree_plan_split` | Plan how to split a large file into focused neurons |
| | `neuraltree_find_dead` | Find orphan files that nothing references |
| | `neuraltree_generate_index` | Auto-generate `_INDEX.md` for any directory |
| | `neuraltree_shrink_and_wire` | Atomic: extract sections + wire back-links + generate index |
| | `neuraltree_split_and_wire` | Atomic: split by headings + wire all pieces + replace with index |
| **Lessons** | `neuraltree_lesson_match` | Find past lessons matching a current situation |
| | `neuraltree_lesson_add` | Record a new lesson from an autoloop decision |
| **Scoring** | `neuraltree_score` | Compute structural metrics (5 of 6 — precision needs Viking) |
| | `neuraltree_diagnose` | Classify retrieval failures by gap type |
| **Semantic** | `neuraltree_precision` | Search Viking + retrieve content — Claude judges relevance externally |
| | `neuraltree_viking_index` | Batch-index local files into Viking semantic search |
| **Knowledge Map** | `neuraltree_knowledge_map` | Generate a structured map of project knowledge topology |
| **Sandbox** | `neuraltree_sandbox_create` | Create isolated git worktree for safe experimentation |
| | `neuraltree_sandbox_diff` | Compare sandbox changes against original |
| | `neuraltree_sandbox_apply` | Promote sandbox changes to the real project |
| | `neuraltree_sandbox_destroy` | Clean up sandbox worktree |

---

## Flow Score

The Flow Score is a single number (0.0-1.0) that tells you whether information is flowing or stuck. It's a weighted composite of 5 universal metrics derived from the knowledge map:

| Metric | Weight | What It Measures |
|--------|--------|-----------------|
| **Reachability** | 30% | % of files reachable in ≤3 hops from entry points (CLAUDE.md, README.md) via any edge type. |
| **Connectivity** | 25% | % of files with at least 1 edge — not orphaned from the knowledge graph. |
| **Cluster Coherence** | 20% | % of related-file pairs that share a parent directory — are related files co-located? |
| **Size Balance** | 15% | % of files within 3× median size — no mega-files burying information. |
| **Discoverability** | 10% | Precision@3 from Viking semantic search — can the AI actually find what it needs? |

| Score Range | Status | Meaning |
|-------------|--------|---------|
| 0.90 - 1.00 | EXCELLENT | Information flows freely. Weekly spot-checks suffice. |
| 0.75 - 0.89 | HEALTHY | Good shape. Targeted maintenance fixes will push it higher. |
| 0.60 - 0.74 | DEGRADED | Retrieval is unreliable. Several gaps need attention. |
| 0.00 - 0.59 | CRITICAL | Information flow is broken. Full intervention required. |

---

## Subcommands

| Command | Pipeline | Description |
|---------|----------|-------------|
| `/neuraltree` | Auto-detected | Detects mode from project state and runs the appropriate pipeline. |
| `/neuraltree understand` | Understand | Deep parallel exploration and knowledge map generation only. |
| `/neuraltree analyze` | Analyze only | Uses existing knowledge map to identify issues. |
| `/neuraltree fix` | Analyze → Plan → Execute → Verify | Jump straight to fixing — requires existing knowledge map. |
| `/neuraltree verify` | Verify only | Quick re-score with wiki lint + adaptive thresholds. |
| `/neuraltree map` | Show map | Display knowledge map summary (concept clusters, file graph). |
| `/neuraltree auto` | Full pipeline | Understand → Analyze → Plan → Execute → Verify. Always runs everything. |

---

## How It Works

### The Pipeline (v2 — Explore-First)

```
1. ACTIVATE    Verify tools, detect mode, acquire lock, scale agent count to project size
2. UNDERSTAND  Launch 2-10 parallel explorer agents, synthesize into dual-layer knowledge map
3. ANALYZE     Check past lessons, Claude reads the map and REASONS about what's wrong
4. PLAN        Propose concrete reorganization actions — user approves per-item
5. EXECUTE     Apply approved changes in sandbox, wire new/moved files, re-index Viking
6. VERIFY      Wiki lint + adaptive scoring confirms improvement — thresholds derived from project shape
```

### Explore-First vs Metric-First

v1 scored first, then fixed what the formula said. v2 **understands first**:

- **Explorer agents** read every knowledge file, not just scan metadata
- **Knowledge map** captures both structure (file graph) and meaning (concept clusters)
- **Claude reasons** about gaps instead of following hardcoded weights
- **Adaptive scoring** derives thresholds from the project's actual shape, not fixed numbers

Safe actions (wiring, indexing) are applied automatically. Destructive actions (deletes, moves, splits) are always held for your approval. All changes happen in a **sandbox** (isolated git worktree) first.

---

## Example Output

```
═══════════════════════════════════════════════════
  NeuralTree Report — my-project
  Mode: full | Agents: 5 | Duration: 94s
═══════════════════════════════════════════════════

Knowledge Map: 47 files → 8 concept clusters
  ├── API Layer (12 files) — well-connected
  ├── Database (8 files) — isolated island
  ├── Auth (6 files) — missing cross-refs to API
  └── ... 5 more clusters

Issues Found: 4
  1. CRITICAL  Database cluster has 0 inbound links from API layer
  2. HIGH      Auth middleware not referenced by any route handler docs
  3. MEDIUM    3 orphan files in docs/archive/ — never referenced
  4. LOW       2 index files over 100 lines (trunk pressure)

Flow Score: 0.52 → 0.81 (+0.29)  [adaptive thresholds]

SAFE ACTIONS (executed — non-destructive):
  + docs/database/schema.md — added ## Related (4 synapses to API layer)
  + docs/auth/middleware.md — wired to routes/protected.md
  + docs/api/_INDEX.md — regenerated (was 142 lines, now 67)

PENDING ACTIONS (require approval — destructive):
  1. ! MOVE docs/archive/old-api-notes.md → docs/api/migration-notes.md
  2. ! DELETE docs/archive/draft-v0.md — confirmed dead (0 references)

Which actions? (all / none / pick by number, e.g. '1,3')
```

---

## Modes

NeuralTree automatically detects the right mode based on your project's state:

| Mode | When | What Happens |
|------|------|-------------|
| **full** | First run (no knowledge map) | Full pipeline: Understand → Analyze → Plan → Execute → Verify. |
| **refresh** | Knowledge map exists but stale (>7 days) | Full pipeline — re-understands to catch changes. |
| **fix** | Map exists, recent, score < 0.60 | Analyze → Plan → Execute → Verify. Skip exploration. |
| **check** | Map exists, recent, score >= 0.60 | Verify only — quick adaptive re-score. |

---

## Key Principles

- **Artery Principle** — It's about FLOW, not storage. The neural tree is an artery system. Information must flow cleanly from trunk to leaf. Cleanup is a side effect, not the goal.
- **0-1-2 Hop Rule** — Any fact reachable in at most 2 tool calls. If it takes 3+ hops, the structure is broken.
- **Trace Before Prune** — Never delete a file without tracing every reference to it first. Dead neurons are confirmed dead, not assumed.
- **User Approves Destructive Actions** — The AutoLoop thinks, the user decides on deletes, moves, and archives.
- **Sandbox First** — All AutoLoop changes happen in an isolated git worktree. Nothing touches the real project until verified.
- **Measure Before You Fix** — The Flow Score is computed before any intervention. No fixing without a baseline.

---

## Development

### Run tests

```bash
# Full test suite (399 tests)
PYTHONPATH=src python3.11 -m pytest tests/ -v

# Quick smoke test
PYTHONPATH=src python3.11 -m pytest tests/ -x -q
```

### Verify tools load

```bash
PYTHONPATH=src python3.11 -c "
import asyncio
from neuraltree_mcp.server import mcp
tools = asyncio.run(mcp.list_tools())
print(f'{len(tools)} tools: {[t.name for t in tools]}')
"
```

### Run MCP server directly

```bash
PYTHONPATH=src python3.11 -m neuraltree_mcp.server
```

### Project structure

```
neuraltree/
├── src/
│   ├── neuraltree_mcp/          Python MCP server (FastMCP)
│   │   ├── server.py            Entry point — registers all 24 tools
│   │   ├── validation.py        Path traversal prevention
│   │   ├── text_utils.py        Shared utilities
│   │   ├── tools/               scan, trace, backup, wire, generate_queries, lesson, reorganize, knowledge_map, precision, viking_index
│   │   ├── scoring/             score, diagnose
│   │   └── sandbox/             sandbox_create, sandbox_diff, sandbox_apply, sandbox_destroy
│   └── skill/
│       ├── SKILL.md             Skill router (v2, explore-first)
│       └── sections/            6 phase files (understand, analyze, plan, execute, verify, report)
├── tests/
│   ├── unit/                    11 test files
│   └── integration/             5 test files (end-to-end via mcp.call_tool())
├── install.sh                   One-command installer
├── pyproject.toml               Package configuration
└── requirements.txt             Python dependencies
```

---

## Manual Installation

If you prefer not to use `install.sh`:

### 1. Install dependencies

```bash
pip install -r requirements.txt
# or with dev tools:
pip install -e ".[dev]"
```

### 2. Copy the skill

```bash
mkdir -p ~/.claude/skills/neuraltree/sections
cp src/skill/SKILL.md ~/.claude/skills/neuraltree/SKILL.md
cp src/skill/sections/*.md ~/.claude/skills/neuraltree/sections/
```

### 3. Register the MCP server

Add this to your `~/.claude.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "neuraltree": {
      "command": "python3.11",
      "args": ["-m", "neuraltree_mcp.server"],
      "cwd": "/absolute/path/to/neuraltree",
      "env": {
        "PYTHONPATH": "src"
      }
    }
  }
}
```

Replace `/absolute/path/to/neuraltree` with the actual path where you cloned the repository.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
