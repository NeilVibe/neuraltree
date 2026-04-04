# Feature Proposal: Incident Memory Layer

> **Status:** Design thinking — needs review and incorporation into main spec
> **Origin:** LocaNext session 2026-04-04. User asked "do you remember the images issue?" — neural tree found it because it was in active memory. But older issues (Phase 100-) are compressed to one-liners and details are lost.

---

## The Problem

The neural tree has:
- **rules/** — HOW to behave (survives forever)
- **active/** — WHAT's happening now (current phase)
- **reference/** — WHERE things are (stable facts)
- **archive/** — WHEN things happened (compressed one-liners)

But archive is TOO compressed. Phase 104 = "8 bugs fixed (image/audio/editing/UI)" — which 8? What caused them? How were they fixed? If the same symptom reappears, the agent has no memory of the solution.

## The Tension

**Can't stack everything** — 20 phases × 5 issues = 100 incident files. That's bloat.
**Can't compress everything** — one-liners lose the diagnostic value.

## Proposed Solution: Incident Index (NOT a file-per-incident)

Instead of individual files per incident, use a SINGLE indexed file per domain that captures patterns, not events.

```
memory/
├── lessons/
│   ├── _INDEX.md           (routing switchboard)
│   ├── images.md           (all image-related lessons)
│   ├── database.md         (all DB/PG/SQLite lessons)
│   ├── lan_network.md      (all LAN/networking lessons)
│   ├── ui_rendering.md     (all UI/Svelte/grid lessons)
│   ├── audio.md            (all audio pipeline lessons)
│   └── build_ci.md         (all build/CI lessons)
```

Each file is a **domain lesson book** — NOT a chronological log. Organized by symptom pattern, not by date.

### Example: `lessons/images.md`

```markdown
---
name: Image Lessons
description: Past image issues — DDS, thumbnails, cache, conversion
type: reference
last_verified: 2026-04-04
---

## DDS Images Not Showing (Phase 113)
- **Symptom:** Zero images in Codex on PEARL
- **Root cause:** `pillow-dds` not installed. Standard Pillow can't read DDS.
- **Chain:** thumbnail endpoint → Image.open(dds) → FAILS → HTTP 500
- **Fix:** `import pillow_dds` in media_converter.py + add to build yml
- **Key file:** `server/tools/ldm/services/media_converter.py`
- **Lesson:** Always check if format handlers are installed, not just the base library.

## Chrome Image Cache Bug (DOC-003)
- **Symptom:** Old images persist after update
- **Root cause:** Chrome caches 404 responses permanently
- **Fix:** Cache-bust with `?v=${Date.now()}` on image URLs
- **Key file:** Svelte components that load images
- **Lesson:** Chrome caches ERRORS too, not just successes.

## DDS Greedy 4-Phase Resolution (Phase 102)
- **Symptom:** Wrong image matched to entity
- **Root cause:** Simple name matching was ambiguous
- **Fix:** 4-phase greedy: A=knowledge, B=greedy attrs, C=knowledge_key chain, D=Korean name
- **Key file:** `server/tools/ldm/services/mega_index.py`
- **Lesson:** Image-to-entity matching needs multi-phase disambiguation.
```

### Why Domain Files, Not Per-Incident Files

| Approach | Files at 50 incidents | Searchable? | Maintainable? |
|----------|----------------------|-------------|---------------|
| File per incident | 50 files | Viking finds them | Hard to browse, bloats |
| Chronological log | 1 file, 500+ lines | Grep only | Grows forever |
| **Domain lesson books** | **~6 files, ~30-50 lines each** | **Viking + browse** | **Natural pruning by domain** |

Domain books have a natural cap: there are only so many IMAGE lessons, DB lessons, etc. When a domain book gets too long (~80+ lines), it means the team keeps hitting the same class of problem — which is itself a signal.

## Lifecycle Rules

### When to ADD a lesson
- Bug took >1 hour to diagnose
- Root cause was surprising (not obvious from the code)
- Same symptom appeared before (recurring pattern)
- Fix required understanding a non-obvious chain (A → B → C → failure)

### When to NOT add
- Simple typo fix
- Obvious error (missing import, syntax error)
- One-off configuration issue
- Already documented in the code itself (comments, docstrings)

### When to PRUNE
- Lesson references code that no longer exists (dead neuron)
- Root cause was in a system that was rewritten
- Lesson is so well-known it's in rules/ now (graduated)

### Graduation: Lesson → Rule
If the same lesson applies 3+ times, it should become a RULE:
- `lessons/images.md: "Always check format handlers"` → `rules/coding.md: "Verify format handler installation"`
- The lesson stays (historical context) but the rule becomes the enforcement mechanism

## How NeuralTree AutoLoop Handles This

During the DIAGNOSE phase, after classifying gaps:
1. Check `lessons/` for matching symptoms
2. If found: "This looks like {lesson}. Previous fix was {X} in {file}."
3. If not found after fix: "New lesson learned. Add to lessons/{domain}.md?"

During ENFORCE phase:
- Score `lessons/` freshness (are key files still valid?)
- Check for lessons that should graduate to rules

## Viking Integration

Each lesson book gets indexed in Viking. Queries like:
- "images not showing" → hits `lessons/images.md` (DDS + Chrome cache)
- "PG connection rejected" → hits `lessons/lan_network.md`
- "audio not playing" → hits `lessons/audio.md`

The SYMPTOM is the search key, not the fix. Agents search by what they SEE, not what they need to DO.

## Impact on Scoring

Add to Flow Score? Optional 7th metric:
- **Lesson Coverage:** What % of past incidents (from git log bug fixes) have corresponding lessons?
- Low score = institutional memory loss
- Could be weighted at 0.05 (same as trunk pressure — maintenance tier)

Or keep it out of scoring and just make it a feature of the investigation protocol.

---

## Open Questions

1. Should this be MANDATORY in every neuraltree, or optional for mature projects?
2. Who writes the lessons — the agent automatically after fixing a bug, or the user manually?
3. How to detect "same symptom reappeared" across sessions?
4. Should lessons link to git commits (the actual fix)?

---

*This document should be reviewed and incorporated into the main neuraltree spec.*
