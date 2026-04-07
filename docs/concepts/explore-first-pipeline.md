---
project: neuraltree
type: concept
---

# Explore-First Pipeline (v2)

**The 5-phase pipeline: Understand, Analyze, Plan, Execute, Verify.**

NeuralTree v2 replaced the metric-first approach (v1) with an explore-first approach. Instead of computing scores and fixing numbers, it starts by deeply understanding the project.

## The 5 Phases

| Phase | What Happens | Key Tools |
|---|---|---|
| 1. Understand | N parallel agents explore + build [Knowledge Map](knowledge-map.md) | `neuraltree_scan`, `neuraltree_knowledge_map` |
| 2. Analyze | Claude reasons about what's wrong, checks lessons | `neuraltree_diagnose`, `neuraltree_lesson_match` |
| 3. Plan | Propose reorganization, user approves | `neuraltree_plan_move`, `neuraltree_plan_split` |
| 4. Execute | Apply in [sandbox](sandbox-first.md) | `neuraltree_sandbox_*` |
| 5. Verify | Score confirms improvement, wiki lint, record lessons | `neuraltree_score`, `neuraltree_wiki_lint` |

## Explore-First vs Metric-First

- **Metric-First (v1):** Compute scores → fix lowest metric → re-score. Problem: optimizing numbers without understanding the project.
- **Explore-First (v2):** Read deeply → understand structure → reason about problems → fix with judgment. The [Artery Principle](artery-principle.md) in action.

## Related

- [Flow Score](flow-score.md) — used in Verify phase
- [Knowledge Map](knowledge-map.md) — built in Understand phase
- [Sandbox First](sandbox-first.md) — Execute phase uses sandbox
- [Autoloop](autoloop.md) — can run the pipeline autonomously
