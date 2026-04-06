---
project: neuraltree
type: concept
---

# Knowledge Map

**Dual-layer map of project structure and connections.**

The Knowledge Map is NeuralTree's internal representation of a project's information architecture. It's built during the Map phase of the [Explore-First Pipeline](explore-first-pipeline.md).

## Two Layers

1. **Structure Layer:** File tree with metadata (size, type, frontmatter, key concepts)
2. **Connection Layer:** Edges between files (imports, links, shared concepts, semantic similarity)

## How It's Built

1. [Explore phase](explore-first-pipeline.md) agents read every file with `neuraltree_scan`
2. Map phase synthesizes findings into `neuraltree_knowledge_map` (saved as `.neuraltree/knowledge_map.json`)
3. Connections are discovered via `neuraltree_wire` (keyword overlap) and [Viking](viking-semantic-search.md) (semantic similarity)

## How It's Used

- `neuraltree_diagnose` reads the map to identify structural problems
- `neuraltree_score` uses the map for wiring_density and cluster_coherence
- `neuraltree_find_dead` uses the map to find orphaned files
- The Skill reads it to understand the project before proposing changes

## Related

- [Explore First Pipeline](explore-first-pipeline.md) — map is built in Phase 2
- [Flow Score](flow-score.md) — map feeds multiple score components
- [Viking Semantic Search](viking-semantic-search.md) — adds semantic edges to the map
