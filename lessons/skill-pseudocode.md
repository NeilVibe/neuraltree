---
name: Skill-Pseudocode Lessons
description: Past skill-pseudocode issues
type: reference
last_verified: 2026-04-08
---

## Skill pseudocode in index.md and explore.md used wrong wiki_lint output keys (orphans, stale_files, source) causing silent empty results (2026-04-08)
- **Symptom:** Skill pseudocode in index.md and explore.md used wrong wiki_lint output keys (orphans, stale_files, source) causing silent empty results
- **Root cause:** wiki_lint tool was renamed from orphans to orphan_pages, stale_files to stale_pages, broken source to file at some point, but skill section files were never updated to match. .get() with default [] silently returns empty instead of erroring.
- **Chain:** wiki_lint key rename → skill sections not updated → .get('orphans', []) always [] → problem-dir targeting broken → Phase 2 explores nothing → issues missed
- **Fix:** Updated all key references in index.md and explore.md: orphans→orphan_pages, stale_files→stale_pages, source→file, stale_days→max_age_days. Rule: when renaming tool output keys, grep all section files for the old key names.
- **Key file:** `src/skill/sections/index.md`
- **Commit:** 055585e69b3f

## Docs
- `src/skill/sections/index.md` — implementation target
