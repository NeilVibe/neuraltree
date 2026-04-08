# Index Phase — Full Project Indexing

> Index everything. Score everything. THEN decide what to explore.

**Input:** `scan_result`, `knowledge_files`, `project_root`.
**Output:** `index_results` — wiki_lint, score, diagnose, semantic edges, dead files.

This phase runs ALL quantitative tools BEFORE any agent exploration.
It gives Claude the full picture of the project's health so exploration
can be targeted at actual problem areas, not blanket reading.

## Step 1: Viking Batch Index

Index ALL knowledge files into Viking for semantic search.
Batch in groups of 50 to avoid overwhelming the API.

```
if not DEGRADED_MODE:
    # Batch index all knowledge files
    batch_size = 50
    total_indexed = 0
    for i in range(0, len(knowledge_files), batch_size):
        batch = knowledge_files[i:i+batch_size]
        result = neuraltree_viking_index(
            file_paths=batch,
            project_root=project_root,
        )
        total_indexed += result.get("indexed", 0)
        emit(f"  Viking indexed: {total_indexed}/{len(knowledge_files)}")
    emit(f"Phase 1a: Viking indexed {total_indexed} files")
else:
    emit("Phase 1a: Viking unavailable — skipping semantic indexing")
```

## Step 2: Wiki Lint

