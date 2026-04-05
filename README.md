# NeuralTree

**Universal neural organization for AI coding agents.**

NeuralTree transforms any project into a structured information system where any fact is reachable in 0-2 hops, every node is wired to related nodes, and semantic search catches what structure misses. It measures information flow with a single composite metric (Flow Score), diagnoses retrieval failures, and auto-repairs them in a sandboxed loop — so your AI agent can always *find* what it needs.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  /neuraltree                         │
│              THE BRAIN (Skill)                       │
│   Orchestrator — benchmarks, diagnoses,              │
│   auto-repairs, enforces. You invoke it, it drives.  │
├──────────────┬──────────────────┬───────────────────┤
│ neuraltree   │  Viking MCP      │  Qwen3.5          │
│ THE MUSCLE   │  THE MEMORY      │  THE JUDGE        │
│ 22 tools     │  Semantic search │  YES/NO relevance │
│ scan, score, │  across all      │  judgments for     │
│ wire, diag,  │  indexed content │  Precision@3      │
│ sandbox...   │                  │  scoring           │
└──────────────┴──────────────────┴───────────────────┘
```

**Brain** orchestrates everything. **Muscle** does pure computation (filesystem scans, scoring, wiring). **Memory** provides semantic search. **Judge** evaluates retrieval quality. The Brain is the only component that calls the other three.

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

That's it. NeuralTree detects it's a first run (bootstrap mode), scans your project, generates test queries, benchmarks information flow, diagnoses gaps, auto-repairs what it can in a sandbox, and produces a report.

---

## Prerequisites

| Dependency | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | MCP server runtime |
| [FastMCP](https://github.com/jlowin/fastmcp) | 2.0.0+ | MCP server framework |
| [Viking MCP](https://github.com/openviking) | any | Semantic search — the memory layer. Indexes all project docs for embedding-powered retrieval. |
| [Ollama](https://ollama.com) + Qwen3.5 | any | LLM-as-Judge — scores whether Viking search results actually answer test queries (Precision@3). Set `"think": false` for speed. |
| Claude Code | any | AI coding agent that runs the skill |

### Install Ollama + Qwen3.5

```bash
# Install Ollama (if not already installed)
curl -fsSL https://ollama.com/install.sh | sh

# Pull the model
ollama pull qwen3:latest
```

NeuralTree calls Ollama with `"think": false` and `temperature: 0` for fast, deterministic YES/NO judgments. Without Qwen3.5, Precision@3 (25% of Flow Score) cannot be computed and scoring runs in degraded mode.

---

## MCP Tools (24)

NeuralTree's MCP server provides 24 tools across 7 categories:

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
| | `neuraltree_predict` | Virtual backtest — simulate changes before applying |
| | `neuraltree_update_calibration` | Update prediction model accuracy from real outcomes |
| **Semantic** | `neuraltree_precision` | Compute Precision@3 — searches Viking + judges with Qwen3.5 in one call |
| | `neuraltree_viking_index` | Batch-index local files into Viking semantic search |
| **Sandbox** | `neuraltree_sandbox_create` | Create isolated git worktree for safe experimentation |
| | `neuraltree_sandbox_diff` | Compare sandbox changes against original |
| | `neuraltree_sandbox_apply` | Promote sandbox changes to the real project |
| | `neuraltree_sandbox_destroy` | Clean up sandbox worktree |

---

## Flow Score

The Flow Score is a single number (0.0-1.0) that tells you whether information is flowing or stuck. It's a weighted composite of 6 metrics:

| Metric | Weight | What It Measures |
|--------|--------|-----------------|
| **Hop Efficiency** | 25% | Can any fact be reached in 0-2 hops? The fundamental guarantee. |
| **Precision@3** | 25% | Do the top 3 Viking search results actually answer the query? |
| **Synapse Coverage** | 20% | What percentage of knowledge files have `## Related` cross-references? |
| **Dead Neuron Ratio** | 15% | How many files are orphaned — referenced by nothing, invisible to the network? |
| **Freshness** | 10% | Are files verified recently, or is the content stale and untrusted? |
| **Trunk Pressure** | 5% | Are index files lean (<100 lines), or bloated with noise? |

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
| `/neuraltree audit` | Benchmark only | Read-only analysis. Outputs Flow Score + gap report. No changes. |
| `/neuraltree fix` | Diagnose + AutoLoop | Skip benchmarking, jump straight to fixing diagnosed gaps. |
| `/neuraltree enforce` | Enforce only | Update state, re-index Viking, clean temp files. No analysis. |
| `/neuraltree benchmark` | Full benchmark | Detailed scoring with per-metric breakdown and precision analysis. |
| `/neuraltree auto` | Full pipeline | Benchmark, Diagnose, AutoLoop, Enforce. Always runs everything. |

