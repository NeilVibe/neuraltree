# Explore Phase

> Read deeply. Report honestly. Every file gets understood, not just counted.

**Input:** `scan_result`, `agent_count`, `knowledge_files`, `dirs`.
**Output:** `explorer_reports` (list of per-agent structured reports).

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
emit(f"Phase 1/6: Explored {total_files_explored} files with {agent_count} agents. {total_issues_found} issues found.")
```

**Proceed to Map (read `sections/map.md`).**
