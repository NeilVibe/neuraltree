# Map Phase — Knowledge Map Synthesis

> Merge explorer reports into a single graph. See the whole picture.

**Input:** `explorer_reports` from Explore phase.
**Output:** `knowledge_map` saved to `.neuraltree/knowledge_map.json`.

## Step 1: Merge File Reports

```
files = {}
for report in explorer_reports:
    for file_report in report["files"]:
        path = file_report["path"]
        files[path] = file_report
```

## Step 2: Build Edge Graph

Edges come from three sources:

**A. Explicit references** (from explorer reports):
```
edges = []
for path, file_data in files.items():
    for ref in file_data.get("references_to", []):
        if ref in files:  # only edges to known files
            edges.append({
                "source": path,
                "target": ref,
                "type": "reference",
                "weight": 1.0,
            })
```

**B. Semantic similarity** (from shared concepts):
```
for path_a, data_a in files.items():
    concepts_a = set(data_a.get("key_concepts", []))
    for path_b, data_b in files.items():
        if path_a >= path_b:
            continue
        concepts_b = set(data_b.get("key_concepts", []))
        overlap = concepts_a & concepts_b
        if len(overlap) >= 2:
            jaccard = len(overlap) / len(concepts_a | concepts_b)
            if jaccard > 0.3:
                edges.append({
                    "source": path_a,
                    "target": path_b,
                    "type": "semantic",
                    "weight": round(jaccard, 3),
                    "shared_concepts": sorted(overlap),
                })
```

**C. Directory co-location** (files in same directory):
```
from collections import defaultdict
dir_groups = defaultdict(list)
for path in files:
    dir_groups[os.path.dirname(path) or "."].append(path)

for dir_path, members in dir_groups.items():
    if len(members) > 1:
        for i, a in enumerate(members):
            for b in members[i+1:]:
                # Only add if no stronger edge exists
                has_edge = any(
                    (e["source"] == a and e["target"] == b) or
                    (e["source"] == b and e["target"] == a)
                    for e in edges
                )
                if not has_edge:
                    edges.append({
                        "source": a, "target": b,
                        "type": "co-located",
                        "weight": 0.5,
                    })
```

## Step 3: Detect Concept Clusters

Group files by shared concepts using a simple greedy algorithm:

```
# Start with files sorted by concept count
unclustered = set(files.keys())
clusters = []

while unclustered:
    # Pick the file with most concepts as seed
    seed = max(unclustered, key=lambda p: len(files[p].get("key_concepts", [])))
    cluster_files = {seed}
    seed_concepts = set(files[seed].get("key_concepts", []))

    # Add files that share 2+ concepts with the cluster
    for other in list(unclustered):
        if other == seed:
            continue
        other_concepts = set(files[other].get("key_concepts", []))
        if len(seed_concepts & other_concepts) >= 2:
            cluster_files.add(other)
            seed_concepts |= other_concepts

    # Name the cluster from top concepts
    from collections import Counter
    concept_counts = Counter()
    for f in cluster_files:
        concept_counts.update(files[f].get("key_concepts", []))
    top_concepts = [c for c, _ in concept_counts.most_common(3)]
    cluster_name = "_".join(top_concepts[:2])

    clusters.append({
        "name": cluster_name,
        "concept": ", ".join(top_concepts),
        "files": sorted(cluster_files),
    })
    unclustered -= cluster_files
```

## Step 4: Collect Issues

Merge all issues from explorers + add graph-derived issues:

```
issues = []

# From explorers
for path, data in files.items():
    for issue_desc in data.get("issues", []):
        issues.append({
            "type": classify_issue(issue_desc),
            "file": path,
            "description": issue_desc,
            "severity": "medium",
        })

# Graph-derived: orphan files (no edges)
connected = {e["source"] for e in edges} | {e["target"] for e in edges}
for path in files:
    if path not in connected:
        issues.append({
            "type": "orphan",
            "file": path,
            "description": f"{path} has no connections to any other file",
            "severity": "high",
        })

# Graph-derived: clusters spanning 3+ directories
for cluster in clusters:
    dirs_in_cluster = {os.path.dirname(f) for f in cluster["files"]}
    if len(dirs_in_cluster) >= 3:
        issues.append({
            "type": "scattered_cluster",
            "cluster": cluster["name"],
            "description": f"Cluster '{cluster['name']}' spans {len(dirs_in_cluster)} directories: {sorted(dirs_in_cluster)}",
            "severity": "medium",
        })
```

## Step 5: Compute Stats and Save

```
import statistics
project_name = os.path.basename(os.path.abspath("."))
file_sizes = [d.get("size_lines", 0) for d in files.values()]

knowledge_map = {
    "version": 2,
    "timestamp": now_iso8601(),
    "project_name": project_name,
    "files": files,
    "edges": edges,
    "clusters": clusters,
    "issues": issues,
    "stats": {
        "total_files": len(files),
        "total_edges": len(edges),
        "total_clusters": len(clusters),
        "total_issues": len(issues),
        "avg_file_size": round(statistics.mean(file_sizes)) if file_sizes else 0,
        "median_file_size": round(statistics.median(file_sizes)) if file_sizes else 0,
        "max_depth": max(f.count("/") for f in files) if files else 0,
    },
}

neuraltree_knowledge_map(action="save", knowledge_map=knowledge_map, project_root=".")
emit(f"Phase 2/6: Knowledge map built — {len(files)} files, {len(edges)} edges, {len(clusters)} clusters, {len(issues)} issues")
```

**Proceed to Analyze (read `sections/analyze.md`).**
