# Benchmark Protocol

> Measure before you fix. The Flow Score is the single number that tells you whether information is flowing or stuck.

The Benchmark Protocol indexes project content into Viking, generates test queries, searches Viking for answers, judges relevance with LLM, computes structural metrics, and assembles a composite **Flow Score** (0.0-1.0). Every other section depends on this number.

## Step 0: Pre-Index into Viking

**Always run this step** (bootstrap, critical, health-check, maintenance — all modes).
Index ALL knowledge files into Viking BEFORE generating queries. Without this, every query returns EMBEDDING_GAP because Viking has nothing to search.

```
scan_result = neuraltree_scan(path=".", max_files=10000)

# Collect all knowledge files: .md files + key config files
knowledge_files = [
    f for f in scan_result["files"]
    if f.endswith(".md") and not f.startswith(".pytest_cache/")
]

# Also include CLAUDE.md, README.md, and any .json/.yaml config at root level
for f in scan_result["files"]:
    if f in ("CLAUDE.md", "README.md", "pyproject.toml") and f not in knowledge_files:
        knowledge_files.append(f)

if knowledge_files and not DEGRADED_MODE:
    index_result = neuraltree_viking_index(
        file_paths=knowledge_files,
        project_root="."
    )
    emit(f"Phase 2/5: Pre-indexed {index_result['indexed']} files into Viking ({index_result['failed']} failed)")
else:
    emit("Phase 2/5: Skipping Viking pre-index (DEGRADED_MODE or no files)")
```

**Skip only in spot-check mode** — Viking already has content from prior runs.

## Step 1: Generate Queries

Generate test queries that probe the project's information structure. These queries simulate what an agent would actually ask during a working session.

**Step 1a: MCP tool generates mechanical queries** from CLAUDE.md tables, headings, bold terms, MEMORY.md links, _INDEX.md entries, README.md headings, git log subjects, and lesson symptoms.

```
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

**Step 1b: Claude supplements with understanding-based queries.** Read CLAUDE.md and README.md, then generate 5-10 additional queries that test REAL information retrieval — questions an agent would actually ask while working on this project. These should cover:

- Architecture decisions ("Where is the validation layer defined?")
- Cross-cutting concerns ("How do tools register with the server?")
- Debugging scenarios ("What happens when Viking is unavailable?")
- Integration points ("How does the skill communicate with the MCP server?")

Append these to `queries` with `source: "claude_intelligence"`.

Emit: `Phase 2/5: Generating test queries... {len(queries)} queries from {result["sources"]} sources + Claude intelligence`

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

## Step 2: Precision@3 (Viking Search + Claude Judges)

Call `neuraltree_precision` to search Viking and retrieve content. Then **Claude judges relevance** — no external LLM needed.

**Step 2a: Search Viking**
```
precision_result = neuraltree_precision(
    queries=queries,
    project_root="."
)
```

Returns per-query results with `verdict: "PENDING"` and `content` previews.

**Step 2b: Claude judges relevance using sequential thinking.**

Use `sequential_thinking` MCP to reason through judgments systematically:

```
sequential_thinking(
    thought: "Judging Precision@3 for {len(queries)} queries. For each query,
    I'll evaluate the top 3 Viking results: does the content DIRECTLY help
    answer the query? YES if the content contains useful information for
    answering. NO if unrelated or only tangential.",
    thoughtNumber: 1,
    totalThoughts: 3,
    nextThoughtNeeded: true
)
```

For each query, examine each result's `content` field and assign:
- **YES** — the content directly helps answer the query
- **NO** — the content is unrelated or only tangentially mentions the topic

```
sequential_thinking(
    thought: "[Per-query judgments with reasoning for each YES/NO decision]",
    thoughtNumber: 2,
    totalThoughts: 3,
    nextThoughtNeeded: true
)
```

Compute precision per query and aggregate:
```
per_query_precision = yes_count / min(total_results, limit)
status = "PASS" if per_query_precision >= 0.67 else "FAIL"
precision_at_3 = sum(per_query_precision) / len(queries)
```

```
sequential_thinking(
    thought: "Precision@3 = {precision_at_3}. {passed} PASS, {failed} FAIL.
    Key failures: [list top 3 failed queries and why]",
    thoughtNumber: 3,
    totalThoughts: 3,
    nextThoughtNeeded: false
)
```

**Step 2c: Store results** for later use by `neuraltree_diagnose()`:
```
for i, qr in enumerate(precision_result["query_results"]):
    queries[i]["precision"] = computed_precision[i]
    queries[i]["viking_results"] = [
        {"uri": j["uri"]} for j in qr["judgments"]
    ]
    queries[i]["judgments"] = qr["judgments"]  # with verdicts filled in by Claude
```

**If `DEGRADED_MODE` is true**: Set `precision_at_3 = None`. Continue to Step 4.

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
