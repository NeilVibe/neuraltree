# Map Phase — Knowledge Map Synthesis

> One tool call. No pseudocode. The MCP tool does ALL computation.

**Input:** `explorer_reports` from Explore phase (list of agent report dicts).
**Output:** `knowledge_map` saved to `.neuraltree/knowledge_map.json`.

## Step 1: Build the Knowledge Map (ONE tool call)

Pass ALL explorer reports to the `build` action. The tool deterministically computes:
- **Reference edges** from explicit `references_to` in each file report
- **Semantic edges** via pairwise Jaccard on `key_concepts` (threshold > 0.3, overlap >= 2)
- **Co-location edges** for files in the same directory (only if no stronger edge exists)
- **Greedy concept clusters** (seed by most concepts, expand by 2+ shared)
- **Graph-derived issues** (orphan files with no edges, scattered clusters spanning 3+ dirs)
- **Explorer-reported issues** propagated from file reports
- **Stats** (totals, averages, median, max depth)

```
result = neuraltree_knowledge_map(
    action="build",
    project_root=".",
    explorer_reports=explorer_reports,
)
# result contains: saved (path), knowledge_map (full map), stats (summary)
```

The tool saves the map to `.neuraltree/knowledge_map.json` automatically.

**If `result` contains an `"error"` key:** Stop and report the error to the user. Do NOT proceed to Analyze.

**If `result["warnings"]` is non-empty:** Show warnings to the user (e.g., skipped paths, dropped reports) but continue.

## Step 2: Emit Summary

```
stats = result["stats"]
emit(f"Phase 2/6: Knowledge map built — {stats['total_files']} files, "
     f"{stats['total_edges']} edges, {stats['total_clusters']} clusters, "
     f"{stats['total_issues']} issues")
```

## What the Tool Computes (for reference — you do NOT need to do this)

| Computation | Algorithm | Threshold |
|-------------|-----------|-----------|
| Reference edges | For each file's `references_to`, create edge if target is a known file | - |
| Semantic edges | Pairwise Jaccard similarity on `key_concepts` sets | Jaccard > 0.3 AND overlap >= 2 |
| Co-location edges | Files in same directory, only if no reference or semantic edge exists | weight = 0.5 |
| Clusters | Greedy: seed = file with most concepts, expand by 2+ shared concepts | overlap >= 2 |
| Orphans | Files with zero edges (not in any edge source or target) | severity: high |
| Scattered clusters | Clusters spanning 3+ directories | severity: medium |

**Proceed to Analyze (read `sections/analyze.md`).**
