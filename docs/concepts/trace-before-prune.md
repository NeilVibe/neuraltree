---
project: neuraltree
type: concept
---

# Trace Before Prune

**Investigate every connection before recommending deletion.**

When NeuralTree identifies a file as potentially dead or orphaned, it must trace all references to that file before suggesting removal. This prevents breaking hidden dependencies.

## The Rule

1. Use `neuraltree_trace` to find all incoming references (who links to this file?)
2. Use `neuraltree_scan` to check the file's outgoing references (what does it link to?)
3. Check if the file is referenced in indexes, CLAUDE.md, README, or config files
4. Only after confirming zero live references → recommend deletion

## Why This Matters

Projects accumulate files that look dead but are referenced by:
- CI/CD workflows (trigger files)
- Import paths in code
- Documentation cross-references
- Config files or scripts

Deleting without tracing causes silent breakage.

## Related

- [Sandbox First](sandbox-first.md) — test deletions in sandbox before applying
- [User Approves Destructive Actions](user-approves-destructive.md) — user confirms all deletions
- [Explore First Pipeline](explore-first-pipeline.md) — tracing happens in the Analyze phase
