# Session 15 Handoff — 2026-04-07

## What Was Done

### 1. Committed Session 13+14 Work
All previously uncommitted work staged and committed:
- Wiki lint tool (#26), precision dedup, 11 concept pages, 426 tests

### 2. Precision Overview-Stub Fix
`_viking_search()` in `precision.py` now **skips `.overview.md` stubs** and prefers content chunks from the same source doc. Viking indexes files as directories — the `.overview.md` is a title-only stub (32-68 chars), while `upload_xxx.md` chunks have the actual content (978-3000 chars).

Live test confirmed: content lengths went from 52-68ch stubs to 978-3000ch real content. +3 new tests (429 total).

### 3. Knowledge Map Rebuild (21 → 85 files)
The old knowledge map was stale (21 files, 98 edges, cluster_coherence=0). Rebuilt from scratch:
- Generated explorer reports from actual project files (85 files)
- Extracted 123 cross-references (Python imports, markdown links, wikilinks)
- New map: **85 files, 482 edges, 10 clusters**

### 4. CLAUDE.md Wiring
Added markdown links from Key Principles to concept pages and SKILL.md. This made all concept pages, skill sections, and lessons reachable from entry points.

### 5. Flow Score Progress

| Metric | Session Start | Session End |
|--------|--------------|-------------|
| reachability | 1.00 (stale map) | **0.882** (real) |
| connectivity | 1.00 | **1.00** |
| cluster_coherence | **0.00** | **0.941** |
| size_balance | 0.952 | **0.871** |
| discoverability | null | **null** (needs MCP restart) |
| **flow_score** | **0.693** | **0.833** |

### 6. Wiki Lint on Itself
Ran wiki_lint on neuraltree: health_score=60, 0 broken links, 23 orphans (handoffs + skill sections — expected), 0 stale.

## Files Changed

```
src/neuraltree_mcp/tools/precision.py    — overview-stub skip in dedup
tests/unit/test_precision.py             — +3 overview-skip tests (429 total)
CLAUDE.md                                — wired to concept pages + SKILL.md
.neuraltree/knowledge_map.json           — rebuilt (85 files, 482 edges)
docs/HANDOFF_2026-04-07_SESSION15.md     — this file
```

## Commits (3)

```
0473895 docs: wire CLAUDE.md to concept pages and SKILL.md for reachability
ed23e83 fix: skip .overview.md stubs in precision dedup, prefer content chunks
de006f6 feat: wiki_lint tool, precision dedup, Karpathy concept pages
```

## MCP Needs Restart

The MCP server (PID 4001427) is running pre-fix code. After restart:

### Step 1: Re-run Precision
```
neuraltree_generate_queries(project_root="/home/neil1988/neuraltree")
→ feed queries into neuraltree_precision()
→ judge results, compute precision@3 (should be much higher with overview-skip fix)
```

### Step 2: Fill Discoverability
Precision@3 result fills the null discoverability metric → completes the flow score.

## Next Session Priorities

1. **Restart MCP** — pick up overview-skip fix
2. **Re-run precision** — get real discoverability score, complete flow score
3. **Archive handoff docs** — 10 dead handoffs drag down reachability (0.882 → ~0.98 if archived)
4. **Size balance** — 11 oversized files flagged (reorganize.py 31KB, knowledge_map.py 21KB, test files 17-25KB)
5. **Test on LocaNext at scale** — run full pipeline on a real large project
6. **Consider**: auto-maintenance in the Skill (rebuild knowledge map when source changes)
