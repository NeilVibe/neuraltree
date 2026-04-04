# Phase 1: MCP Server Core — Detailed Build Plan

> **Goal:** Build the neuraltree-mcp Python FastMCP server with the first 5 filesystem tools.
> **Duration:** ~3 days (Day 1: scan/trace/backup/restore, Day 2: wire/generate_queries, Day 3: score/diagnose + LLM spike)
> **Test strategy:** Unit test each tool, mock test with simulated project structures.

---

## Day 1: Filesystem Foundation (scan, trace, backup, restore)

### Tool 1: `neuraltree_scan()`

**What it does:** Fast filesystem inventory with scale cap.

**Input:**
- `path: str = "."` — root to scan
- `max_files: int = 10000` — cap to prevent OOM

**Output:**
```json
{
  "dirs": ["memory/", "docs/", ...],
  "files": ["memory/MEMORY.md", ...],
  "sizes": {"memory/MEMORY.md": 1234, ...},
  "dates": {"memory/MEMORY.md": "2026-04-04", ...},
  "empty_dirs": ["archive/old_code/"],
  "total_count": 847,
  "capped": false
}
```

**Implementation:**
- Walk filesystem with `pathlib.Path.rglob("*")`
- Skip: `.git/`, `node_modules/`, `__pycache__/`, `.neuraltree/`
- Count up to max_files, set `capped=true` if hit
- Collect sizes with `stat().st_size`, dates with `stat().st_mtime`
- Identify empty dirs (dirs with no files inside)

**Test plan:**
- Unit: Create tmp dir with known structure, verify counts
- Edge: Empty dir, single file, 10k+ files (cap test), permission denied

---

### Tool 2: `neuraltree_trace()`

**What it does:** Trace ALL references to a file/directory.

**Input:**
- `target: str` — file or directory path to trace

**Output:**
```json
{
  "referenced_by": ["CLAUDE.md:15", "docs/INDEX.md:42"],
  "references_to": ["server/auth/lan.py", "server/config.py"],
  "is_alive": true,
  "permission_errors": []
}
```

**Implementation:**
- Extract target basename and relative path
- Grep patterns to search:
  1. Exact filename: `basename` in all .md, .py, .js, .svelte, .yml, .yaml, .json, .sh files
  2. Relative path: `relative_path` in same files
  3. CI workflows: search `.github/workflows/` and `.gitea/workflows/`
  4. Config files: search `*.json`, `*.yaml`, `*.yml` in root and .claude/
