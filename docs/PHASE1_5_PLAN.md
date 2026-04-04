# Phase 1.5: Incident Memory / Lessons Layer — Detailed Build Plan

> **Goal:** Add lesson_match and lesson_add MCP tools, extract shared text utilities, integrate with generate_queries and predict, fix diagnose.py validation bug.
> **Prerequisite:** Phase 1 complete (14 tools, 121 tests passing, all review findings fixed)
> **Spec:** docs/FEATURE_INCIDENT_MEMORY.md
> **Architecture constraint:** The Skill orchestrates lesson lookup. The MCP server stays pure computation. lesson_match is NOT embedded inside diagnose.
> **Reviewed by:** 4 agents (architecture, security, implementability, test coverage). 10 corrections applied.

---

## Step 1: Extract Shared Text Utilities

### Create `src/neuraltree_mcp/text_utils.py`

Extract from `tools/wire.py` into a shared module:

```python
STOPWORDS: frozenset[str]       # ~70 common English stopwords
SKIP_DIRS: frozenset[str]       # .git, node_modules, __pycache__, .neuraltree, .venv, venv, .tox, htmlcov
                                # NOTE: This is the superset from scan.py. Using it across all tools
                                # adds .tox and htmlcov skipping to wire/score/diagnose — net improvement,
                                # intentional behavioral change (test artifacts should never be indexed).
BACKTICK_PATH_RE: re.Pattern    # Shared regex for backtick path extraction

def extract_keywords(content: str, min_freq: int = 2) -> set[str]:
    """Extract topic keywords (words appearing min_freq+ times, minus stopwords).
    
    Regex: [a-zA-Z_][a-zA-Z0-9_]{2,} (identifier-like tokens, 3+ chars)
    Filters: stopwords, len > 2
    Returns: set of lowercase keyword strings
    
    Use min_freq=1 for short text (symptoms, queries).
    Use min_freq=2 for long text (file content, wiring comparison).
    """

def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity. Returns 0.0 if both empty.
    Simplified: union = a | b; return len(a & b) / len(union) if union else 0.0
    """

def extract_backtick_paths(content: str) -> list[str]:
    """Extract file paths from `backtick` references using BACKTICK_PATH_RE."""

def walk_project_files(root: Path, extensions: set[str] | None = None) -> list[Path]:
    """Walk project tree, skip SKIP_DIRS, optionally filter by extension.
    Used by: wire (find .md leaves), lesson_match (find lesson files),
    diagnose (find text files), score (find .md files).
    """
```

### Update consumers (all in same commit to avoid broken imports):
- `tools/wire.py` — import from text_utils, remove `_extract_keywords`, `_jaccard`, `_extract_backtick_paths`, `STOPWORDS`, `SKIP_DIRS`, `_find_leaf_files`. Replace `_find_leaf_files(root)` with `walk_project_files(root, {".md"})` at line 108.
- `scoring/diagnose.py` — import `SKIP_DIRS` from text_utils, DELETE local `SKIP_DIRS` at line 10. Replace ad-hoc keyword extraction (lines 90-98) with `extract_keywords(query_text + " " + hint, min_freq=1)` — preserving the hint merge.
- `scoring/score.py` — import `SKIP_DIRS` from text_utils, delete local definition
- `tools/scan.py` — import `SKIP_DIRS` from text_utils, delete local definition
- `tools/trace.py` — import `SKIP_DIRS` from text_utils, delete local definition
- `tests/unit/test_wire.py` — update imports to `from neuraltree_mcp.text_utils import ...` IN THE SAME COMMIT

### Test plan:
- Create `tests/unit/test_text_utils.py` with extracted + new tests
- Update `test_wire.py` imports (same commit as extraction)
- Run full suite to verify no regressions

---

## Step 2: Build `neuraltree_lesson_match`

### Create `src/neuraltree_mcp/tools/lesson.py`

**Tool: `neuraltree_lesson_match(symptoms: list[str], project_root: str = ".") -> dict`**

Searches `memory/lessons/` (or `lessons/`) for matching past incidents.

