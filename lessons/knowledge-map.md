---
name: Knowledge-Map Lessons
description: Past knowledge-map issues
type: reference
last_verified: 2026-04-08
---

## knowledge_map build action returns 0 files when explorer_reports use 'file' key instead of expected format (2026-04-08)
- **Symptom:** knowledge_map build action returns 0 files when explorer_reports use 'file' key instead of expected format
- **Root cause:** The knowledge_map build action expects explorer reports with specific field names that don't match the format we constructed manually. The tool silently produces an empty map instead of erroring on unrecognized fields.
- **Chain:** Phase 3 Map → neuraltree_knowledge_map(action=build) → explorer_reports format mismatch → 0 files → overwrites existing valid map
- **Fix:** Investigate the exact explorer_report format expected by knowledge_map build action (check knowledge_map.py source). The reports need to match what the Explore phase agents produce, not a manually constructed dict.
- **Key file:** `src/neuraltree_mcp/tools/knowledge_map.py`
- **Commit:** f2419f7a0806

## Docs
- `src/neuraltree_mcp/tools/knowledge_map.py` — implementation target
