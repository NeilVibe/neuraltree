# Compile Phase — Build the Wiki

> Raw sources → compiled wiki pages. Knowledge compounds, never re-derived.

**Input:** `knowledge_map` from Map phase, `index_results` from Index phase.
**Output:** `.neuraltree/wiki/` — structured, interlinked wiki pages.

This is the Karpathy LLM-Wiki pattern: instead of re-discovering knowledge
from raw files every session, compile it once into a persistent wiki.
The wiki is a compounding artifact — it gets richer with every run.

## Step 1: Check Existing Wiki

```
wiki_state = neuraltree_wiki_read(project_root=".")
```

If wiki exists and has pages, this is an UPDATE run (merge new knowledge).
If no wiki exists, this is a FRESH COMPILE (build from scratch).

## Step 2: Identify What to Compile

From the knowledge map, extract concept clusters. Each cluster becomes
a wiki page. The goal: one page per concept, not one page per file.

**Sources for compilation:**
- Concept clusters from `knowledge_map.clusters[]`
- Entity pages for key files (CLAUDE.md, MEMORY.md, architecture docs)
- Synthesis pages for cross-cutting concerns (auth, testing, deployment)

**Scale-aware page count:**
```
if total_kb_files < 30:    max_pages = 5
elif total_kb_files < 100:  max_pages = 15
elif total_kb_files < 300:  max_pages = 30
elif total_kb_files < 1000: max_pages = 50
else:                       max_pages = 80
```

## Step 3: Compile Each Page

For each concept cluster or topic:

1. **Read the source files** in the cluster (use Read tool, NOT Viking — you want full content)
2. **Synthesize** the knowledge: extract key facts, decisions, patterns, relationships
3. **Write the wiki page** with this structure:

```markdown
---
name: {Topic Name}
description: {One-line summary of what this page covers}
source_count: {N}
last_compiled: {today_iso8601()}
---

# {Topic Name}

{2-3 sentence overview of this concept/entity}

## Key Facts

- {Fact 1 — with source file reference}
- {Fact 2}
- ...

## How It Works

{Deeper explanation if needed — architecture, flow, decisions}

## Sources

- `{source_file_1}` — {what it contributed}
- `{source_file_2}` — {what it contributed}

## Related

- [{Related Page 1}](related-page-1.md) — {why related}
- [{Related Page 2}](related-page-2.md) — {why related}
```

4. **Save via tool:**
```
neuraltree_compile(
    topic="{Topic Name}",
    content=page_content,
    sources=[list of source paths],
    project_root=".",
)
```

The tool handles: file writing, index update, log append.

## Step 4: Compile the Overview Page

Every wiki needs an overview — a single page that summarizes the entire
project and links to all major topic pages. This is the wiki's trunk.

```
neuraltree_compile(
    topic="Overview",
    content=overview_content,
    sources=["CLAUDE.md", "README.md"],
    project_root=".",
)
```

The overview should answer: "What is this project, what are its major
components, and where do I find information about each?"

## Step 5: Cross-Link Pages

After all pages are compiled, review the wiki index and ensure
every page has `## Related` links to 2-4 other wiki pages.
The 0-1-2 hop rule applies: any wiki page reachable from the
overview in at most 2 hops.

## Step 6: Emit Summary

```
wiki_state = neuraltree_wiki_read(project_root=".")
emit(f"Phase 4/8: Wiki compiled — {wiki_state['page_count']} pages in .neuraltree/wiki/")
```

**If updating an existing wiki:** Report pages added, updated, unchanged.

**Proceed to Analyze (read `sections/analyze.md`).**