---

## How It Works

### The Pipeline

```
1. ACTIVATE    Verify tools, detect mode, acquire lock
2. BENCHMARK   Generate queries, search Viking, judge precision, compute Flow Score
3. DIAGNOSE    Classify each failure — SYNAPSE_GAP, DEAD_NEURON, EMBEDDING_GAP, etc.
4. AUTOLOOP    Karpathy-style loop: predict improvement, apply fix, measure, keep/discard
5. ENFORCE     Update state.json, re-index Viking, record lessons, emit report
```

### The AutoLoop

The AutoLoop is NeuralTree's self-repair engine. It runs in a **sandbox** (isolated git worktree) so it never touches your real project until changes are verified:

1. **Predict** — For each diagnosed gap, predict how much fixing it will improve the Flow Score
2. **Prioritize** — Sort by predicted improvement, work on the highest-impact gap first
3. **Fix** — Apply the repair (add cross-references, re-index, update frontmatter)
4. **Measure** — Re-score in the sandbox. Did the Flow Score actually improve?
5. **Decide** — KEEP (improvement confirmed), DISCARD (no improvement), or HOLD (needs human review)
6. **Repeat** — Up to 10 iterations, stopping early if the score converges or hits 0.95+

Safe actions (wiring, indexing) are applied automatically. Destructive actions (deletes, moves) are always held for your approval.

---

## Example Output

```
═══════════════════════════════════════════════════
  NeuralTree Report — my-project
  Mode: bootstrap | Duration: 127s
═══════════════════════════════════════════════════

Flow Score: 0.41 -> 0.87 (+0.46)

┌──────────────────────────────────────────────────┐
│ Metric              Before   After    Delta      │
│ Hop Efficiency       0.45    0.88    +0.43       │
│ Precision@3          0.33    0.87    +0.54       │
│ Synapse Coverage     0.61    0.97    +0.36       │
│ Dead Neuron Ratio    0.70    1.00    +0.30       │
│ Freshness            0.80    0.95    +0.15       │
│ Trunk Pressure       0.80    1.00    +0.20       │
└──────────────────────────────────────────────────┘

SAFE ACTIONS (executed — non-destructive):
  + memory/rules/build_rules.md — added ## Related (3 synapses)
  + memory/active/phase3.md — re-indexed in Viking
  + docs/architecture/overview.md — added ## Related (5 synapses)

PENDING ACTIONS (require approval — destructive):
  1. ! CREATE memory/reference/api_patterns.md — content gap: no API documentation
  2. ! SPLIT docs/MONOLITH.md — focus gap: 340 lines, 6 distinct topics

AutoLoop: 7 iterations, 5 KEEP / 2 DISCARD / 2 HOLD
Calibration accuracy: 72%
Exit reason: converged (delta < 0.005 for 3 iterations)
Next run ETA: 3 days (health-check)

Which actions? (all / none / pick by number, e.g. '1,3')
```

---

## Modes

NeuralTree automatically detects the right mode based on your project's state:

| Mode | When | What Happens |
|------|------|-------------|
| **bootstrap** | First run (no `.neuraltree/state.json`) | Full pipeline. Sandbox mandatory. |
| **critical** | Flow Score < 0.60 | Full pipeline. Sandbox mandatory. |
| **health-check** | Last run > 7 days ago | Re-benchmark everything, fix if degraded. |
| **maintenance** | Score 0.60-0.90, run within 7 days | Targeted fixes for degraded areas only. |
| **spot-check** | Score > 0.90, run within 7 days | Quick verification. 30 seconds. |

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
# Full test suite (306 tests)
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
│   │   ├── server.py            Entry point — registers all 22 tools
│   │   ├── validation.py        Path traversal prevention
│   │   ├── text_utils.py        Shared utilities
│   │   ├── tools/               scan, trace, backup, wire, generate_queries, lesson, reorganize
│   │   ├── scoring/             score, diagnose, predict, update_calibration
│   │   └── sandbox/             sandbox_create, sandbox_diff, sandbox_apply, sandbox_destroy
│   └── skill/
│       └── SKILL.md             2,500-line skill instruction file
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
mkdir -p ~/.claude/skills/neuraltree
cp src/skill/SKILL.md ~/.claude/skills/neuraltree/SKILL.md
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
