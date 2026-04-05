# Diagnose Protocol

> Failed queries are symptoms. Gap types are the diagnosis. The priority queue is the treatment plan.

**Input:** `baseline` object from Benchmark, `DEGRADED_MODE` flag.
**Output:** `priority_queue` (sorted list of gaps to fix), `diagnosis` object.

## Step 1: Identify Failed Queries

A query "fails" if `precision_at_3 < 0.67` OR the correct source file was not in Viking's top 3.

```
failed_queries = []
for query in baseline["queries"]:
    correct_file_found = any(
        query.get("source", "") in r["uri"]
        for r in query.get("viking_results", [])
    )
    if query.get("precision", 1.0) < 0.67 or not correct_file_found:
        failed_queries.append(query)
```

If `failed_queries` is empty — all queries passed. Initialize default `autoloop_state`, set `exit_reason = "no_failures"`, skip to Enforce (`sections/enforce.md`).

## Step 2: Classify Failures

```
viking_results_for_diagnose = []
for query in failed_queries:
    viking_results_for_diagnose.append({
        "query": query["text"],
        "results": [r["uri"] for r in query.get("viking_results", [])]
    })

diagnosis = neuraltree_diagnose(
    failed_queries=[
        {"text": q["text"], "expected_topic": q.get("source", "")}
        for q in failed_queries
    ],
    project_root=".",
    viking_results=viking_results_for_diagnose
)

# In DEGRADED_MODE, reclassify EMBEDDING_GAP -> SYNAPSE_GAP
if DEGRADED_MODE:
    for d in diagnosis["diagnoses"]:
        if d["gap_type"] == "EMBEDDING_GAP":
            d["gap_type"] = "SYNAPSE_GAP"
    diagnosis["gap_counts"]["SYNAPSE_GAP"] += diagnosis["gap_counts"].get("EMBEDDING_GAP", 0)
    diagnosis["gap_counts"]["EMBEDDING_GAP"] = 0
```

**Gap types:**

| Gap Type | Meaning | Fix Cost |
|----------|---------|----------|
| `SYNAPSE_GAP` | Files exist but lack `## Related` wiring | ~5s |
| `FRESHNESS_GAP` | `last_verified` is stale (>30 days) | ~10s |
| `EMBEDDING_GAP` | File exists but Viking hasn't indexed it | ~30s |
| `FOCUS_GAP` | File too large (>500 lines), dilutes search | ~2min |
| `CONTENT_GAP` | No file exists for this topic | ~5min |

## Step 2b: Enrich Dead Neuron Detection

```
dead_result = neuraltree_find_dead(project_root=".")

if dead_result["total_dead"] > 0:
    for dead_file in dead_result["dead_files"][:20]:
        already_diagnosed = any(
            dead_file["path"] in d.get("matching_files", [])
            for d in diagnosis["diagnoses"]
        )
        if not already_diagnosed:
            diagnosis["diagnoses"].append({
                "query": f"[dead neuron] {dead_file['path']}",
                "gap_type": "SYNAPSE_GAP",
                "target_file": dead_file["path"],
                "matching_files": [dead_file["path"]],
                "fix": f"Wire {dead_file['path']} with ## Related links",
                "source": "neuraltree_find_dead"
            })
    diagnosis["gap_counts"]["SYNAPSE_GAP"] = sum(
        1 for d in diagnosis["diagnoses"] if d["gap_type"] == "SYNAPSE_GAP"
    )
    diagnosis["total_failures"] = len(diagnosis["diagnoses"])
```

## Step 3: Enrich with Lessons

```
symptoms = [d["query"] + " " + d["gap_type"] for d in diagnosis["diagnoses"]]
lesson_matches = neuraltree_lesson_match(symptoms=symptoms, project_root=".")

for i, diag in enumerate(diagnosis["diagnoses"]):
    if i < len(lesson_matches.get("matches", [])):
        symptom_result = lesson_matches["matches"][i]
        top_lessons = [l for l in symptom_result["lessons"] if l["score"] > 0.5]
        if top_lessons:
            diag["prior_lesson"] = top_lessons[0]
```

## Step 4: Build Priority Queue

Sort by fix cost (cheapest first): SYNAPSE(1) > FRESHNESS(2) > EMBEDDING(3) > FOCUS(4) > CONTENT(5).

```
PRIORITY_ORDER = {"SYNAPSE_GAP": 1, "FRESHNESS_GAP": 2, "EMBEDDING_GAP": 3, "FOCUS_GAP": 4, "CONTENT_GAP": 5}

for d in diagnosis["diagnoses"]:
    d["target_file"] = d["matching_files"][0] if d.get("matching_files") else None

priority_queue = sorted(
    diagnosis["diagnoses"],
    key=lambda d: (PRIORITY_ORDER.get(d["gap_type"], 99), d.get("precision", 0.0))
)
```

## Step 5: Emit Summary

```
emit(f"Phase 3/5: Diagnosed {diagnosis['total_failures']} failures: ...")
emit(f"Priority queue: {len(priority_queue)} fixes ordered by cost (cheapest first)")
```

**If failures exist** — proceed to AutoLoop (`sections/autoloop.md`).
**If no failures** — skip to Enforce (`sections/enforce.md`).
