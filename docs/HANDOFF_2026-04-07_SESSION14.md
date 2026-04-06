# Session 14 Handoff — 2026-04-07

## What Was Done

### 1. Precision Dedup Fix (Code)
`_viking_search()` in `precision.py` now **deduplicates by source document** — keeps only the highest-scoring chunk per source doc. Also increased over-fetch from `limit*3` to `limit*10` to handle cross-project bleed better.

New helper `_source_doc(uri)` extracts the source doc name from Viking chunk URIs.

### 2. Concept Pages — Karpathy LLM-Wiki (Knowledge)
Created `docs/concepts/` with **11 standalone concept pages**, each with frontmatter, definitions, and wikilinks to related concepts:

- `_INDEX.md` — navigation entry point
- `artery-principle.md` — "It's about FLOW, not storage"
- `hop-rule.md` — "0-1-2 Hop Rule"
- `trace-before-prune.md` — investigate before deleting
- `sandbox-first.md` — never modify real project directly
- `algorithm-tool-judgment-claude.md` — deterministic in tools, reasoning in Claude
- `explore-first-pipeline.md` — the 6-phase pipeline
- `flow-score.md` — universal organization metric
- `knowledge-map.md` — dual-layer project map
- `viking-semantic-search.md` — Model2Vec embeddings
- `autoloop.md` — autonomous improvement loop
- `user-approves-destructive.md` — user confirms all destructive actions

All 12 files indexed in Viking. Concept pages now score 0.42-0.57 (vs 0.30-0.35 for old overview chunks).

### 3. Wiki Lint Tool (New MCP Tool #26)
New `neuraltree_wiki_lint` tool — Karpathy-inspired wiki health checker:
- **Broken links** — wikilinks/markdown links to non-existent files
- **Orphan pages** — zero inbound links
- **Stale pages** — not modified in N days
- **Cross-reference density** — avg inbound links per page
- **Health score** — composite 0-100

21 new tests for the lint tool.

### 4. Precision Results

| Metric | Session 13 | Session 14 |
|--------|-----------|-----------|
| precision@3 | 0.62 | **0.81** |
| Zero-result queries | 2 | 0 |
| Tests | 400 | **426** |
| MCP tools | 25 | **26** |

## Files Changed (NOT YET COMMITTED)

```
src/neuraltree_mcp/tools/precision.py    — dedup by source doc, over-fetch *10
src/neuraltree_mcp/tools/wiki_lint.py    — NEW: wiki health checker
src/neuraltree_mcp/server.py             — register wiki_lint (26 tools)
tests/unit/test_precision.py             — +8 tests (dedup, _source_doc)
tests/unit/test_wiki_lint.py             — NEW: 21 tests
tests/integration/test_server.py         — tool count 25→26
CLAUDE.md                                — updated counts, structure, wiki category
docs/concepts/*.md                       — NEW: 12 concept pages
docs/HANDOFF_2026-04-07_SESSION14.md     — this file
```

## Key Insight: Karpathy's LLM-Wiki

Researched Karpathy's LLM-Wiki approach. Core lesson: **the fix is upstream of search — it's about how content is organized, not how you search it.**

1. **One concept = one page** — gives Viking clean, well-titled targets (implemented)
2. **Index-first navigation** — LLM reads index, drills into pages (implemented)
3. **Dense wikilinks** — every page links to related pages (implemented)
4. **LLM health checks** — periodic lint passes for broken links, orphans, staleness (implemented as `wiki_lint`)
5. **Raw → Wiki separation** — immutable sources vs LLM-owned summaries (partially done: handoffs=raw, concepts=wiki)

## Next Session Priorities

1. **Restart MCP** to pick up dedup fix + wiki_lint tool
2. **Test wiki_lint on neuraltree itself** — run it, see what it finds
3. **Commit everything** — stage and commit all changes
4. **Test on LocaNext at scale** — run full pipeline on a real large project
5. **Consider**: auto-maintenance in the Skill (update concept pages when source changes)
6. **Consider**: consolidate old handoff docs into archive (8 dead handoffs identified)
