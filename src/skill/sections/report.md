# Execution Report

> Show the full picture — before, after, and what changed.

## Report Format

```
elapsed = f"{(time.time() - start_time):.0f}s"  # start_time set during activation

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

METRICS
  ┌───────────────────┬────────┬────────┬────────┐
  │ Metric            │ Before │ After  │ Delta  │
  ├───────────────────┼────────┼────────┼────────┤
  │ reachability      │ {b_re} │ {a_re} │ {d_re} │
  │ connectivity      │ {b_co} │ {a_co} │ {d_co} │
  │ cluster_coherence │ {b_cc} │ {a_cc} │ {d_cc} │
  │ size_balance      │ {b_sb} │ {a_sb} │ {d_sb} │
  │ discoverability   │ {b_di} │ {a_di} │ {d_di} │
  └───────────────────┴────────┴────────┴────────┘

KNOWLEDGE MAP SAVED: .neuraltree/knowledge_map.json
STATE SAVED: .neuraltree/state.json
```

## Release Lock

```
release_lock()
emit("Lock released. Run complete.")
```