**Input:**
- `symptoms: list[str]` — batch of symptom descriptions to search for
- `project_root: str` — project root (validated)

**Algorithm:**
1. `validate_project_root(project_root)`
2. Discover lesson files: `walk_project_files(root, {".md"})` filtered to paths containing `/lessons/`, skip `_INDEX.md`
3. Parse each lesson file into structured entries:
   - Split on `## ` headings
   - **Skip known non-lesson headings:** `## Related`, `## Docs`, `## Content`, `## Rules` — these are structural sections, not lesson entries
   - Extract fields from `- **Bold:** value` bullet lines under each heading
   - Fields: symptom, root_cause, chain, fix, key_file, lesson, commit
4. For each input symptom:
   - `extract_keywords(symptom, min_freq=1)` (min_freq=1 because symptoms are short)
   - For each parsed lesson entry:
     - `extract_keywords(entry.heading + " " + entry.fields.get("symptom", "") + " " + entry.fields.get("root_cause", ""), min_freq=1)`
     - `score = jaccard(symptom_kw, lesson_kw)`
     - Boost +0.15 if any symptom keyword appears in the lesson heading itself
   - Cap score at 1.0
   - Keep matches with score > 0.2
   - Sort by score descending, return top 3 per symptom
   - **Zero-match case:** still emit entry in `matches[]` with `"lessons": []` so the Skill knows "we checked, found nothing"

**Output:**
```json
{
  "matches": [
    {
      "symptom_query": "images not showing",
      "lessons": [
        {
          "heading": "DDS Images Not Showing",
          "domain": "images",
          "file": "memory/lessons/images.md",
          "fields": {
            "symptom": "Zero images in Codex on PEARL",
            "root_cause": "pillow-dds not installed",
            "fix": "import pillow_dds in media_converter.py",
            "key_file": "server/tools/ldm/services/media_converter.py",
            "lesson": "Always check if format handlers are installed",
            "commit": "abc1234"
          },
          "score": 0.72
        }
      ]
    },
    {
      "symptom_query": "quantum computing",
      "lessons": []
    }
  ],
  "total_matches": 1,
  "warnings": []
}
```

**Validation:**
- `validate_project_root(project_root)`
- Max 50 symptoms per call (prevent DoS)
- Max 1000 chars per symptom

---

## Step 3: Build `neuraltree_lesson_add`

**Tool: `neuraltree_lesson_add(domain: str, lesson: dict, project_root: str = ".") -> dict`**

Adds a lesson entry to a domain file.

**Input:**
- `domain: str` — domain name, validated against allowlist regex
- `lesson: dict` — structured lesson content
- `project_root: str` — project root (validated)

**Domain validation (allowlist):**
```python
DOMAIN_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$')
```
- Reject empty, slash-containing, dot-leading, or overly long names
- Normalize to lowercase: `domain = domain.lower()`

**Lesson dict schema:**
```python
REQUIRED_KEYS = {"symptom", "root_cause", "fix"}
OPTIONAL_KEYS = {"chain", "key_file", "lesson", "commit"}
ALL_KEYS = REQUIRED_KEYS | OPTIONAL_KEYS
MAX_FIELD_LENGTH = 2000
```
- Reject unknown keys
- Reject non-string values
- Reject fields exceeding MAX_FIELD_LENGTH
- Strip leading `---` AND reject values containing `\n---\n` (frontmatter injection prevention)

**Per-file size cap:**
```python
MAX_LESSON_FILE_BYTES = 512 * 1024  # 512KB per domain file
```
If existing file exceeds cap, return `{"added": false, "error": "Domain file exceeds 512KB limit"}`.

