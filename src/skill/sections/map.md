# Map Phase — Knowledge Map Synthesis

> Viking finds the meaning. The tool builds the graph.

**Input:** `explorer_reports` from Explore phase (list of agent report dicts).
**Output:** `knowledge_map` saved to `.neuraltree/knowledge_map.json`.

## Step 1: Compute Semantic Edges via Viking

For each file in the explorer reports, query Viking with the file's topic
as search text. The top results that are OTHER known files (not itself)
become semantic edges.

```
semantic_edges = []
all_file_paths = set()
for report in explorer_reports:
    for f in report["files"]:
        all_file_paths.add(f["path"])

queries = []
for report in explorer_reports:
    for f in report["files"]:
        queries.append({"text": f["topic"], "source_file": f["path"]})

# Call Viking with all file topics as queries
precision_result = neuraltree_precision(
    queries=[{"text": q["text"]} for q in queries],
    project_root=".",
    limit=3,
)

# For each query result, find matches that are known project files
for i, qr in enumerate(precision_result["query_results"]):
    source_file = queries[i]["source_file"]
    for hit in qr.get("judgments", []):
        # Viking URIs look like: viking://resources/neuraltree/CLAUDE.md/chunk_abc123/...
        # Match against known file paths using the URI's path component
        uri = hit["uri"]
        matched_path = None
        for known_path in all_file_paths:
            # Check if the known filename appears in the Viking URI
            basename = known_path.split("/")[-1]
            if basename in uri and known_path != source_file:
                matched_path = known_path
                break
        if matched_path:
            semantic_edges.append({
                "source": source_file,
                "target": matched_path,
                "weight": round(hit["score"], 3),
                "reason": f"Viking similarity: {hit['score']:.3f}",
            })
```

**If Viking is unavailable (DEGRADED_MODE):** Skip this step. Pass
`semantic_edges=None` to the build action. The map will have reference
and co-location edges only.

## Step 2: Build the Knowledge Map

Pass explorer reports AND Viking semantic edges to the `build` action.
The tool deterministically computes:
- **Reference edges** from explicit `references_to` in each file report
- **Semantic edges** from Viking (passed in via `semantic_edges` parameter)
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

## Step 3: Emit Summary

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
| Semantic edges | Pre-computed by Viking/Model2Vec, passed via `semantic_edges` param | caller decides |
| Co-location edges | Files in same directory, only if no reference or semantic edge exists | weight = 0.5 |
| Clusters | Greedy: seed = file with most concepts, expand by 2+ shared concepts | overlap >= 2 |
| Orphans | Files with zero edges (not in any edge source or target) | severity: high |
| Scattered clusters | Clusters spanning 3+ directories | severity: medium |

**Proceed to Analyze (read `sections/analyze.md`).**
