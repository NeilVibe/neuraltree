# Analyze Phase — Claude Reasons About the Project

> No formulas. Read the map. Think. Report what's wrong and why.

**Input:** `knowledge_map` from Map phase.
**Output:** `analysis` — issues with Claude's reasoning and proposed fixes.

## Step 1: Load the Knowledge Map

```
km_result = neuraltree_knowledge_map(action="load", project_root=".")
km = km_result["map"]
```

## Step 2: Claude Analyzes the Map

Read the knowledge map and reason about the project's organization.
DO NOT use formulas or thresholds. Instead, THINK about:

**A. Structure Assessment:**
- Are files in logical directories? Do directory names match their contents?
- Is there a clear trunk → branch → leaf hierarchy?
- Are there files that should be in the same folder but aren't?

**B. Relationship Assessment:**
- Are there files that clearly relate but have no `## Related` links?
- Are there dead-end files that nothing references?
- Are there clusters of tightly-related files? Should they be co-located?

**C. Content Assessment:**
- Are any files too large? (relative to the project's own average, not a fixed cutoff)
- Are there duplicate or overlapping files?
- Are there stale files with outdated content?
- Are there files with misleading names?

**D. Navigability Assessment:**
- Can you find any piece of information in 0-2 tool calls from the trunk?
- Are there "dead zones" — areas of the project unreachable from navigation?
- Would an agent new to this project know where to look?

## Step 3: Produce Issue List

For each issue, write:

```
{
  "id": "issue_1",
  "type": "misplaced" | "orphan" | "too_large" | "duplicate" | "stale" |
          "unwired" | "scattered" | "naming" | "dead_zone" | "bloated_trunk",
  "files": ["path1.md", "path2.md"],
  "description": "Human-readable description of what's wrong",
  "reasoning": "Why this matters for information flow",
  "proposed_fix": "What should be done about it",
  "severity": "high" | "medium" | "low",
  "requires_user_approval": true/false,
  "auto_fixable": true/false
}
```

**Severity guide:**
- **high:** Information is unreachable or actively misleading
- **medium:** Information is findable but poorly organized
- **low:** Cosmetic or minor improvement

## Step 4: Merge with Map Issues

Combine Claude's analysis with issues already in the knowledge map.
Deduplicate by file path. Claude's reasoning overrides mechanical detection.

```
analysis = {
    "timestamp": now_iso8601(),
    "total_issues": len(all_issues),
    "by_severity": {"high": N, "medium": N, "low": N},
    "by_type": {...},
    "issues": all_issues,
    "summary": "One paragraph summary of the project's organizational health",
}

high = analysis["by_severity"]["high"]
medium = analysis["by_severity"]["medium"]
low = analysis["by_severity"]["low"]

emit(f"Phase 3/6: Analysis complete — {len(all_issues)} issues ({high} high, {medium} medium, {low} low)")
```

**If no issues found:** Skip to Verify.
**If issues found:** Proceed to Plan (read `sections/plan.md`).
