---
project: neuraltree
type: concept
---

# Autoloop

**Autonomous improvement loop with KEEP/HOLD/DISCARD decisions.**

The Autoloop is NeuralTree's mode for autonomous project reorganization. It runs the [Explore-First Pipeline](explore-first-pipeline.md) repeatedly, making improvements and deciding whether to keep them.

## How It Works

1. Run the full pipeline (Explore → Map → Analyze → Plan → Execute → Verify)
2. Compare before/after [Flow Score](flow-score.md)
3. Decision:
   - **KEEP:** Score improved, changes are good → apply to real project
   - **HOLD:** Score unchanged, needs more iteration → keep in [sandbox](sandbox-first.md)
   - **DISCARD:** Score decreased or changes are harmful → destroy sandbox

## Key Constraints

- All changes happen in sandbox ([Sandbox First](sandbox-first.md))
- [User Approves Destructive Actions](user-approves-destructive.md) — KEEP requires user confirmation
- Lessons from each loop iteration are recorded via `neuraltree_lesson_add`
- Maximum iterations are bounded to prevent infinite loops

## Lessons Learned

First live run findings are documented in `lessons/autoloop.md`:
- Scoring has limits (some improvements aren't captured by metrics)
- Performance bottlenecks in large projects (many Viking calls)
- Value filtering prevents busywork recommendations

## Related

- [Explore First Pipeline](explore-first-pipeline.md) — autoloop runs this pipeline
- [Sandbox First](sandbox-first.md) — all changes in sandbox
- [User Approves Destructive Actions](user-approves-destructive.md) — user confirms KEEP
- [Flow Score](flow-score.md) — decides KEEP/HOLD/DISCARD