Run wiki_lint to get the structural health assessment:
- Broken links (references to files that don't exist)
- Orphan pages (files nothing links to)
- Freshness (files not modified recently)
- Cross-reference density (how well-connected the wiki is)
- Health score (composite)

```
lint_result = neuraltree_wiki_lint(
    project_root=project_root,
    max_age_days=90,
)
emit(f"Phase 1b: Wiki lint — health={lint_result['health_score']}, "
     f"broken={len(lint_result['broken_links'])}, "
     f"orphans={len(lint_result['orphan_pages'])}, "
     f"stale={len(lint_result['stale_pages'])}")
```

## Step 3: Flow Score (Baseline)

Score the project's information flow. If no knowledge map exists yet,
this returns `no_map: true` with null metrics — that's expected on first run.
The real score comes after Phase 3 (Map).

```
score_result = neuraltree_score(
    project_root=project_root,
)
if score_result.get("no_map"):
    emit("Phase 1c: Flow score — N/A (no knowledge map yet, will score after Phase 3)")
else:
    emit(f"Phase 1c: Flow score — {score_result.get('flow_score_partial', 'N/A')}")
```

## Step 4: Find Dead Files

Find files that nothing references at all.

```
dead_result = neuraltree_find_dead(
    project_root=project_root,
)
emit(f"Phase 1d: Dead files — {dead_result['total_dead']} unreferenced files")
```

## Step 5: Semantic Edge Discovery (Viking Precision)

Generate search queries from representative files and run Viking
precision to discover semantic relationships across the project.

For large projects (300+ files), sample strategically:
- All trunk files (CLAUDE.md, README.md, INDEX files)
- All orphan files from wiki_lint
- Random sample from each directory (max 3 per dir)

```
if not DEGRADED_MODE:
    # Generate queries for representative files
    query_result = neuraltree_generate_queries(
        project_root=project_root,
    )
    queries = query_result.get("queries", [])

    # Run precision in batches of 30
    all_precision_results = []
    batch_size = 30
    for i in range(0, len(queries), batch_size):
        batch = queries[i:i+batch_size]
        precision_result = neuraltree_precision(
            queries=batch,
            project_root=project_root,
            limit=3,
        )
        all_precision_results.extend(
            precision_result.get("query_results", [])
        )
        emit(f"  Precision: {min(i+batch_size, len(queries))}/{len(queries)} queries")

    # Build semantic edges from precision results
    semantic_edges = []
    for qr in all_precision_results:
        source = qr.get("query", "")
        for hit in qr.get("judgments", []):
            semantic_edges.append({
                "source": source,
                "target": hit.get("uri", ""),
                "weight": round(hit.get("score", 0), 3),
                "reason": f"Viking similarity: {hit.get('score', 0):.3f}",
            })

    emit(f"Phase 1e: {len(semantic_edges)} semantic edges from Viking precision")

    # Identify failed queries (low/no results) for diagnose
    failed_queries = []
    for qr in all_precision_results:
        judgments = qr.get("judgments", [])
        if not judgments or all(j.get("score", 0) < 0.3 for j in judgments):
            failed_queries.append({"text": qr.get("query", "")})
else:
    semantic_edges = None
    failed_queries = []
    emit("Phase 1e: Skipped (Viking unavailable)")
```

## Step 6: Diagnose

Classify what's wrong using failed precision queries.
Now runs AFTER precision so it has actual query failures to diagnose.

```
if failed_queries:
    diagnose_result = neuraltree_diagnose(
        failed_queries=failed_queries,
        project_root=project_root,
        viking_results=[
            {"query": qr.get("query", ""), "results": [j.get("uri", "") for j in qr.get("judgments", [])]}
            for qr in all_precision_results
        ] if not DEGRADED_MODE else None,
    )
    emit(f"Phase 1f: Diagnose — {diagnose_result['total_failures']} gap(s) classified: {diagnose_result['gap_counts']}")
else:
    diagnose_result = {"diagnoses": [], "gap_counts": {}, "total_failures": 0, "warnings": ["No failed queries to diagnose"]}
    emit("Phase 1f: Diagnose — no failed queries, all precision results look good")
```

## Step 7: Check Lessons

Check if we've seen similar issues before.

```
lesson_result = neuraltree_lesson_match(
    context=f"Project with {len(knowledge_files)} knowledge files, "
            f"health_score={lint_result.get('health_score', 'unknown')}, "
            f"orphans={len(lint_result.get('orphan_pages', []))}, "
            f"broken_links={len(lint_result.get('broken_links', []))}",
    project_root=project_root,
)
if lesson_result.get("matches"):
    emit(f"Phase 1g: {len(lesson_result['matches'])} past lessons matched")
    for lesson in lesson_result["matches"][:3]:
        emit(f"  - {lesson.get('title', 'untitled')}")
else:
    emit("Phase 1g: No past lessons found")
```

## Step 8: Emit Index Summary

```
index_results = {
    "wiki_lint": lint_result,
    "score": score_result,
    "diagnose": diagnose_result,
    "dead_files": dead_result,
    "semantic_edges": semantic_edges,
    "lessons": lesson_result,
    "viking_indexed": total_indexed if not DEGRADED_MODE else 0,
}

# Identify problem areas for targeted exploration
problem_dirs = set()
for orphan in lint_result.get("orphan_pages", []):
    problem_dirs.add(os.path.dirname(orphan.get("file", "")) or ".")
for broken in lint_result.get("broken_links", []):
    problem_dirs.add(os.path.dirname(broken.get("file", "")) or ".")
for issue in diagnose_result.get("issues", []):
    for f in issue.get("files", []):
        problem_dirs.add(os.path.dirname(f) or ".")

emit(f"""
Phase 1/8: Index Complete
  Viking indexed: {index_results['viking_indexed']} files
  Wiki health:    {lint_result.get('health_score', '?')}
  Flow score:     {score_result.get('flow_score_partial', '?')}
  Broken links:   {len(lint_result.get('broken_links', []))}
  Orphans:        {len(lint_result.get('orphan_pages', []))}
  Stale files:    {len(lint_result.get('stale_pages', []))}
  Dead files:     {dead_result['total_dead']}
  Semantic edges: {len(semantic_edges) if semantic_edges else 0}
  Problem dirs:   {len(problem_dirs)}
  Past lessons:   {len(lesson_result.get('matches', []))}
""")
```

## Step 9: Save Checkpoint

Persist ALL index results to `.neuraltree/` so they survive context
compaction and session boundaries. These are the project's health snapshot.

```
write_file(".neuraltree/index_results.json", json.dumps({
    "timestamp": now_iso8601(),
    "total_files": len(knowledge_files),
    "viking_indexed": index_results["viking_indexed"],
    "wiki_lint": lint_result,
    "score": score_result,
    "diagnose": diagnose_result,
    "dead_files": dead_result,
    "semantic_edges_count": len(semantic_edges) if semantic_edges else 0,
    "lessons": lesson_result,
    "problem_dirs": sorted(problem_dirs),
}, indent=2))
emit("Checkpoint saved: .neuraltree/index_results.json")
```

**If resuming a session:** Check for `.neuraltree/index_results.json` first.
If it exists and is < 1 hour old, LOAD it instead of re-running Phase 1.
This prevents wasting tokens re-indexing when context was compacted.

**Proceed to Explore (read `sections/explore.md`).**
