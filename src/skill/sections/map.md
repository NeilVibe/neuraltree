# Map Phase — Knowledge Map Synthesis

> Viking finds the meaning. The tool builds the graph.

**Input:** `explorer_reports` from Explore phase, `index_results` from Index phase.
**Output:** `knowledge_map` saved to `.neuraltree/knowledge_map.json`.

## Step 1: Use Semantic Edges from Index Phase

The Index phase already computed semantic edges via Viking precision.
Use those directly — do NOT re-query Viking here.

```
# Semantic edges were computed in Phase 1 (Index)
semantic_edges = index_results.get("semantic_edges", None)
```

If the Index phase was skipped (e.g., `/neuraltree explore` subcommand),
compute semantic edges now following the approach in `sections/index.md` Step 6.

## Step 2: Build the Knowledge Map

Pass explorer reports AND Index semantic edges to the `build` action.
The tool deterministically computes:
- **Reference edges** from explicit `references_to` in each file report
- **Semantic edges** from Viking (pre-computed in Index phase)
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
    semantic_edges=semantic_edges,
)
# result contains: saved (path), knowledge_map (full map), stats (summary)
```

The tool saves the map to `.neuraltree/knowledge_map.json` automatically.

**If `result` contains an `"error"` key:** Stop and report the error to the user. Do NOT proceed to Analyze.

**If `result["warnings"]` is non-empty:** Show warnings to the user (e.g., skipped paths, dropped reports) but continue.

## Step 3: Enrich with Index Data

Merge wiki_lint and diagnose results from the Index phase into the
knowledge map's issue list. This ensures the map contains ALL known
issues — both structural (from the map build) and tool-detected
(from wiki_lint, score, diagnose, find_dead).

```
# Add wiki_lint broken links as map issues
for broken in index_results["wiki_lint"].get("broken_links", []):
    # Add as issue if not already in map
    ...

# Add diagnose issues
for issue in index_results["diagnose"].get("issues", []):
    # Add as issue if not already in map
    ...
```

## Step 4: Emit Summary

```
stats = result["stats"]
emit(f"Phase 3/8: Knowledge map built — {stats['total_files']} files, "
     f"{stats['total_edges']} edges, {stats['total_clusters']} clusters, "
     f"{stats['total_issues']} issues")
```

## What the Tool Computes (for reference — you do NOT need to do this)

| Computation | Algorithm | Threshold |
|-------------|-----------|-----------|
| Reference edges | For each file's `references_to`, create edge if target is a known file | - |
| Semantic edges | Pre-computed by Viking/Model2Vec in Index phase, passed via `semantic_edges` | caller decides |
| Co-location edges | Files in same directory, only if no reference or semantic edge exists | weight = 0.5 |
| Clusters | Greedy: seed = file with most concepts, expand by 2+ shared concepts | overlap >= 2 |
| Orphans | Files with zero edges (not in any edge source or target) | severity: high |
| Scattered clusters | Clusters spanning 3+ directories | severity: medium |

**Proceed to Compile (read `sections/compile.md`).**
