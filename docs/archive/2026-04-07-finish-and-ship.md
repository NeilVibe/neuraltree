# NeuralTree Finish & Ship — Design Spec

> Trim dead weight, wire orphaned tools, integrate autoresearch. Ship clean.

## Current State

- 26 MCP tools, 7 never called by pipeline
- flow_score: 0.894 (precision@3: 0.613)
- 4,546 lines production code, 426 tests passing
- autoloop described but never implemented
- lesson system built but orphaned

## Changes

### Phase 1: Delete Dead Weight

Delete tools that are genuinely redundant (sandbox/Claude already does the job better):

| Tool | Lines | Why delete |
|------|-------|-----------|
| `predict` | 237 | Sandbox + re-score is real measurement, not simulation |
| `update_calibration` | (in predict.py) | Depends on predict |

Also delete:
- `tests/unit/test_predict.py`
- `tests/unit/test_diagnose.py` (diagnose stays but test file may need updates)
- Predict/calibration tests from `test_e2e_pipeline.py` and `test_degraded_mode.py`

Relocate `_viking_uri_matches_file` from `diagnose.py` to `text_utils.py` (test_reorganize.py imports it).

Update `server.py`: remove predict/calibration registration.

**Tools after: 24 (was 26)**

### Phase 2: Wire Orphaned Tools

**lesson_match → Analyze phase:**
Before Claude reasons about issues, check: "have we seen this symptom before?"
Add to analyze.md Step 1: `lesson_match(symptom=<issue_type>, project_root=...)`
This surfaces rules like "don't split files 3+ hops from trunk."

**lesson_add → Verify phase (discard path):**
When autoresearch discards a change, record WHY it failed.
Add to verify.md: if score decreased, `lesson_add(lesson=<what_failed>)`

**wiki_lint → Verify phase:**
After sandbox changes, run wiki_lint as health check.
Add to verify.md Step 1b: `wiki_lint(project_root=sandbox_root)`
Catches broken links/orphans that the score metrics miss.

**diagnose → stays but NOT wired:**
Keep as standalone tool for manual debugging. Don't force it into pipeline.

### Phase 3: Split reorganize.py

809 lines, 6 tools → 6 files + shared utils:

```
tools/
├── reorganize_utils.py    (shared: _SEARCHABLE_EXTENSIONS, _find_all_references, _compute_rewrites, _strip_ref_fragment)
├── plan_move.py
├── plan_split.py
├── find_dead.py
├── generate_index.py
├── shrink_and_wire.py
└── split_and_wire.py
```

Update imports in server.py and test_reorganize.py.

### Phase 4: Autoresearch Integration

Replace the unimplemented autoloop with autoresearch:

**In SKILL.md, the "auto" subcommand becomes:**
```
/neuraltree auto
→ Runs /autoresearch with:
  - Scope: project docs/markdown files
  - Metric: targeted sub-metric (not composite flow_score)
  - Verify: neuraltree_score → parse specific sub-metric
  - Each iteration: one pipeline fix (wire/move/split/shrink)
```

**Sub-metric targeting per iteration (Karpathy principle):**
- Iteration picks the LOWEST sub-metric
- Targets that ONE metric specifically
- Measures improvement on THAT metric
- flow_score is the dashboard, not the target

**Delete from docs/concepts/:** autoloop.md (replaced by autoresearch integration)
**Keep:** lessons/ directory (real knowledge, now wired in)

### Phase 5: Cleanup

- Archive 10 handoff docs → `docs/archive/` (fixes reachability 0.882 → ~0.98)
- Fix CLAUDE.md: remove false claims about lesson recording, diagnose calls, autoloop
- Update CLAUDE.md: 24 tools (was 26), document autoresearch integration
- Update README.md: match reality
- Rebuild knowledge map after all changes

### Phase 6: Merge Explore + Map

User-facing simplification: explore and map are one phase called "Understand."

```
Before: Explore → Map → Analyze → Plan → Execute → Verify (6 phases)
After:  Understand → Analyze → Plan → Execute → Verify (5 phases)
```

Internally explore.md and map.md merge into understand.md.
The pipeline feels tighter. User doesn't care about the split.

## Final State

- **22 tools** (was 26): 2 deleted, 2 kept standalone (restore, diagnose)
- **5-phase pipeline**: Understand → Analyze → Plan → Execute → Verify
- **Lessons wired in**: analyze checks history, verify records failures
- **wiki_lint wired in**: verify catches structural rot
- **Autoloop = autoresearch**: no custom loop, use the proven skill
- **No oversized files**: reorganize.py split into 6+1 files
- **Clean docs**: no false claims, no dead handoffs

## Execution Order

1. Phase 1 (delete) — smallest blast radius, immediate cleanup
2. Phase 2 (wire) — add value to existing pipeline
3. Phase 3 (split) — code organization
4. Phase 4 (autoresearch) — skill integration
5. Phase 5 (cleanup) — docs and knowledge map
6. Phase 6 (merge) — final simplification

## Risk Mitigations

- Relocate `_viking_uri_matches_file` BEFORE deleting diagnose (if we delete it later)
- Run full test suite after each phase
- Rebuild knowledge map after phase 3 and 5
