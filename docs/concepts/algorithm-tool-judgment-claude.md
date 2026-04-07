---
project: neuraltree
type: concept
---

# Algorithm in Tool, Judgment in Claude

**Deterministic logic lives in MCP tools. Reasoning lives in the Skill.**

This is NeuralTree's fundamental architecture split between the MCP server and the Skill (SKILL.md).

## The Split

| Lives in MCP Tools | Lives in Claude (Skill) |
|---|---|
| File scanning, path traversal | Deciding what's important |
| Keyword extraction, Jaccard similarity | Judging if a connection is meaningful |
| Score computation formulas | Interpreting scores in context |
| Sandbox file operations | Deciding what to move/split/delete |
| Viking search queries | Judging if results are relevant |

## Why This Split

- **Tools are fast, repeatable, testable** — unit tests cover every edge case
- **Claude is flexible, contextual, creative** — handles ambiguity and novel situations
- **No hardcoded heuristics for judgment** — the Skill prompts Claude to reason, not follow rules
- **Tools don't hallucinate** — they return facts, Claude interprets them

## V2 Design Decision

This split was formalized in v2 after v1 tried to encode too much judgment in tool code (hardcoded scoring formulas that didn't generalize). See `lessons/v2-design-decisions.md`.

## Related

- [Flow Score](flow-score.md) — tools compute partial score, Claude judges discoverability
- [Index-First Pipeline](index-first-pipeline.md) — tools index, agents explore, Claude analyzes
- [Autoloop](autoloop.md) — tools propose, Claude decides KEEP/HOLD/DISCARD
