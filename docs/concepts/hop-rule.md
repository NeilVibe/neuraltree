---
project: neuraltree
type: concept
---

# 0-1-2 Hop Rule

**Any information reachable in max 2 tool calls.**

This rule defines the maximum acceptable retrieval distance in a well-organized project:

- **0 hops:** Agent already knows it (in CLAUDE.md, active context)
- **1 hop:** One tool call finds it (semantic search, index lookup, direct file read)
- **2 hops:** One tool call finds a pointer, second call reads the content

## Why 2 Hops Maximum

Beyond 2 hops, agents lose context, make wrong turns, or give up. Two hops is the practical limit for reliable information retrieval by AI coding agents.

## How It's Measured

The [Flow Score](flow-score.md) includes a `discoverability` component that tests whether key concepts are reachable within this limit using [Viking Semantic Search](viking-semantic-search.md).

## What Breaks It

- Deep folder nesting with no index files
- Documents that reference other documents without links
- Concepts defined only in conversation history, never written down
- Missing or stale knowledge maps

## Related

- [Artery Principle](artery-principle.md)
- [Flow Score](flow-score.md)
- [Knowledge Map](knowledge-map.md)
