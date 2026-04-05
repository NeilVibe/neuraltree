# NeuralTree AutoLoop Proof Run — 2026-04-05

## Summary

First live execution of the full NeuralTree pipeline against `/home/neil1988/newfin` (5,489 files).

## Results

| Metric | Baseline | After Fix | Delta | 
|--------|----------|-----------|-------|
| **Flow Score** | 0.1679 | 0.1729 | **+0.0050** |
| precision_at_3 | 0.2600 | 0.2800 | +0.0200 |
| hop_efficiency | 0.002 | 0.002 | 0 |
| synapse_coverage | 0.000 | 0.000 | 0 |
| dead_neuron_ratio | 0.583 | 0.583 | 0 |
| freshness | 0.000 | 0.000 | 0 |
| trunk_pressure | 0.300 | 0.300 | 0 |
| Queries passing | 2/50 | 2/50 | 0 |

**Decision: KEEP** — Flow Score improved.

## Fix Applied

Indexed 27 additional files into Viking (14,647 new embeddings):
- 11 Python scripts (autorsi_unified.py, chart_analysis.py, etc.)
- 16 docs (protocol/, analysis/, guides/ directories)

## Why Small Improvement

### The ceiling problem
Indexing files into Viking only improves `precision_at_3` (weight: 0.25). The other 5 metrics (weight: 0.75 combined) measure **structural properties** of the project:
- `synapse_coverage` (0.20): needs `## Related` links between files → newfin has ZERO
- `freshness` (0.10): needs `last_verified` frontmatter dates → newfin has ZERO
- `hop_efficiency` (0.25): needs files reachable in ≤2 hops via indexes/links → newfin score 0.002
- `dead_neuron_ratio` (0.15): 42% orphan files → needs wiring
- `trunk_pressure` (0.05): CLAUDE.md is 700+ lines → needs trimming

**Maximum possible score from indexing alone: ~0.25** (perfect precision_at_3). To break past 0.25, newfin needs structural changes (wiring, frontmatter, index files).

### The query quality problem
48/50 queries generated from CLAUDE.md headings produce verbose/noisy query text like "How does NEVER RUN PRODUCTION SCRIPTS WITHOUT EXPLICIT REQUEST work?" — these are extracted literally from ## headings. The heading extraction needs smarter text cleaning.

### The LLM judge strictness
Even with full content via viking_read, only 28% of results judged relevant. Possible causes:
1. Viking's semantic search returns topically adjacent but not directly answering results
2. Qwen3.5:4b with think=false may be too conservative (quick NO without reasoning)
3. The relevance rubric is binary — "tangentially related" scores 0 same as "completely irrelevant"

## Bugs Found During Proof Run (Session Total)

| # | Bug | Fix | Impact |
|---|-----|-----|--------|
| 1 | `generate_queries.py` L113: relative path resolved to CWD | `root / path` | Queries from wrong CLAUDE.md |
| 2 | Query gen only parsed "Term"/"Need" tables | Added heading + bold term extraction | 0→79 queries from CLAUDE.md |
| 3 | Qwen3.5 thinking mode: 75s/call | `think: false` → 3.3s/call | 17x speedup |
| 4 | Viking search abstracts empty | Added `viking_read()` for full content | precision 0.000→0.260 |
| 5 | Path traversal vulnerability | Added `is_absolute()` + `validate_within_root` | Security fix |
| 6 | Strategy 2c ran unconditionally | Gated on `claude_count == 0` | Fixed query inflation |
| 7 | Sources counts stale after dedup | Recount from final list | Correct reporting |
| 8 | No per-strategy cap | `_MAX_PER_STRATEGY = 15` | Prevents domination |
| 9 | Re-score path missing viking_read | Added to SKILL.md L1325 | Consistent scoring |

## Performance

| Operation | Time |
|-----------|------|
| Scan (5,489 files) | 0.5s |
| Generate queries (50) | 0.3s |
| Viking search (50 queries × 3) | 1.5s |
| Viking read (150 results) | 3.0s |
| LLM judge (150 calls, think=false) | 45s |
| Structural score | 2.0s |
| Diagnose | 0.5s |
| **Full benchmark** | **~50s** |
| Viking indexing (27 files) | ~120s |
| **Full autoloop iteration** | **~250s** |

## Next Steps (to break past 0.25)

1. **Structural fixes needed** — the autoloop should add `## Related` wiring between newfin's docs (SYNAPSE_GAP fixes)
2. **Freshness** — add `last_verified` frontmatter to newfin's markdown files
3. **Trunk pressure** — split newfin's 700-line CLAUDE.md into focused sections
4. **Better heading extraction** — clean heading text (strip emoji, uppercase phrases, numbered prefixes)
5. **Graduated relevance** — consider 0/0.5/1 scoring instead of binary YES/NO for borderline results
