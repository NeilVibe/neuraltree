---
project: neuraltree
type: concept
---

# User Approves Destructive Actions

**Autoloop thinks, user decides on deletes and moves.**

NeuralTree never applies destructive changes (file deletions, moves, renames) without explicit user approval. The AI proposes, the human disposes.

## What Counts as Destructive

- Deleting files (even if `neuraltree_find_dead` flags them)
- Moving files to different directories
- Renaming files
- Splitting files into multiple parts
- Applying sandbox changes to the real project (KEEP decision)

## How Approval Works

1. NeuralTree proposes changes via `neuraltree_plan_move` / `neuraltree_plan_split`
2. Changes are executed in [sandbox](sandbox-first.md) only
3. `neuraltree_sandbox_diff` shows the full diff
4. User reviews and explicitly approves `neuraltree_sandbox_apply`

## Why Not Fully Autonomous

- AI can misjudge file importance (CI trigger files look like dead files)
- [Trace Before Prune](trace-before-prune.md) catches most issues, but not all
- Destructive actions are irreversible in the real project
- Users know context that the AI doesn't (planned features, external dependencies)

## Related

- [Sandbox First](sandbox-first.md) — destructive actions only in sandbox
- [Trace Before Prune](trace-before-prune.md) — investigate before proposing deletion
- [Autoloop](autoloop.md) — autonomous but still requires user approval for KEEP
