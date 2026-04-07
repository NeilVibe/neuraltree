# Verify Phase — Organization Scoring

> Score AFTER understanding. The score validates your work, it doesn't drive it.

**Input:** Sandbox with applied changes.
**Output:** Before/after score comparison. Sandbox approval prompt.

## Step 1: Score from Knowledge Map

```
score_result = neuraltree_score(
    project_root=sandbox_root,
)
```

The score reads the knowledge map and computes:
- **reachability** — % of files reachable in ≤3 hops from entry points
- **connectivity** — % of files with at least 1 edge (not orphaned)
- **cluster_coherence** — % of related file pairs in same directory
- **size_balance** — % of files within 3× median size
- **discoverability** — precision@3 from Viking (computed below)

## Step 1b: Wiki Health Check

Run wiki_lint on the sandbox to catch structural issues the score metrics miss:

```
lint_result = neuraltree_wiki_lint(project_root=sandbox_root)

if lint_result.get("broken_links"):
    emit(f"  WARNING: {len(lint_result['broken_links'])} broken links found")
if lint_result.get("orphan_pages"):
    emit(f"  INFO: {len(lint_result['orphan_pages'])} orphan pages")

health_score = lint_result.get("health_score", 0)
emit(f"  Wiki health: {health_score}/100")
```

If broken links > 0, flag the sandbox changes as needing review before approval.

## Step 2: Compute Discoverability (if Viking available)

```
if not DEGRADED_MODE:
    queries = neuraltree_generate_queries(project_root=sandbox_root)
    precision_result = neuraltree_precision(
        queries=queries["queries"],
        project_root=sandbox_root,
    )
    # Claude judges relevance
    discoverability = judge_precision(precision_result)
    final_score = score_result["flow_score_partial"] + (discoverability * 0.10)
else:
    final_score = score_result["flow_score_partial"]
```

## Step 3: Compare Before/After

Load baseline from `.neuraltree/state.json` (or use 0 if bootstrap):

```
before = load_state().get("flow_score", 0)
after = final_score
delta = after - before

emit(f"Phase 5/5: Score {before:.2f} → {after:.2f} ({delta:+.2f})")
```

## Step 4: Sandbox Approval

```
diff = neuraltree_sandbox_diff(project_root=".")
emit(f"Changes: {diff['total_changes']} files modified")

if delta > 0:
    emit("Score improved. Apply changes? (approve / reject)")
else:
    emit("WARNING: Score did not improve. Apply anyway? (approve / reject)")

response = wait_for_user_input()
if "approve" in response.lower():
    neuraltree_sandbox_apply(project_root=".")
    emit("Changes applied.")

    state = {
        "timestamp": now_iso8601(),
        "flow_score": final_score,
        "metrics": score_result["metrics"],
        "mode": mode,
        "actions_applied": len(approved_actions),
    }
    write_file(".neuraltree/state.json", json.dumps(state, indent=2))

if "reject" in response.lower() or delta <= 0:
    neuraltree_lesson_add(
        lesson_text=f"## {mode} run failed (delta={delta:+.3f})\n"
                    f"- Actions attempted: {len(approved_actions)}\n"
                    f"- Score before: {before:.3f}, after: {after:.3f}\n"
                    f"- Reason: {'user rejected' if 'reject' in response.lower() else 'score decreased'}",
        domain="autoloop",
        project_root=".",
    )
    emit("Lesson recorded for future runs.")

neuraltree_sandbox_destroy(project_root=".")
```

**Proceed to Report (read `sections/report.md`).**
