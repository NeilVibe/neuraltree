# Explore Phase — Targeted Deep Reading

> Read deeply where it matters. The Index phase already told us where to look.

**Input:** `index_results` from Index phase, `scan_result`, `agent_count`, `knowledge_files`.
**Output:** `explorer_reports` (list of per-agent structured reports).

## Scale-Aware Strategy

The Index phase gave us quantitative health data. Now we explore
selectively based on project size.

```
total_kb_files = len(knowledge_files)

if total_kb_files < 300:
    strategy = "full"        # Read everything deeply (original v2 behavior)
elif total_kb_files < 2000:
    strategy = "targeted"    # Only explore problem areas from Index
else:
    strategy = "sampled"     # Sample + problem areas
```

---

## Strategy: FULL (< 300 files)

Same as v2 — divide all files among agents, read everything.

### Step 1: Assign Directory Slices

```
dir_file_counts = {}
for f in knowledge_files:
    d = os.path.dirname(f) or "."
    dir_file_counts.setdefault(d, []).append(f)

agent_slices = [[] for _ in range(agent_count)]
agent_loads = [0] * agent_count

for d, files in sorted(dir_file_counts.items(), key=lambda x: -len(x[1])):
    lightest = agent_loads.index(min(agent_loads))
    agent_slices[lightest].append({"dir": d, "files": files})
    agent_loads[lightest] += len(files)
```

### Step 2: Launch All Agents

Launch all agents in parallel (same as v2). Each agent reads its full
slice and reports structured JSON.

---

## Strategy: TARGETED (300-2000 files)

Only explore directories flagged as problems by the Index phase.
This typically reduces exploration from 1000+ files to 100-300.

### Step 1: Identify Exploration Targets

Build the target list from Index results:

```
target_files = set()

# 1. All orphan files (wiki_lint found no links to them)
for orphan in index_results["wiki_lint"].get("orphan_pages", []):
    target_files.add(orphan["file"])

# 2. All files with broken outgoing links
for broken in index_results["wiki_lint"].get("broken_links", []):
    target_files.add(broken["file"])

# 3. All stale files
for stale in index_results["wiki_lint"].get("stale_pages", []):
    target_files.add(stale["file"])

# 4. All dead files (nothing references them at all)
for dead in index_results["dead_files"].get("dead_files", []):
    target_files.add(dead["path"] if isinstance(dead, dict) else dead)

# 5. All files from diagnosed issues
for issue in index_results["diagnose"].get("issues", []):
    for f in issue.get("files", []):
        target_files.add(f)

# 6. Trunk files (always explore — CLAUDE.md, README.md, INDEX files)
trunk_patterns = ["CLAUDE.md", "README.md", "INDEX.md", "_INDEX.md",
                  "MEMORY.md", "ROADMAP.md", "PROJECT.md"]
for f in knowledge_files:
    basename = os.path.basename(f).upper()
    if any(basename == p.upper() for p in trunk_patterns):
        target_files.add(f)

# 7. If still < 50 files, add random sample from underexplored dirs
if len(target_files) < 50:
    import random
    remaining = [f for f in knowledge_files if f not in target_files]
    random.shuffle(remaining)
    target_files.update(remaining[:50 - len(target_files)])

# Filter to only files that actually exist in scan
target_files = sorted(f for f in target_files if f in set(knowledge_files))
```

### Step 2: Scale Agent Count

```
# Fewer targets = fewer agents needed
if len(target_files) < 30:
    explore_agent_count = 2
elif len(target_files) < 100:
    explore_agent_count = 3
elif len(target_files) < 300:
    explore_agent_count = 5
else:
    explore_agent_count = min(agent_count, 7)
```

### Step 3: Assign and Launch

Same greedy slicing algorithm as FULL, but on `target_files` only.

```
emit(f"Phase 2/8: Targeted exploration — {len(target_files)} files "
     f"(out of {len(knowledge_files)}) with {explore_agent_count} agents")
```

---

## Strategy: SAMPLED (2000+ files)

For very large projects. Explore trunk + problem areas + statistical sample.

Same as TARGETED but add:
- Max 5 files per directory (random sample)
- Cap total at 500 files
- Always include the 20 largest files (likely important)

---

## Explorer Agent Prompt Template

All strategies use the same agent prompt. The agent receives its file
list and reports structured JSON.

```
You are an explorer agent for NeuralTree. Your job is to READ every file
in your assigned slice and report what you find.

PROJECT ROOT: {project_root}
YOUR ASSIGNED FILES:
{file_list}

For EACH file, read it fully and report:
{
  "path": "relative/path.md",
  "topic": "one-line summary of what this file is about",
  "key_concepts": ["concept1", "concept2", ...],  // 3-8 concepts
  "references_to": ["other_file.md", ...],  // files this references
  "size_lines": 123,
  "staleness": null or "description of outdated content",
  "issues": ["too large", "duplicate of X", "misplaced", ...]
}

For EACH directory, report:
{
  "path": "relative/dir/",
  "purpose": "what this directory contains",
  "cohesion": "high" | "medium" | "low",
  "issues": ["naming unclear", "mixed concerns", ...]
}

Also report any CROSS-FILE OBSERVATIONS:
- Files that seem to duplicate each other
- Files that reference things that don't exist
- Content that seems misplaced (wrong directory)
- Clusters of files that belong together but are separated

Be thorough. Be honest. Report problems you see.
Return your report as a JSON object with keys: files, directories, observations.
```

## Collect Reports

```
explorer_reports = []
for agent_result in agent_results:
    report = parse_json(agent_result)
    explorer_reports.append(report)

total_files_explored = sum(len(r.get("files", [])) for r in explorer_reports)
total_issues_found = sum(
    len(f.get("issues", [])) for r in explorer_reports for f in r.get("files", [])
)
emit(f"Phase 2/8: Explored {total_files_explored} files with "
     f"{explore_agent_count} agents. {total_issues_found} issues found.")
```

## Save Checkpoint

Persist explorer reports so they survive context compaction.

```
write_file(".neuraltree/explorer_reports.json", json.dumps({
    "timestamp": now_iso8601(),
    "strategy": strategy,
    "agent_count": explore_agent_count,
    "total_files_explored": total_files_explored,
    "total_issues_found": total_issues_found,
    "reports": explorer_reports,
}, indent=2))
emit("Checkpoint saved: .neuraltree/explorer_reports.json")
```

**If resuming:** Check for `.neuraltree/explorer_reports.json`. If < 1 hour
old, LOAD it instead of re-exploring.

**Proceed to Map (read `sections/map.md`).**
