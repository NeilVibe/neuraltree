# Understand Phase — Explore + Map

> Read deeply. Build the graph. Understand before fixing.

**Input:** `scan_result`, `agent_count`, `knowledge_files`, `dirs`.
**Output:** `knowledge_map` saved to `.neuraltree/knowledge_map.json`.

This phase combines exploration (parallel agent reading) with map synthesis
(knowledge graph construction) into a single "understand" step.

## Step 1: Assign Directory Slices

Divide directories among agents. Each agent gets a slice of the project
to read deeply. Balance by file count, not directory count.

```
# Sort dirs by file count (largest first)
dir_file_counts = {}
for f in knowledge_files:
    d = os.path.dirname(f) or "."
    dir_file_counts.setdefault(d, []).append(f)

# Greedy assignment: give largest unassigned dir to least-loaded agent
agent_slices = [[] for _ in range(agent_count)]
agent_loads = [0] * agent_count

for d, files in sorted(dir_file_counts.items(), key=lambda x: -len(x[1])):
    lightest = agent_loads.index(min(agent_loads))
    agent_slices[lightest].append({"dir": d, "files": files})
    agent_loads[lightest] += len(files)
```

## Step 2: Launch Explorer Agents

Launch all agents in parallel using the Agent tool. Each agent receives:
1. The list of files to read
2. The structured report format to follow
3. Instructions to read each file FULLY and report honestly

**Explorer Agent Prompt Template:**

```
You are an explorer agent for NeuralTree. Your job is to READ every file
in your assigned slice and report what you find.

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

Launch all agents in a SINGLE message (parallel execution):

```
for i, slice in enumerate(agent_slices):
    file_list = "\n".join(f"  - {f}" for d in slice for f in d["files"])
    Agent(
        prompt=EXPLORER_PROMPT.format(file_list=file_list),
        description=f"Explorer {i+1}/{agent_count}",
        subagent_type="Explore",
    )
```

## Step 3: Collect Reports

Wait for all agents to complete. Parse each agent's JSON report.

```
explorer_reports = []
for agent_result in agent_results:
    report = parse_json(agent_result)
    explorer_reports.append(report)

total_files_explored = sum(len(r["files"]) for r in explorer_reports)
total_issues_found = sum(
    len(f.get("issues", [])) for r in explorer_reports for f in r["files"]
)
emit(f"Phase 1/5 (explore): {total_files_explored} files read by {agent_count} agents. {total_issues_found} issues found.")
```

## Step 4: Compute Semantic Edges via Viking

For each file in the explorer reports, query Viking with the file's topic
as search text. The top results that are OTHER known files (not itself)
become semantic edges.

```
semantic_edges = []
all_file_paths = set()
for report in explorer_reports:
    for f in report["files"]:
        all_file_paths.add(f["path"])

queries = []
for report in explorer_reports:
    for f in report["files"]:
        queries.append({"text": f["topic"], "source_file": f["path"]})

# Call Viking with all file topics as queries
precision_result = neuraltree_precision(
    queries=[{"text": q["text"]} for q in queries],
    project_root=".",
    limit=3,
)

# For each query result, find matches that are known project files
for i, qr in enumerate(precision_result["query_results"]):
    source_file = queries[i]["source_file"]
    for hit in qr.get("judgments", []):
        # Viking URIs look like: viking://resources/neuraltree/CLAUDE.md/chunk_abc123/...
        # Match against known file paths using the URI's path component
        uri = hit["uri"]
        matched_path = None
        for known_path in all_file_paths:
            # Check if the known filename appears in the Viking URI
            basename = known_path.split("/")[-1]
            if basename in uri and known_path != source_file:
                matched_path = known_path
                break
        if matched_path:
            semantic_edges.append({
                "source": source_file,
                "target": matched_path,
                "weight": round(hit["score"], 3),
                "reason": f"Viking similarity: {hit['score']:.3f}",
            })
```

**If Viking is unavailable (DEGRADED_MODE):** Skip this step. Pass
`semantic_edges=None` to the build action. The map will have reference
and co-location edges only.

## Step 5: Build the Knowledge Map

Pass explorer reports AND Viking semantic edges to the `build` action.
The tool deterministically computes:
- **Reference edges** from explicit `references_to` in each file report
- **Semantic edges** from Viking (passed in via `semantic_edges` parameter)
- **Co-location edges** for files in the same directory (only if no stronger edge exists)
- **Greedy concept clusters** (seed by most concepts, expand by 2+ shared)
- **Graph-derived issues** (orphan files with no edges, scattered clusters spanning 3+ dirs)
- **Explorer-reported issues** propagated from file reports
- **Stats** (totals, averages, median, max depth)

```
result = neuraltree_knowledge_map(
    action="build",
    project_root=".",
    explorer_reports=explorer_reports,
    semantic_edges=semantic_edges,
)
# result contains: saved (path), knowledge_map (full map), stats (summary)
```

The tool saves the map to `.neuraltree/knowledge_map.json` automatically.

**If `result` contains an `"error"` key:** Stop and report the error to the user. Do NOT proceed to Analyze.

**If `result["warnings"]` is non-empty:** Show warnings to the user (e.g., skipped paths, dropped reports) but continue.

## Step 6: Emit Summary

```
stats = result["stats"]
emit(f"Phase 1/5 (map): Knowledge map built — {stats['total_files']} files, "
     f"{stats['total_edges']} edges, {stats['total_clusters']} clusters, "
     f"{stats['total_issues']} issues")
```

## What the Tool Computes (for reference — you do NOT need to do this)

| Computation | Algorithm | Threshold |
|-------------|-----------|-----------|
| Reference edges | For each file's `references_to`, create edge if target is a known file | - |
| Semantic edges | Pre-computed by Viking/Model2Vec, passed via `semantic_edges` param | caller decides |
| Co-location edges | Files in same directory, only if no reference or semantic edge exists | weight = 0.5 |
| Clusters | Greedy: seed = file with most concepts, expand by 2+ shared concepts | overlap >= 2 |
| Orphans | Files with zero edges (not in any edge source or target) | severity: high |
| Scattered clusters | Clusters spanning 3+ directories | severity: medium |

**Proceed to Analyze (read `sections/analyze.md`).**
