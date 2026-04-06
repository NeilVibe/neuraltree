# Plan Phase — Reorganization Proposals

> Show the user what you'd change and why. They decide.

**Input:** `analysis` from Analyze phase.
**Output:** `approved_actions` list.

## Step 1: Convert Issues to Actions

For each issue, generate a concrete action:

| Issue Type | Action |
|-----------|--------|
| `unwired` | `neuraltree_wire()` the file, append `## Related` |
| `orphan` | Wire it OR mark for deletion (user decides) |
| `too_large` | `neuraltree_plan_split()` or `neuraltree_shrink_and_wire()` |
| `duplicate` | Merge files, redirect references |
| `stale` | Update `last_verified` or flag for review |
| `misplaced` | `neuraltree_plan_move()` to correct directory |
| `scattered` | Move cluster members to shared directory |
| `naming` | Rename file/directory |
| `dead_zone` | Add index file or wire into trunk |
| `bloated_trunk` | Extract sections to branch files |

## Step 2: Trace Before Destructive Actions

For every move, delete, or split — call `neuraltree_trace()` first:

```
for action in actions:
    if action["type"] in ("move", "delete", "split", "merge"):
        for file in action["files"]:
            trace = neuraltree_trace(target=file, project_root=".")
            action["trace"] = {
                "referenced_by": trace["referenced_by"],
                "references_to": trace["references_to"],
                "is_alive": trace["is_alive"],
            }
```

## Step 3: Present to User

Group actions by type. Show auto-fixable actions first, then approval-required:

```
AUTO-FIX (will apply automatically):
  1. Wire CLAUDE.md with ## Related → [README.md, memory/MEMORY.md]
  2. Wire docs/spec.md with ## Related → [CLAUDE.md]
  3. Add last_verified frontmatter to 5 files

APPROVAL REQUIRED:
  4. [MOVE] memory/old_notes.md → archive/old_notes.md
     Reason: File is stale (last verified 2025-01), only referenced by memory/MEMORY.md
     Impact: Update 1 reference in MEMORY.md
     Approve? (y/n)

  5. [SPLIT] docs/MEGA_GUIDE.md (800 lines) → 4 focused files
     Reason: 3x project average size, contains 4 distinct topics
     Impact: Create 4 new files + index, update 2 references
     Approve? (y/n)
```

## Step 4: Collect Approvals

```
approved_actions = []
for action in auto_fixable:
    approved_actions.append(action)

for action in needs_approval:
    emit(action["description"])
    response = wait_for_user_input()
    if "y" in response.lower():
        approved_actions.append(action)
    else:
        action["status"] = "rejected"

emit(f"Phase 4/6: {len(approved_actions)} actions approved, {rejected} rejected")
```

**Proceed to Execute (read `sections/execute.md`).**