- For each match: record `file:line_number`
- `is_alive` = len(referenced_by) > 0
- Handle permission errors gracefully (add to list, don't crash)

**Test plan:**
- Unit: Create project with known refs, verify all found
- Edge: File with zero refs, file with 50+ refs, permission denied dir
- False negative awareness: document what grep CAN'T find (dynamic imports, template strings)

---

### Tool 3: `neuraltree_backup()`

**What it does:** Backup files before autoloop changes.

**Input:**
- `files: list[str]` — files to back up

**Output:**
```json
{
  "backed_up": ["memory/reference/lan_auth.md", ...],
  "backup_dir": ".neuraltree/.tmp/backup/",
  "total_size": "2.3MB"
}
```

**Implementation:**
- Create `.neuraltree/.tmp/backup/` if not exists
- For each file: copy preserving relative path structure
- Size cap: if backup dir exceeds 100MB, warn and skip large files
- Never touch git stash

**Test plan:**
- Unit: Backup 3 files, verify copies exist with correct content
- Edge: File doesn't exist, permission denied, 100MB cap

---

### Tool 4: `neuraltree_restore()`

**What it does:** Restore files from backup.

**Input:**
- `files: list[str] | None` — specific files or None for all

**Output:**
```json
{
  "restored": ["memory/reference/lan_auth.md", ...],
  "not_found": []
}
```

**Implementation:**
- If files=None, restore ALL from backup dir
- Copy backup files back to original locations
- Verify content matches backup (integrity check)

**Test plan:**
- Unit: Backup, modify original, restore, verify content matches
- Edge: Backup dir empty, partial restore

---

## Day 2: Intelligence Tools (wire, generate_queries)

### Tool 5: `neuraltree_wire()`

**What it does:** Auto-generate ## Related and ## Docs for a leaf file.

**Input:**
- `file_path: str` — the leaf file to wire
- `all_leaf_paths: list[str] | None` — all leaf files to compare against

**Output:**
```json
{
  "related": [
    {"file": "security_state.md", "score": 0.34, "reason": "shared keywords: auth, LAN, security"}
  ],
  "docs": [
    {"file": "server/auth/lan.py", "direction": "referenced_by"}
  ],
  "suggested_content": "## Related\n- [security_state.md]..."
}
```

**Implementation:**
- Keyword extraction:
  1. Read file content
  2. Split on whitespace, lowercase
  3. Filter stopwords (the, a, is, are, was, were, be, been, to, of, in, for, on, with, at, by, from, this, that, it, and, or, but, not, as, an, will, can, do, has, have, had, would, should, could, may, might, shall, must)
  4. Count frequency, keep words appearing 2+ times = topic words
- Jaccard similarity:
  1. For each other leaf: extract keywords same way
  2. `jaccard = len(intersection) / len(union)` (guard: if union empty, return 0.0)
  3. Boost +0.1 if files share ## Docs targets
  4. Boost +0.05 if files are in same branch (same parent dir)
  5. Top 3 candidates with score > 0.15 = ## Related
- Docs extraction:
  1. Find backtick paths in content (`` `path/to/file` ``)
  2. Grep project for references TO this file from source code
  3. Both directions = ## Docs candidates

**Test plan:**
- Unit: Two files with known keyword overlap, verify Jaccard computed correctly
- Unit: File with backtick paths, verify ## Docs extracted
- Edge: Empty file (zero keywords), file with only stopwords, division by zero guard

---

### Tool 6: `neuraltree_generate_queries()`

**What it does:** Auto-generate test queries from project context.

**Input:**
- `claude_md_path: str | None`
- `memory_md_path: str | None`
- `index_paths: list[str] | None`
- `git_log_lines: int = 100`
- `indexed_doc_count: int = 30`

**Output:**
```json
{
  "queries": [
    {"text": "What is GDP?", "source": "claude_md", "category": "what_is"},
    {"text": "How does LAN auth work?", "source": "memory", "category": "how_does"}
  ],
  "sources": {"claude_md": 8, "memory": 10, "indexes": 7, "git": 5},
  "total": 30
}
```

**Implementation:**
- Strategy 1 — CLAUDE.md glossary:
  - Parse `| Term | Meaning |` tables
  - For each term: generate "What is {term}?"
- Strategy 2 — CLAUDE.md nav table:
  - Parse `| Need | Go To |` tables
  - For each need: generate "How does {topic} work?"
- Strategy 3 — MEMORY.md sections:
  - Parse `- [Title](file)` links
  - For each: generate "What do we know about {title}?"
- Strategy 4 — _INDEX.md files:
  - Parse entries
  - For each: generate "Where is {topic} documented?"
- Strategy 5 — git log:
  - `git log --oneline -N`
  - Filter out: starts with "chore:", "ci:", "merge", "version", "trigger"
  - Extract nouns from remaining subjects
  - Generate "What changed with {noun}?"
- Query count: `max(20, min(50, indexed_doc_count / 3))`
- Dedup: remove queries with >80% word overlap

**Test plan:**
- Unit: Feed known CLAUDE.md content, verify correct queries generated
- Unit: Feed git log with junk + real commits, verify filtering works
- Edge: Empty CLAUDE.md, no git, no memory

---

## Day 3: Scoring + LLM Spike (score, diagnose, predict + Precision@3 spike)

### Tool 7: `neuraltree_score()`

**What it does:** Compute 4 structural metrics.

### Tool 8: `neuraltree_diagnose()`

**What it does:** Classify query failures by gap type.

### Tool 9: `neuraltree_predict()`

**What it does:** Virtual backtest with calibration weights.

### LLM-as-Judge Spike

**RISKIEST ASSUMPTION.** Before building the full scoring pipeline, validate:
- Run 5 queries against Viking
- Judge relevance with Qwen3-8B (local) or Haiku (API)
- Does the rubric produce consistent YES/NO?
- Is latency acceptable? (<2s per judgment with local Qwen3)
- If fails: design fallback (keyword overlap scoring instead of LLM)

---

## Build Order

```
Day 1: scan() → test → trace() → test → backup() → test → restore() → test
Day 2: wire() → test → generate_queries() → test
Day 3: score() → test → diagnose() → test → LLM spike → predict() → test
```

Each tool: implement → unit test → mock test → review → log result → next.

---

## Review Gates

After Day 1: Review agent checks all 4 filesystem tools
After Day 2: Review agent checks wire() algorithm + query generation quality
After Day 3: Review agent checks scoring math + LLM spike results

Final: Integration test — all tools running together via MCP server.
