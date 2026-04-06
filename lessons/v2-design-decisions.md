---
name: V2 Design Decisions
description: Key architectural lessons from building NeuralTree v2
type: reference
last_verified: 2026-04-07
---

## Algorithms in tools, judgment in skills (2026-04-06)
- **Symptom:** Map phase had 190 lines of pseudocode for Jaccard, clustering, co-location. Claude read it, understood intent, and approximated — produced ~5 edges by intuition instead of computing all 136 pairs.
- **Root cause:** LLMs don't execute algorithms. They reason. Pseudocode in a skill is a suggestion, not enforcement.
- **Fix:** Move all deterministic computation into MCP tools. Skills orchestrate tool calls and make judgment decisions.
- **Principle:** `Algorithm → MCP tool (deterministic). Judgment → Claude (reasoning).`

## Viking > Jaccard for semantic similarity (2026-04-07)
- **Symptom:** Jaccard on agent-written `key_concepts` missed synonyms and depended on word choice.
- **Root cause:** Jaccard is lexical overlap. Concepts like "scoring" and "evaluation" share zero words but mean the same thing.
- **Fix:** Replace internal Jaccard edge computation with Viking (Model2Vec) semantic edges passed via `semantic_edges` parameter.
- **Principle:** Use embedding-based similarity for conceptual relationships. Reserve Jaccard for exact-match tasks only.

## Value filter prevents busywork (2026-04-07)
- **Symptom:** Pipeline proposed 7 issues, 3 were busywork (wire all files, add frontmatter to README, pad index). Signal-to-noise: 57%.
- **Root cause:** No filter between assessment and issue production.
- **Fix:** Added 4-rule value filter: drop "unwired" if reference chain works, drop frontmatter on standard files, drop fixes without a named beneficiary, drop padding for its own sake.
- **Result:** Signal-to-noise went from 57% to 100%.

## Docs
- `CLAUDE.md` — project overview
- `lessons/autoloop.md` — earlier autoloop lessons
