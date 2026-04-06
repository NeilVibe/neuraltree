---
project: neuraltree
type: concept
---

# Viking Semantic Search

**Model2Vec embeddings for concept-level search across project documentation.**

Viking (OpenViking) is the semantic search layer that powers NeuralTree's discoverability scoring and concept retrieval.

## How It Works

1. Documents are chunked and embedded using Model2Vec (running on port 8100)
2. Embeddings are stored in Viking's index (port 1933)
3. `neuraltree_precision` searches Viking and retrieves content for relevance judging
4. `neuraltree_viking_index` batch-indexes project files into Viking

## Role in NeuralTree

- **Discoverability scoring:** Can an agent find key concepts via semantic search? (precision@3)
- **Embedding gap detection:** `neuraltree_diagnose` checks if important files are missing from the index
- **Concept retrieval:** The Skill uses Viking to find related documentation before proposing changes

## Precision@3

The primary metric for Viking quality. For each auto-generated query:
1. Search Viking for top 3 results
2. Claude judges each result as relevant or not
3. precision@3 = relevant results / total results

Results are deduplicated by source document to prevent one large file from consuming all result slots.

## Related

- [Flow Score](flow-score.md) — discoverability component uses Viking
- [0-1-2 Hop Rule](hop-rule.md) — Viking enables 1-hop concept retrieval
- [Knowledge Map](knowledge-map.md) — Viking adds semantic edges