**Algorithm:**
1. `validate_project_root(project_root)`
2. Validate domain (regex + lowercase normalization)
3. Locate lessons directory: try `memory/lessons/`, fall back to `lessons/`
4. Construct file path, then `validate_within_root(lesson_file, root)` — defense-in-depth
5. Create dir + `_INDEX.md` if they don't exist; `validate_within_root(lessons_dir, root)` after mkdir
6. Check file size cap
7. Read existing domain file (or start empty)
8. Duplicate check: `extract_keywords(new_symptom, min_freq=1)` vs each existing symptom heading — reject if >80% word overlap. **Must use `min_freq=1`** — symptoms are short, min_freq=2 would return empty keywords.
9. Append new lesson entry in standard format:
   ```markdown
   ## {symptom} ({date})
   - **Symptom:** {symptom}
   - **Root cause:** {root_cause}
   - **Chain:** {chain}  (if provided)
   - **Fix:** {fix}
   - **Key file:** `{key_file}`  (if provided, backtick format for scanner compatibility)
   - **Lesson:** {lesson}  (if provided)
   - **Commit:** {commit}  (auto-detected if not provided)
   ```
10. Update file-level `## Docs` section: if `key_file` provided, append to the `## Docs` section at end of file (NOT per-entry — file-level, so scanner checks all key_files). If `## Docs` doesn't exist, create it.
11. Update `_INDEX.md` if domain is new (append `- [Domain](domain.md) — domain lessons`)
12. Auto-detect commit hash if not provided:
    ```python
    result = subprocess.run(["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=str(root), timeout=10)
    commit = result.stdout.strip()[:12]
    if not re.match(r'^[0-9a-f]{7,40}$', commit):
        commit = None  # graceful fallback
    ```
    **Note:** `git rev-parse HEAD` is a non-pure side effect. This is an intentional exception to the MCP purity rule — documented here.

**Output:**
```json
{
  "added": true,
  "file": "memory/lessons/images.md",
  "domain": "images",
  "duplicate": false,
  "commit": "abc1234",
  "warnings": []
}
```

---

## Step 4: Register new tools in `server.py`

Add to imports and registration blocks:

```python
from neuraltree_mcp.tools.lesson import register as register_lesson
# ...
register_lesson(mcp)
```

Update docstring: 14 → 16 tools. Add `Lessons: lesson_match, lesson_add` to category list.

---

## Step 5: Update `generate_queries.py` — Strategy 6

**Add BEFORE git log (Strategy 5 becomes 6).** Lesson regression queries are higher-value than git-derived queries.

**Strategy 5 (new) — Lesson symptoms:**
1. Discover lesson files via `walk_project_files(root, {".md"})` filtered to `*/lessons/*.md`, skip `_INDEX.md`
2. Parse `## ` headings, skip known non-lesson headings (`## Related`, `## Docs`, `## Content`)
3. For each symptom heading: generate `{"text": "Has {symptom} recurred?", "source": "lessons", "category": "regression"}`
4. Add `"lessons": 0` to `sources` dict
5. Update docstring to describe 6 strategies

**Execution order:**
```
Strategy 1: CLAUDE.md glossary     (what_is)
Strategy 2: CLAUDE.md nav          (how_does)
Strategy 3: MEMORY.md links        (what_know)
Strategy 4: _INDEX.md entries      (where_is)
Strategy 5: Lesson symptoms        (regression)   ← NEW
Strategy 6: git log                (what_changed)  ← was Strategy 5
```

---

## Step 6: Update `predict.py` — lesson_add action

Add to the action dispatch (between archive/delete and `change_impacts.append`):

```python
elif action == "lesson_add":
    # Institutional memory contribution — informational metric only
    current_lc = predicted.get("lesson_coverage", 0.0) or 0.0
    predicted["lesson_coverage"] = current_lc + 0.02
    impact["metric_deltas"]["lesson_coverage"] = 0.02
```

**Must update both `predicted` dict AND `metric_deltas`** — otherwise `lesson_coverage` won't appear in `predicted_metrics` output.

No change to Flow Score weights. `lesson_coverage` is NOT in the `WEIGHTS` dict and will not affect the weighted composite.

---

## Step 7: Fix `diagnose.py` validation bug

Add `validate_project_root` import and call. Existing bug — `diagnose` currently accepts any `project_root` without validation.

```python
from neuraltree_mcp.validation import validate_project_root
# ...
try:
    root = validate_project_root(project_root)
except ValueError as e:
    return {"diagnoses": [], "gap_counts": {}, "fix_priority": [], "total_failures": 0,
            "warnings": [], "error": str(e)}
```

