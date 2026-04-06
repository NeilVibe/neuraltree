# Execution Report

> Show the full picture — before, after, and what changed.

## Report Format

```
/neuraltree — Execution Report
═══════════════════════════════

Project: {project_name}
Mode: {mode} | Agents: {agent_count} | Duration: {elapsed}

KNOWLEDGE MAP
  Files explored:  {total_files}
  Edges found:     {total_edges} (reference: {ref}, semantic: {sem}, co-located: {co})
  Clusters:        {total_clusters}
  Issues found:    {total_issues}

ANALYSIS
  High severity:   {high}
  Medium severity:  {medium}
  Low severity:     {low}

ACTIONS
  Approved:        {approved}
  Rejected:        {rejected}
  Applied:         {applied}

SCORE
  Before:          {before:.2f}
  After:           {after:.2f}
  Delta:           {delta:+.2f} ({pct:+.0f}%)
  Mode:            {adaptive|static}

METRICS (adaptive thresholds)
  ┌──────────────────┬────────┬────────┬────────┐
  │ Metric           │ Before │ After  │ Delta  │
  ├──────────────────┼────────┼────────┼────────┤
  │ hop_efficiency   │ {b_he} │ {a_he} │ {d_he} │
  │ synapse_coverage │ {b_sc} │ {a_sc} │ {d_sc} │
  │ dead_neuron_ratio│ {b_dn} │ {a_dn} │ {d_dn} │
  │ freshness        │ {b_fr} │ {a_fr} │ {d_fr} │
  │ trunk_pressure   │ {b_tp} │ {a_tp} │ {d_tp} │
  │ precision_at_3   │ {b_p3} │ {a_p3} │ {d_p3} │
  └──────────────────┴────────┴────────┴────────┘

KNOWLEDGE MAP SAVED: .neuraltree/knowledge_map.json
STATE SAVED: .neuraltree/state.json
```

## Release Lock

```
release_lock()
emit("Lock released. Run complete.")
```
