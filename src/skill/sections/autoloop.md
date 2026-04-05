# Karpathy AutoLoop

> Analyze. Propose. Execute. Measure. Decide. Learn. Repeat.

**Input:** `priority_queue`, `diagnosis`, `baseline`, `DEGRADED_MODE`, `mode`.
**Output:** `autoloop_state` (kept/discarded/held lists), `current_flow_score`, `latest_metrics`, `exit_reason`.

Claude is the brain. MCP tools are the measurement layer. Claude proposes, tools measure, numbers decide.

## Sandbox Mode

**Mandatory for:** bootstrap and critical mode (flow_score < 0.60).

```
if mode in ("bootstrap", "critical"):
    sandbox = neuraltree_sandbox_create(project_root=".")
    sandbox_root = sandbox["sandbox_path"]
else:
    sandbox_root = "."
```

## Initialize

```
autoloop_state = {
    "iteration": 0, "max_iterations": 8,
    "score_history": [baseline["flow_score"]],
    "kept": [], "discarded": [], "held": [],
    "convergence_counter": 0
}
latest_metrics = dict(baseline["metrics"])
current_flow_score = baseline["flow_score"]

# Route CONTENT_GAP to HOLD — user must provide content
for d in diagnosis["diagnoses"]:
    if d["gap_type"] == "CONTENT_GAP":
        autoloop_state["held"].append({
            "failure": d, "gap_type": "CONTENT_GAP",
            "target": d.get("matching_files", [None])[0] if d.get("matching_files") else d.get("query", "unknown"),
            "reason": "Content does not exist — user must provide",
            "suggested_path": d.get("fix", "TBD")
        })
```

## Per-Iteration Steps

### Step 1: Analyze and Propose

Claude reads the current state and proposes ONE coherent action. Not from a fixed list — from understanding the project.

**What to consider for each file:**
- Is it useful? Stale? Duplicate?
- Too large? Shrink or split?
- Sacred file? (some files must stay as-is)
- What's the wiring situation? Split + wire = one action.
- Would Viking indexing help more than restructuring?

```
proposed_action = {
    "description": "...",
    "files_affected": [...],
    "expected_impact": "...",
}
emit(f"Iteration {autoloop_state['iteration']+1}: {proposed_action['description']}")
```

### Step 2: Backup

```
neuraltree_backup(files=proposed_action["files_affected"], project_root=sandbox_root)
```

### Step 3: Execute

Claude performs the proposed action. MCP tools as helpers:
- `neuraltree_wire()` for `## Related` suggestions
- `neuraltree_plan_split()` for split proposals
- `neuraltree_plan_move()` for safe file moves
- `neuraltree_generate_index()` for directory indexes
- `neuraltree_find_dead()` for identifying orphans
- `neuraltree_viking_index()` for Viking indexing (if not DEGRADED_MODE)

**Key rule:** Every file created or modified must be wired into the tree. No orphan creation.

### Step 4: Measure

```
new_score = neuraltree_score(project_root=sandbox_root)
new_flow = new_score["flow_score_partial"]

if not DEGRADED_MODE:
    new_precision = ...  # re-run neuraltree_precision on affected queries
    new_flow = new_score["flow_score_partial"] + (new_precision * 0.25)

actual_delta = new_flow - current_flow_score
emit(f"  Score: {current_flow_score:.3f} -> {new_flow:.3f} ({actual_delta:+.3f})")
```

### Step 5: Decide — KEEP or DISCARD

```
if actual_delta > 0:
    current_flow_score = new_flow
    latest_metrics = new_score["metrics"]
    autoloop_state["kept"].append({
        "strategy": proposed_action["description"],
        "actual_delta": actual_delta,
        "files_changed": proposed_action["files_affected"],
        "new_files": [...], "wired_files": [...]
    })
    emit(f"  KEEP — {proposed_action['description']}")
else:
    neuraltree_restore(files=proposed_action["files_affected"], project_root=sandbox_root)
    autoloop_state["discarded"].append({
        "strategy": proposed_action["description"],
        "actual_delta": actual_delta,
    })
    emit(f"  DISCARD — {proposed_action['description']} (delta {actual_delta:+.3f})")
```

### Step 6: Learn

```
neuraltree_update_calibration(predicted_delta=0.0, actual_delta=actual_delta, project_root=".")

neuraltree_lesson_add(
    domain="autoloop",
    lesson={
        "symptom": proposed_action["description"],
        "root_cause": f"delta {actual_delta:+.3f}",
        "fix": f"{'KEEP' if actual_delta > 0 else 'DISCARD'}",
        "key_file": proposed_action["files_affected"][0] if proposed_action["files_affected"] else "batch"
    },
    project_root="."
)
```

### Step 7: Check Exit Conditions

```
autoloop_state["iteration"] += 1
autoloop_state["score_history"].append(current_flow_score)

# Convergence detection
if len(autoloop_state["score_history"]) >= 2:
    delta = abs(autoloop_state["score_history"][-1] - autoloop_state["score_history"][-2])
    if delta < 0.01:
        autoloop_state["convergence_counter"] += 1
    else:
        autoloop_state["convergence_counter"] = 0

# Exit conditions
if current_flow_score > 0.85: exit_reason = "Healthy"
elif autoloop_state["convergence_counter"] >= 2: exit_reason = "Converged"
elif autoloop_state["iteration"] >= autoloop_state["max_iterations"]: exit_reason = "Hard cap"
```

## Sandbox Finalization

After convergence (bootstrap/critical modes only):

```
if sandbox_root != ".":
    diff = neuraltree_sandbox_diff(project_root=".")
    emit(f"Sandbox changes: {diff['total_changes']} total")
    emit("Approve sandbox changes? (approve / reject)")
    user_response = wait_for_user_input()
    if "approve" in user_response.lower():
        neuraltree_sandbox_apply(files=[f["path"] for f in diff["modified"] + diff["added"]], project_root=".")
        emit("Sandbox changes applied to real project.")
    neuraltree_sandbox_destroy(project_root=".")
```

**Proceed to Enforce (read `sections/enforce.md`).**