---

## Step 8: Update test fixtures

### `tests/conftest.py` — extend `tmp_project`

Add `memory/lessons/` with:

**`_INDEX.md`** — routing switchboard (uses `- [Title](path)` format for generate_queries Strategy 4 compatibility):
```markdown
---
name: Lessons Index
type: reference
last_verified: 2026-04-04
---

- [Images](images.md) — image pipeline lessons
- [Database](database.md) — DB/PG lessons
```

**`images.md`** — well-formed, fresh, 2 entries + `## Docs` at file level:
```markdown
---
name: Image Lessons
description: Past image issues — DDS, thumbnails, cache, conversion
type: reference
last_verified: 2026-04-04
---

## DDS Images Not Showing (Phase 113)
- **Symptom:** Zero images in Codex on PEARL
- **Root cause:** pillow-dds not installed
- **Fix:** import pillow_dds in media_converter.py
- **Key file:** `server/tools/media_converter.py`
- **Lesson:** Always check if format handlers are installed

## Chrome Image Cache Bug (DOC-003)
- **Symptom:** Old images persist after update
- **Root cause:** Chrome caches 404 responses permanently
- **Fix:** Cache-bust with ?v=${Date.now()} on image URLs
- **Key file:** `locaNext/src/components/ImageViewer.svelte`
- **Lesson:** Chrome caches ERRORS too, not just successes

## Related
- [database.md](database.md) — cross-domain reference

## Docs
- `server/tools/media_converter.py` — DDS conversion
- `locaNext/src/components/ImageViewer.svelte` — image display
```

**`database.md`** — stale, unwired, 1 entry:
```markdown
---
name: Database Lessons
description: Past DB issues — PG, SQLite, connections
type: reference
last_verified: 2025-06-01
---

## PG Connection Refused
- **Symptom:** Cannot connect to PostgreSQL after router reboot
- **Root cause:** LAN IP changed, pg_hba.conf had old IP
- **Fix:** Update pg_hba.conf with new subnet range
- **Key file:** `config/pg_hba.conf`
```

Tests covered by this fixture:
- lesson_match: DDS symptom match, Chrome cache match, PG connection match
- lesson_match: `## Related` and `## Docs` correctly skipped (not parsed as lesson entries)
- generate_queries Strategy 5: 3 lesson headings → 3 regression queries
- score.py: `images.md` has `## Docs` with valid backtick paths (scanner compatible)
- score.py: `database.md` stale (last_verified 2025-06-01), missing `## Docs` (dead neuron candidate)

---

## Step 9: Write tests (~30 tests)

### Unit tests: `tests/unit/test_text_utils.py` (~10 tests)
- test_extract_keywords_basic
- test_extract_keywords_stopwords_removed
- test_extract_keywords_min_freq_1 — single-occurrence words returned
- test_extract_keywords_min_freq_2_default — frequency threshold works
- test_extract_keywords_empty_content
- test_jaccard_identical / disjoint / partial / empty (4 tests)
- test_extract_backtick_paths_basic
- test_walk_project_files_skips_dirs — verify SKIP_DIRS respected
- test_walk_project_files_extension_filter — only .md returned when filtered

### Unit tests: `tests/unit/test_lesson.py` (~16 tests)

**lesson_match tests:**
- test_lesson_match_finds_symptom — "DDS images" query matches DDS lesson
- test_lesson_match_no_match — "quantum computing" returns `"lessons": []`
- test_lesson_match_ranks_symptom_over_fix — "images not showing" ranks DDS > Chrome cache (symptom-first)
- test_lesson_match_short_symptom_still_matches — single-word "DDS" matches (verifies min_freq=1)
- test_lesson_match_batch — 2 symptoms, each gets own top-3 (per-symptom isolation)
- test_lesson_match_empty_lessons_dir — no crash, returns empty matches per symptom
- test_lesson_match_malformed_file — broken frontmatter doesn't crash, adds warning
- test_lesson_match_skips_non_lesson_headings — `## Related`, `## Docs` NOT parsed as entries
- test_lesson_match_file_with_no_entries — lesson file with only frontmatter returns no entries

