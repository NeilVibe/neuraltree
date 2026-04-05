# Benchmark Protocol

> Measure before you fix. The Flow Score is the single number that tells you whether information is flowing or stuck.

The Benchmark Protocol generates test queries, searches Viking for answers, judges relevance with LLM, computes structural metrics, and assembles a composite **Flow Score** (0.0-1.0). Every other section depends on this number.

## Step 1: Generate Queries

Generate test queries that probe the project's information structure. These queries simulate what an agent would actually ask during a working session.

```
scan_result = neuraltree_scan(path=".", max_files=10000)
index_paths = [f for f in scan_result["files"] if os.path.basename(f) == "_INDEX.md"]

result = neuraltree_generate_queries(
    project_root=".",
    claude_md_path="CLAUDE.md",
    memory_md_path="memory/MEMORY.md",
    index_paths=index_paths,
    git_log_lines=100,
    indexed_doc_count=scan_result["total_count"]
)
queries = result["queries"]
```

Emit: `Phase 2/5: Generating test queries... {result["total"]} queries from {result["sources"]} sources`

**Spot-check mode filtering:** If mode is `spot-check`, load `.neuraltree/queries.json` and filter to only queries tagged `status: "critical"`.

```
if mode == "spot-check":
    if os.path.exists(".neuraltree/queries.json"):
        with open(".neuraltree/queries.json") as f:
            cached = json.load(f)
        queries = [q for q in cached if q.get("status") == "critical"]
    else:
        emit("queries.json not found — running full benchmark instead of spot-check")
```

## Step 2: Precision@3 (Viking Search + LLM Judge)

Call `neuraltree_precision` — this single tool handles Viking search AND LLM-as-Judge internally.

```
precision_result = neuraltree_precision(
    queries=queries,
    project_root="."
)

precision_at_3 = precision_result["precision_at_3"]  # float or None if degraded
```

**Store per-query results** for later use by `neuraltree_diagnose()`:
```
for i, qr in enumerate(precision_result["query_results"]):
    queries[i]["precision"] = qr["precision"]
    queries[i]["viking_results"] = [
        {"uri": j["uri"]} for j in qr["judgments"]
    ]
    queries[i]["judgments"] = qr["judgments"]
```

**If `DEGRADED_MODE` is true** (or `precision_at_3` is null): Set `precision_at_3 = None`. Continue to Step 4.

## Step 3: Structural Metrics

```
score_result = neuraltree_score(project_root=".")
```

Returns: `hop_efficiency`, `synapse_coverage`, `dead_neuron_ratio`, `freshness`, `trunk_pressure`, `flow_score_partial`, `details`, `warnings`.

## Step 4: Assemble Flow Score

**Full mode (Viking available):**

```
final_flow_score = score_result["flow_score_partial"] + (precision_at_3 * 0.25)
```

**Weights:** hop_efficiency (0.25), precision_at_3 (0.25), synapse_coverage (0.20), dead_neuron_ratio (0.15), freshness (0.10), trunk_pressure (0.05).

**Degraded mode (no Viking):**

```
structure_reachability = (hop_efficiency + synapse_coverage) / 2
Degraded Flow Score = structure_reachability * 0.45 + dead_neuron_ratio * 0.25 + freshness * 0.20 + trunk_pressure * 0.10
```

Degraded Flow Score is **capped at 0.75**.

## Step 5: Record Baseline

```
baseline = {
    "timestamp": now_iso8601(),
    "mode": mode,
    "flow_score": final_flow_score,
    "precision_at_3": precision_at_3,
    "metrics": {
        "hop_efficiency": score_result["metrics"]["hop_efficiency"],
        "synapse_coverage": score_result["metrics"]["synapse_coverage"],
        "dead_neuron_ratio": score_result["metrics"]["dead_neuron_ratio"],
        "freshness": score_result["metrics"]["freshness"],
        "trunk_pressure": score_result["metrics"]["trunk_pressure"]
    },
    "flow_score_partial": score_result["flow_score_partial"],
    "query_count": len(queries),
    "queries": queries,
    "warnings": score_result["warnings"]
}
```

Emit: `Phase 2/5: Baseline Flow Score: {final_flow_score:.2f} ({status})`

Status: EXCELLENT (>=0.90), HEALTHY (0.75-0.89), DEGRADED (0.60-0.74), CRITICAL (<0.60).

## Step 6: Route by Score

```
if mode == "spot-check" and final_flow_score > 0.90:
    emit(f"NeuralTree spot-check — {project_name}")
    emit(f"Score: {final_flow_score:.2f} (Excellent) | {len(queries)} queries | 0 failures")
    release_lock()
    stop()
elif mode == "spot-check" and final_flow_score <= 0.90:
    emit("WARNING: Flow Score dropped. Upgrading to maintenance mode.")
    mode = "maintenance"
```

**Proceed to Diagnose (read `sections/diagnose.md`).**
