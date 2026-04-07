# NeuralTree Concepts Index

> One concept per page. Each page is a self-contained definition with wikilinks to related concepts.

## Core Principles

- [Artery Principle](artery-principle.md) — It's about FLOW, not storage
- [0-1-2 Hop Rule](hop-rule.md) — Any information reachable in max 2 tool calls
- [Trace Before Prune](trace-before-prune.md) — Investigate every connection before deleting
- [Sandbox First](sandbox-first.md) — Never modify the real project directly
- [Algorithm Tool Judgment Claude](algorithm-tool-judgment-claude.md) — Deterministic logic in tools, reasoning in the Skill

## Architecture

- [Index-First Pipeline](index-first-pipeline.md) — The 7-phase pipeline: Index, Explore, Map, Analyze, Plan, Execute, Verify
- [Flow Score](flow-score.md) — Universal organization quality metric (0-100)
- [Knowledge Map](knowledge-map.md) — Dual-layer map of project structure and connections
- [Viking Semantic Search](viking-semantic-search.md) — Model2Vec embeddings for concept-level search

## Patterns

- [Autoloop](autoloop.md) — Autonomous improvement loop with KEEP/HOLD/DISCARD decisions
- [User Approves Destructive Actions](user-approves-destructive.md) — Autoloop thinks, user decides on deletes/moves
