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

## Step 2: Usefulness Gate

Before tracing or presenting, review each action and ask:

**"If I don't do this, what breaks?"**

| Answer | Decision |
|--------|----------|
| Someone can't find critical information | KEEP — high value |
| An agent would be misled by stale/broken content | KEEP — correctness |
| Knowledge is buried where no one will look | KEEP — discoverability |
| A metric improves but nothing practical changes | DROP — busywork |
| The file gets "nicer" but no one was struggling | DROP — cosmetic |

Drop any action that only serves metric compliance. The pipeline exists
to improve information FLOW, not to achieve scores.

## Step 3: Trace Before Destructive Actions

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

## Step 4: Present to User

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

## Step 5: Collect Approvals

```
approved_actions = []
for action in auto_fixable:
    approved_actions.append(action)

rejected = 0
for action in needs_approval:
    emit(action["description"])
    response = wait_for_user_input()
    if "y" in response.lower():
        approved_actions.append(action)
    else:
        rejected += 1
        action["status"] = "rejected"

emit(f"Phase 5/7: {len(approved_actions)} actions approved, {rejected} rejected")
```

**Proceed to Execute (read `sections/execute.md`).**
