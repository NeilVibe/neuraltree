---
name: First-Run-Feedback Lessons
description: Past first-run-feedback issues
type: reference
last_verified: 2026-04-08
---

## Health score stuck at 10 despite significant navigation improvements (orphans -30, cross-ref +41%, 3 stale trunk files fixed) (2026-04-08)
- **Symptom:** Health score stuck at 10 despite significant navigation improvements (orphans -30, cross-ref +41%, 3 stale trunk files fixed)
- **Root cause:** wiki_lint counts .claude/agents/, .claude/skills/, .claude/commands/ as orphan pages (~200 files). These are framework boilerplate loaded by tooling, not markdown navigation. They dominate the orphan count (336 total, ~200 are .claude/ framework), making the health_score misleading for actual project health.
- **Chain:** scan → wiki_lint → health_score. Scan already has exclude_patterns but wiki_lint doesn't inherit them. The exclude list should flow through the entire pipeline.
- **Fix:** KEEP: Add .claude/agents/, .claude/skills/, .claude/commands/ to default exclude_dirs in wiki_lint (like .git, node_modules). These files are tool-loaded, not wiki-navigated. Alternatively, let neuraltree_scan accept an exclude list that propagates to all downstream tools (wiki_lint, find_dead, score).
- **Key file:** `src/neuraltree/tools/wiki_lint.py`
- **Commit:** 6f1a94dafc60


## Viking batch index fails ~35% of files with HTTP 500 during Phase 1 indexing (107/305 failed) (2026-04-08)
- **Symptom:** Viking batch index fails ~35% of files with HTTP 500 during Phase 1 indexing (107/305 failed)
- **Root cause:** When 7 batches of 50 files are sent in parallel, the Viking/Model2Vec server gets overwhelmed. HTTP 500 errors are likely OOM or connection pool exhaustion on the embedding server. Files that fail tend to be larger (planning docs, summaries).
- **Chain:** neuraltree_viking_index → parallel upload threads → Viking HTTP API → Model2Vec embedding. Bottleneck is Viking server, not embedding model.
- **Fix:** KEEP: Add retry logic to neuraltree_viking_index for HTTP 500 failures. Either retry failed files in a second pass, or reduce parallelism when errors spike. Current max_workers=8 threads per batch x 7 parallel batches = 56 concurrent uploads is too aggressive.
- **Key file:** `src/neuraltree/tools/viking_index.py`
- **Commit:** 6f1a94dafc60


## neuraltree_scan returns 1.1MB JSON that exceeds tool output limits, requiring subagent to process (2026-04-08)
- **Symptom:** neuraltree_scan returns 1.1MB JSON that exceeds tool output limits, requiring subagent to process
- **Root cause:** Project has 5,482 files. scan returns every file path + size + date in one JSON blob. The sizes and dates dicts alone are ~500KB. Tool output cap forces saving to disk and using jq/python to extract.
- **Chain:** neuraltree_scan → JSON output → Claude context. For 5K+ file projects, the full scan output is unusable in conversation.
- **Fix:** KEEP: Add a summary_only mode to neuraltree_scan that returns counts and directory tree without per-file sizes/dates. Full detail can be a separate call or file output. Most consumers only need the file list and total_count, not every byte size.
- **Key file:** `src/neuraltree/tools/scan.py`
- **Commit:** 6f1a94dafc60


## neuraltree_score requires knowledge_map but knowledge_map requires explorer_reports which requires agents. No baseline score possible before exploration. (2026-04-08)
- **Symptom:** neuraltree_score requires knowledge_map but knowledge_map requires explorer_reports which requires agents. No baseline score possible before exploration.
- **Root cause:** Phase 1 (Index) wants to call neuraltree_score for a baseline flow_score, but the tool requires a knowledge_map.json which doesn't exist until Phase 3 (Map). The skill instructs 'Score the project flow WITHOUT a knowledge map' but the tool returns an error without one.
- **Chain:** index.md Step 3 → neuraltree_score → requires knowledge_map.json → doesn't exist yet → error/skip.
- **Fix:** KEEP: Either (a) make neuraltree_score work without a knowledge map by computing basic metrics from wiki_lint + find_dead data, or (b) update sections/index.md Step 3 to skip score when no map exists and note it as 'N/A - will compute after map build'. Option (a) is better for before/after comparison.
- **Key file:** `src/neuraltree/tools/score.py`
- **Commit:** 6f1a94dafc60


