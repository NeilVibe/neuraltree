# Execution Report

> One glance tells the user everything: what improved, what's pending, and when to run again.

**Input:** `baseline`, `autoloop_state`, `current_flow_score`, `latest_metrics`, `exit_reason`, `DEGRADED_MODE`, `project_name`, `mode`, `run_start_time`.

## Full Report Format

Emit after every `bootstrap`, `critical`, `maintenance`, or `health-check` run:

```
===============================================
  NeuralTree Report — {project_name}
  Mode: {mode} | Duration: {elapsed_seconds}s
===============================================

Flow Score: {before} -> {after} ({delta:+.2f})

| Metric              | Before | After  | Delta  |
|---------------------|--------|--------|--------|
| Hop Efficiency      | 0.45   | 0.88   | +0.43  |
| Precision@3         | 0.33   | 0.87   | +0.54  |
| Synapse Coverage    | 0.61   | 0.97   | +0.36  |
| Dead Neuron Ratio   | 0.70   | 1.00   | +0.30  |
| Freshness           | 0.80   | 0.95   | +0.15  |
| Trunk Pressure      | 0.80   | 1.00   | +0.20  |
```

**In DEGRADED_MODE:** Precision@3 shows "N/A", add warning banner above table.

## Action Sections

### SAFE ACTIONS (executed — non-destructive)

```
if autoloop_state["kept"]:
    emit("SAFE ACTIONS (executed):")
    for k in autoloop_state["kept"]:
        emit(f"  + {k['strategy']} — delta {k['actual_delta']:+.3f}")
```

### PENDING ACTIONS (require approval — destructive)

Gathered from HOLD items (CONTENT_GAP, FOCUS_GAP):

```
pending_actions = []
for held in autoloop_state["held"]:
    if held.get("gap_type") == "CONTENT_GAP":
        pending_actions.append({"type": "CREATE", "target": held.get("suggested_path"), "reason": held["reason"]})
    elif held.get("gap_type") == "FOCUS_GAP":
        pending_actions.append({"type": "SPLIT", "target": held.get("target"),
            "reason": held["reason"], "split_plan": held.get("split_plan", [])})

if pending_actions:
    emit("PENDING ACTIONS (require approval):")
    for i, pa in enumerate(pending_actions, 1):
        if pa["type"] == "DELETE":
            emit(f"  {i}. DELETE {pa['target']} — {pa['reason']}")
        elif pa["type"] == "ARCHIVE":
            emit(f"  {i}. ARCHIVE {pa['target']} -> {pa['destination']} — {pa['reason']}")
        elif pa["type"] == "CREATE":
            emit(f"  {i}. CREATE {pa['target']} — {pa['reason']}")
        elif pa["type"] == "SPLIT":
            emit(f"  {i}. SPLIT {pa['target']} -> {len(pa.get('split_plan', []))} files — {pa['reason']}")
```

## Footer

```
emit(f"AutoLoop: {autoloop_state['iteration']} iterations, "
     f"{len(autoloop_state['kept'])} KEEP / "
     f"{len(autoloop_state['discarded'])} DISCARD / "
     f"{len(autoloop_state['held'])} HOLD")

emit(f"Calibration accuracy: {read_calibration_accuracy('.neuraltree/calibration.json'):.0%}")
emit(f"Exit reason: {exit_reason}")

if current_flow_score >= 0.90: next_eta = "7 days (weekly spot-check)"
elif current_flow_score >= 0.75: next_eta = "3 days (health-check)"
else: next_eta = "1 day (maintenance)"
emit(f"Next run ETA: {next_eta}")
```

## Handling Pending Actions

If `pending_actions` is non-empty:

```
emit("Which actions? (all / none / pick by number, e.g. '1,3')")
user_response = wait_for_user_input()
```

### Processing responses:

**"all"** — Execute all, re-score, update state.
**"1,3"** — Execute selected, re-score, update state.
**"none"** — Skip. Pending items carry to next run.

### Per-action execution:

**DELETE:** Call `neuraltree_trace()` first. If alive (has references), skip with warning. If dead, delete.

**ARCHIVE:** Call `neuraltree_plan_move()` to compute reference rewrites, then move + apply rewrites.

**SPLIT:** Use `split_plan` from diagnose. Write each section to its proposed file, generate index, re-index in Viking, check for references to original before removing it.

**CREATE:** Ask user for content. Write with frontmatter, wire with `neuraltree_wire()`, index with `neuraltree_viking_index()`.

## Spot-Check Short Form

When mode is `spot-check` and score is healthy:

```
NeuralTree spot-check — {project_name}
Score: {score} ({status}) | {query_count} queries | 0 failures
Last full run: {days} days ago | Next: {date}
```

**Report complete. Lock released. NeuralTree run finished.**
