---
project: neuraltree
type: concept
---

# Sandbox First

**Never modify the real project directly. Always work in a sandbox.**

NeuralTree's reorganization pipeline operates in an isolated git worktree (sandbox). Changes are proposed, reviewed, and only applied after explicit user approval.

## How It Works

1. `neuraltree_sandbox_create` — creates an isolated git worktree copy
2. All moves, splits, rewrites happen inside the sandbox
3. `neuraltree_sandbox_diff` — shows what changed vs the real project
4. `neuraltree_sandbox_apply` — merges approved changes back (requires user confirmation)
5. `neuraltree_sandbox_destroy` — cleans up the worktree

## Why Sandbox

- Reorganization is destructive (moves, deletes, rewrites)
- Git worktrees provide real isolation without copying
- Users can review the full diff before any changes land
- Failed experiments are discarded cleanly

## Related

- [User Approves Destructive Actions](user-approves-destructive.md)
- [Explore First Pipeline](explore-first-pipeline.md) — sandbox is used in the Execute phase
- [Autoloop](autoloop.md) — autoloop runs entirely within sandbox
