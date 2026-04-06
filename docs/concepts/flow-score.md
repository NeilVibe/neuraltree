---
project: neuraltree
type: concept
---

# Flow Score

**Universal organization quality metric (0-100).**

The Flow Score measures how well-organized a project is from an information retrieval perspective. It's the primary metric for the [Artery Principle](artery-principle.md).

## Components

| Metric | Weight | What It Measures |
|---|---|---|
| `wiring_density` | 20% | How well files are cross-referenced |
| `index_coverage` | 20% | What percentage of files appear in indexes |
| `naming_quality` | 15% | How descriptive and consistent file names are |
| `tree_depth_penalty` | 15% | Penalizes excessive nesting (>4 levels) |
| `cluster_coherence` | 20% | Whether related files are grouped together |
| `discoverability` | 10% | Can [Viking](viking-semantic-search.md) find key concepts? (precision@3) |

## How It's Computed

1. `neuraltree_score` computes all metrics except discoverability (returns `discoverability: null`)
2. The Skill runs `neuraltree_precision` with auto-generated queries
3. Claude judges each Viking result as relevant or not
4. Final score: `flow_score_partial + (discoverability * 0.10)`

## Interpretation

- **0-30:** Poorly organized, agents struggle to find information
- **30-60:** Partially organized, some gaps in retrieval
- **60-80:** Well organized, most information reachable in 1-2 hops
- **80-100:** Excellent, comprehensive wiring and discoverability

## Related

- [Artery Principle](artery-principle.md) — the philosophy behind Flow Score
- [0-1-2 Hop Rule](hop-rule.md) — what Flow Score measures
- [Viking Semantic Search](viking-semantic-search.md) — powers the discoverability component
- [Algorithm Tool Judgment Claude](algorithm-tool-judgment-claude.md) — tools compute, Claude judges
