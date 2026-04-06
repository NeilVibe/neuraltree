---
project: neuraltree
type: concept
---

# Explore-First Pipeline (v2)

**The 6-phase pipeline: Explore, Map, Analyze, Plan, Execute, Verify.**

NeuralTree v2 replaced the metric-first approach (v1) with an explore-first approach. Instead of computing scores and fixing numbers, it starts by deeply understanding the project.

## The 6 Phases

| Phase | What Happens | Key Tools |
|---|---|---|
| 1. Explore | N parallel agents read the project deeply | `neuraltree_scan`, `neuraltree_trace` |
| 2. Map | Synthesize findings into a dual-layer [Knowledge Map](knowledge-map.md) | `neuraltree_knowledge_map` |
| 3. Analyze | Claude reasons about what's wrong (not formulas) | `neuraltree_diagnose`, `neuraltree_score` |
| 4. Plan | Propose reorganization, user approves | `neuraltree_plan_move`, `neuraltree_plan_split` |
| 5. Execute | Apply in [sandbox](sandbox-first.md) | `neuraltree_sandbox_*` |
| 6. Verify | Score confirms improvement | `neuraltree_score`, `neuraltree_precision` |

## Explore-First vs Metric-First

- **Metric-First (v1):** Compute scores → fix lowest metric → re-score. Problem: optimizing numbers without understanding the project.
- **Explore-First (v2):** Read deeply → understand structure → reason about problems → fix with judgment. The [Artery Principle](artery-principle.md) in action.

## Related

- [Flow Score](flow-score.md) — used in Verify phase
- [Knowledge Map](knowledge-map.md) — built in Map phase
- [Sandbox First](sandbox-first.md) — Execute phase uses sandbox
- [Autoloop](autoloop.md) — can run the pipeline autonomously