## neuraltree_diagnose expects failed_queries but Phase 1 hasn't run precision queries yet at that point in the pipeline (2026-04-08)
- **Symptom:** neuraltree_diagnose expects failed_queries but Phase 1 hasn't run precision queries yet at that point in the pipeline
- **Root cause:** sections/index.md Step 4 calls neuraltree_diagnose passing wiki_lint results, but diagnose expects failed_queries (query strings that returned bad results). The skill conflates two different inputs: structural lint issues vs semantic search failures. In practice, diagnose was skipped because there were no failed queries to pass.
- **Chain:** index.md Step 4 → neuraltree_diagnose(failed_queries=???) → no queries available yet → skipped.
- **Fix:** KEEP: Either (a) reorder index.md so precision queries (Step 6) run before diagnose (Step 4), or (b) let diagnose accept wiki_lint orphans/broken as a different input type and classify them as ISOLATION_GAP or CONTENT_GAP automatically.
- **Key file:** `src/neuraltree/tools/diagnose.py`
- **Commit:** 6f1a94dafc60


## Full 7-phase neuraltree run on 5,482-file project consumed ~80% of context window (2026-04-08)
- **Symptom:** Full 7-phase neuraltree run on 5,482-file project consumed ~80% of context window
- **Root cause:** wiki_lint and find_dead return EVERY orphan/dead file as full JSON objects. On a project with 366 orphans and 290 dead files, these outputs are 50K+ tokens each. Most are .claude/ framework files that aren't actionable. The exploration phase also produces large structured reports from 3 agents.
- **Chain:** Full pipeline: scan(1.1MB) + wiki_lint(50K) + find_dead(50K) + 3 explorer agents(30K each) + map + analyze = fills context.
- **Fix:** KEEP: (1) wiki_lint and find_dead should accept exclude_patterns to filter framework dirs from results, not just from scanning. (2) The skill should recommend running scan with excludes FIRST, then passing the filtered file list to downstream tools. (3) Consider a neuraltree_summary tool that gives top-10 issues instead of exhaustive lists.
- **Key file:** `sections/index.md`
- **Commit:** 6f1a94dafc60


## All Python scripts crash with 'No module named pandas_ta' when run from system Python 3.10 (2026-04-08)
- **Symptom:** All Python scripts crash with 'No module named pandas_ta' when run from system Python 3.10
- **Root cause:** Project requires conda env 'newfin_env' which has pandas_ta, fintest_oop, and all deps. System Python 3.10 is missing them. pandas_ta only ships for Python 3.12+ on PyPI — it's installed from source in the conda env.
- **Chain:** tmux new-session → python3 (system) → import pandas_ta → crash. Fix: tmux new-session → conda activate newfin_env → python → works.
- **Fix:** KEEP: Always prefix tmux commands with: eval "$(conda shell.bash hook)" && conda activate newfin_env && python script.py. Save this as a memory entry so future sessions don't waste 30 minutes debugging import errors.
- **Key file:** `autorsi_unified.py`
- **Commit:** f2419f7a0806


## Tried to make pandas_ta import lazy/optional in 3 files, then had to revert all 3 changes (2026-04-08)
- **Symptom:** Tried to make pandas_ta import lazy/optional in 3 files, then had to revert all 3 changes
- **Root cause:** Root cause was wrong — the dependency isn't missing, the conda env just wasn't activated. Making imports lazy would have hidden real errors and changed behavior (bearish pattern detection silently disabled). Always check the environment before modifying import semantics.
- **Chain:** import fails → wrong instinct: make import lazy → 3 files modified → still crashes deeper → discover conda env → revert all 3 → activate conda → works. Should have been: import fails → check env → activate conda → done.
- **Fix:** KEEP: When imports fail, check conda/venv FIRST before making imports optional. Ask user about their environment. Don't assume system Python is the right interpreter. Lazy imports are a last resort, not a first fix.
- **Key file:** `autorsi_noML.py`
- **Commit:** f2419f7a0806

## Docs
- `src/neuraltree/tools/wiki_lint.py` — implementation target
- `src/neuraltree/tools/viking_index.py` — implementation target
- `src/neuraltree/tools/scan.py` — implementation target
- `src/neuraltree/tools/score.py` — implementation target
- `src/neuraltree/tools/diagnose.py` — implementation target
- `sections/index.md` — implementation target
- `autorsi_unified.py` — implementation target
- `autorsi_noML.py` — implementation target
