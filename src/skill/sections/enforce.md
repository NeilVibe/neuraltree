# Enforce Protocol

> Lock in the gains — graduate learnings, re-index, install guardrails, clean up.

**Input:** `autoloop_state`, `baseline`, `current_flow_score`, `latest_metrics`, `exit_reason`, `mode`, `DEGRADED_MODE`.
**Output:** Updated `.neuraltree/state.json`, `.neuraltree/queries.json`, `.neuraltree/history/`, Viking re-indexed.

## Step 1: Graduation Protocol

### 1a. Calibration — already done
`neuraltree_update_calibration()` was called after every AutoLoop iteration.

### 1b. Evolve queries

```
evolved_queries = []
for query in baseline["queries"]:
    query_status = query.get("status", "active")

    # Queries that passed in ALL iterations -> demote to spot-check
    if query.get("precision", 0) >= 0.67 and query_status != "critical":
        query["status"] = "spot-check"

    # Queries that caught real issues -> promote to critical
    query_source = query.get("source", "")
    matching_kept = any(
        query_source in (k.get("files_changed", []) or [])
        or query_source in (k.get("new_files", []) or [])
        or query_source in (k.get("wired_files", []) or [])
        for k in autoloop_state["kept"]
    )
    matching_held = any(
        query_source in str(h.get("failure", {}).get("matching_files", []))
        for h in autoloop_state["held"]
    )
    if matching_kept or matching_held:
        query["status"] = "critical"

    evolved_queries.append({
        "text": query["text"],
        "source": query.get("source", ""),
        "status": query["status"],
        "last_precision": query.get("precision"),
        "last_run": now_iso8601()
    })
```

### 1c. Fresh queries from git activity

```
recent_files = git_log_modified_files(since=state.get("last_run", "7 days ago"))
knowledge_files = [f for f in recent_files if is_knowledge_file(f)]

if knowledge_files:
    fresh_result = neuraltree_generate_queries(
        project_root=".", claude_md_path="CLAUDE.md", memory_md_path="memory/MEMORY.md",
        index_paths=[f for f in knowledge_files if f.endswith("_INDEX.md")],
        git_log_lines=50, indexed_doc_count=len(knowledge_files)
    )
    for q in fresh_result["queries"]:
        if not any(eq["text"] == q["text"] for eq in evolved_queries):
            evolved_queries.append({
                "text": q["text"], "source": q.get("source", ""),
                "status": "active", "last_precision": None, "last_run": None
            })
```

### 1d. Compress to history

Write a single-line summary to `.neuraltree/history/YYYY-MM-DD.json`:

```json
{
    "date": "2026-04-06",
    "flow_score_before": 0.58,
    "flow_score_after": 0.91,
    "delta": 0.33,
    "iterations": 4,
    "kept": 3, "discarded": 0, "held": 1,
    "fixes": ["wire: 2", "index: 1"],
    "exit_reason": "healthy",
    "calibration_accuracy": 0.87,
    "duration_seconds": 480
}
```

### 1e. Update state.json

```json
{
    "flow_score": 0.91,
    "last_run": "2026-04-06T14:30:00Z",
    "mode": "bootstrap",
    "run_count": 1,
    "calibration_accuracy": 0.87,
    "metrics": { ... }
}
```

### 1f. Save evolved queries

Write `evolved_queries` to `.neuraltree/queries.json`.

### 1g. Clean .tmp/

Delete `.neuraltree/.tmp/iteration_*.json` and `predictions_buffer.json`. Retain `.tmp/backup/` until next run.

## Step 2: Re-index Viking

```
modified_files = set()
for k in autoloop_state["kept"]:
    modified_files.update(k.get("new_files", []))
    modified_files.update(k.get("wired_files", []))
    modified_files.update(k.get("index_files", []))
    modified_files.update(k.get("files_changed", []) if isinstance(k.get("files_changed"), list) else [])

emit(f"Phase 5/5: Re-indexing {len(modified_files)} files in Viking...")

index_result = neuraltree_viking_index(
    file_paths=list(modified_files),
    project_root="."
)
emit(f"Phase 5/5: Indexed {index_result['indexed']} files, {index_result['failed']} failed")
```

## Step 2b: Regenerate Index Files

```
affected_dirs = set()
for k in autoloop_state["kept"]:
    for f in k.get("new_files", []) + k.get("wired_files", []) + k.get("index_files", []):
        d = os.path.dirname(f)
        if d:
            affected_dirs.add(d)

for dir_path in affected_dirs:
    if os.path.isdir(dir_path):
        index_result = neuraltree_generate_index(directory=dir_path, project_root=".")
        if index_result.get("file_count", 0) > 0:
            index_path = os.path.join(dir_path, "_INDEX.md")
            write_file(index_path, index_result["index_content"])
            if not DEGRADED_MODE:
                neuraltree_viking_index(file_paths=[index_path], project_root=".")
```

## Step 3: Install Organization Rule

Create `.claude/rules/neuraltree.md` in the target project (first run only).

Contains: session start protocol, file standards (20-80 lines per leaf, frontmatter, ## Related, ## Docs), weekly hygiene checklist.

## Step 4: Cleanup

1. Remove `.neuraltree/.lock`
2. Remove `.tmp/` working files (preserve backup)
3. Verify `state.json` and `history/` were written

**Proceed to Report (read `sections/report.md`).**
