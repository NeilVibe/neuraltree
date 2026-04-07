# Autoloop

**Autonomous improvement via `/autoresearch` with flow_score sub-metrics.**

NeuralTree's autoloop mode delegates autonomous iteration to the
`/autoresearch` skill (Karpathy-inspired). Instead of a custom loop
with custom prediction and lesson recording, autoloop uses:

- **Metric:** Individual flow_score sub-metric (the lowest one)
- **Scope:** Project docs/markdown files
- **Verify:** `neuraltree_score` → parse targeted sub-metric
- **Each iteration:** One pipeline fix (wire/move/split/shrink)
- **Keep/Discard:** Autoresearch handles via git commit/revert
- **Learning:** `neuraltree_lesson_add` records failures in Verify phase

## Usage

```
/neuraltree auto
```

This routes to `/autoresearch` with the neuraltree pipeline as the
modification engine and the lowest flow_score sub-metric as the target.

## Why Autoresearch > Custom Loop

| Custom autoloop (never shipped) | /autoresearch (proven) |
|--------------------------------|----------------------|
| Custom predict tool | Sandbox + real measurement |
| Custom calibration | Git-based keep/discard |
| Custom lesson recording | lesson_add in verify phase |
| Had to be built and maintained | Already exists and works |

## Related

- [Flow Score](flow-score.md) — the metric autoresearch targets
- [Sandbox First](sandbox-first.md) — changes always in sandbox
- [Algorithm in Tool, Judgment in Claude](algorithm-tool-judgment-claude.md)
