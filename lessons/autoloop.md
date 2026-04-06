---
name: Autoloop Lessons
description: Past autoloop issues
type: reference
last_verified: 2026-04-05
---

## synapse_coverage=0, all files unwired (2026-04-05)
- **Symptom:** synapse_coverage=0, all files unwired
- **Root cause:** Fresh project, no ## Related sections
- **Fix:** KEEP: Wire all .md files with neuraltree_wire suggestions, delta +0.304
- **Key file:** `CLAUDE.md`
- **Commit:** 61961cc553ab


## freshness=0, no last_verified in any file (2026-04-05)
- **Symptom:** freshness=0, no last_verified in any file
- **Root cause:** No frontmatter in project markdown files
- **Fix:** KEEP: Add YAML frontmatter with last_verified to all .md files, delta +0.091
- **Key file:** `CLAUDE.md`
- **Commit:** 61961cc553ab


## FOCUS_GAP 1067-line spec file (2026-04-05)
- **Symptom:** FOCUS_GAP 1067-line spec file
- **Root cause:** Splitting creates many new files without frontmatter, tanks freshness and hop_efficiency
- **Fix:** DISCARD: Raw split without frontmatter+trunk-wiring makes things worse. Must add frontmatter and wire to trunk in same iteration.
- **Key file:** `docs/specs/2026-04-04-neuraltree-skill-design.md`
- **Commit:** 61961cc553ab


## FOCUS_GAP spec split with frontmatter still hurts (2026-04-05)
- **Symptom:** FOCUS_GAP spec split with frontmatter still hurts
- **Root cause:** Splitting a 3-hop file creates many leaf files at 4+ hops, tanking hop_efficiency. Even with frontmatter, ratio 6/28 < 6/11.
- **Fix:** DISCARD: Don't split files that are already 3+ hops from trunk. Only split files at hop 1-2 where the pieces stay reachable.
- **Key file:** `docs/specs/2026-04-04-neuraltree-skill-design.md`
- **Commit:** 61961cc553ab

## Docs
- `CLAUDE.md` — implementation target
- `lessons/v2-design-decisions.md` — later design lessons from v2 build
