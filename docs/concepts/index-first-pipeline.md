---
project: neuraltree
type: concept
---

# Index-First Pipeline (v3)

**The 7-phase pipeline: Index, Explore, Map, Analyze, Plan, Execute, Verify.**

NeuralTree v3 replaced the explore-first approach (v2) with an index-first approach. Instead of blanket-reading everything with agents, it runs all quantitative tools first (Viking indexing, wiki_lint, score, diagnose, find_dead, precision) to get the full health picture in seconds, then targets agent exploration at actual problem areas.

## The 7 Phases

| Phase | What Happens | Key Tools |
|---|---|---|
| 1. Index | Batch-index all files into Viking, run wiki_lint, score, diagnose, find_dead, precision | All 24 tools |
| 2. Explore | Targeted agents read problem areas deeply (scale-aware: full/targeted/sampled) | `neuraltree_scan`, Agent tool |
| 3. Map | Build [Knowledge Map](knowledge-map.md) from index data + explorer reports | `neuraltree_knowledge_map` |
| 4. Analyze | Claude reasons about what's wrong, checks lessons | `neuraltree_diagnose`, `neuraltree_lesson_match` |
| 5. Plan | Propose reorganization, user approves | `neuraltree_plan_move`, `neuraltree_plan_split` |
| 6. Execute | Apply in [sandbox](sandbox-first.md) | `neuraltree_sandbox_*` |
| 7. Verify | Score confirms improvement, wiki lint, record lessons | `neuraltree_score`, `neuraltree_wiki_lint` |

## Index-First vs Explore-First

- **Explore-First (v2):** Read everything with N agents → build map → analyze. Problem: at scale (1000+ files), agents skim too shallowly, Viking gets skipped, most tools go unused.
- **Index-First (v3):** Run all tools first → get quantitative health picture → target agents at problems only. The [Artery Principle](artery-principle.md) in action: tools give you the map, agents give you the understanding.

## Scale-Aware Exploration

| Project Size | Strategy | Agent Behavior |
|---|---|---|
| < 300 files | Full | Read everything (v2 behavior) |
| 300-2000 files | Targeted | Only problem areas from Index phase |
| 2000+ files | Sampled | Trunk + problems + random sample |

## Related

- [Flow Score](flow-score.md) — used in Verify phase
- [Knowledge Map](knowledge-map.md) — built in Map phase
- [Sandbox First](sandbox-first.md) — Execute phase uses sandbox
- [Autoloop](autoloop.md) — can run the pipeline autonomously