**lesson_add tests:**
- test_lesson_add_creates_domain_file — new domain creates file + _INDEX.md
- test_lesson_add_appends_to_existing — second entry in same domain file
- test_lesson_add_duplicate_detection — same symptom blocked (>80% overlap with min_freq=1)
- test_lesson_add_duplicate_boundary — 80% overlap (4/5 words identical) is NOT blocked (threshold is >80%, exclusive)
- test_lesson_add_validates_schema — rejects unknown keys, non-string values, oversized fields
- test_lesson_add_sanitizes_domain — `../../etc/passwd` blocked by regex
- test_lesson_add_empty_domain_rejected — empty string blocked
- test_lesson_add_index_consistency — two sequential domain adds, _INDEX.md has both entries
- test_lesson_add_file_size_cap — returns error when domain file exceeds 512KB
- test_lesson_add_file_level_docs — `## Docs` section appended at file level, not per-entry
- test_lesson_add_commit_autodetect_graceful — commit is None when not in git repo

### Integration tests: add to `tests/integration/test_tool_calls.py` (~6 tests)
- test_lesson_match_via_mcp — call via mcp.call_tool(), verify output shape
- test_lesson_add_via_mcp — call via mcp.call_tool(), verify file created on disk
- test_lesson_add_domain_case_normalization — "Images" → "images" (same file)
- test_lesson_add_path_traversal_blocked — domain="../../etc" rejected
- test_generate_queries_includes_lessons — assert `sources["lessons"] >= 3` and at least one `"category": "regression"` query
- test_lesson_match_zero_match_still_emits_entry — verify `{"symptom_query": "xyz", "lessons": []}` in output

### Update existing tests:
- `tests/unit/test_wire.py` — update imports to `from neuraltree_mcp.text_utils import ...` (SAME COMMIT as Step 1)
- `tests/unit/test_generate_queries.py` — add test for Strategy 5 (lesson symptoms)

---

## Build Order

```
Step 1:  text_utils.py + update ALL consumer imports + update test_wire.py imports → test full suite
Step 2:  lesson.py (lesson_match) → test
Step 3:  lesson.py (lesson_add) → test
Step 4:  server.py registration → test (verify 16 tools)
Step 5:  generate_queries.py Strategy 5 → test
Step 6:  predict.py lesson_add action → test
Step 7:  diagnose.py validation fix → test
Step 8:  conftest.py fixture update → test full suite
Step 9:  all remaining tests (lesson unit + integration) → full suite
```

**Critical sequencing:** Step 1 MUST update test_wire.py imports in the same commit as the extraction. Otherwise the test suite breaks between steps.

---

## Review Gate

After all steps: spawn 5 review agents (code quality, test coverage, silent failures, security, spec compliance). All must pass before Phase 2 (SKILL.md).

---

## What This Does NOT Change

- **Flow Score weights** — no change to the 6-metric composite
- **`neuraltree_diagnose` logic** — stays pure gap classification (Skill joins lesson data separately)
- **Sandbox tools** — no change
- **Backup/restore** — no change
- **Score algorithm** — lesson `## Docs` at file level, scanner covers key_file references automatically

## Known Limitations (Documented, Not Blocking)

- **`## Docs` scanner coverage:** The dead-neuron scanner checks "at least one key_file is valid" per file. If a file has 5 lessons with 5 different key_files and only one is stale, the scanner may not flag it individually. Acceptable for Phase 1.5; can refine in Phase 2 if needed.
- **Strategy 5 cap risk:** If Strategies 1-4 saturate the query count cap (50), lesson regression queries could still be dropped. Acceptable because it only happens on very well-documented projects where the cap is hit before lessons — and those projects have strong coverage anyway.
- **`git rev-parse HEAD` purity exception:** This is a non-pure side effect in the MCP server. Documented and intentional — the alternative (requiring the Skill to pass the commit hash) adds unnecessary orchestration complexity for a best-effort metadata field.
