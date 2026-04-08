---
name: Wiki-Lint Lessons
description: Past wiki-lint issues
type: reference
last_verified: 2026-04-08
---

## wiki_lint reports broken links inside markdown code block templates as real broken links (2026-04-08)
- **Symptom:** wiki_lint reports broken links inside markdown code block templates as real broken links
- **Root cause:** wiki_lint regex extracts links from ALL lines including those inside fenced code blocks (```). Template examples like [Related Page 1](related-page-1.md) inside a code fence are counted as broken links.
- **Chain:** compile.md template example → wiki_lint _extract_links → regex matches inside code block → 2 false broken links
- **Fix:** Add code fence detection to _extract_links in wiki_lint.py — skip lines between ``` markers. This is a false positive pattern that will recur on any project with documentation templates.
- **Key file:** `src/neuraltree_mcp/tools/wiki_lint.py`
- **Commit:** f2419f7a0806

## Docs
- `src/neuraltree_mcp/tools/wiki_lint.py` — implementation target
