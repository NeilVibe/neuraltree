# Edge Cases & Error Recovery

> Things go wrong. The skill must handle every failure gracefully — never crash, never corrupt, never leave the project worse than it found it.

## Without Viking (DEGRADED_MODE)

1. Warn: `"Viking not found. Operating in structure-only mode (4 of 6 metrics)."`
2. Skip: Precision@3 evaluation, Viking re-indexing
3. Reweight: `structure_reachability (0.45), dead_neuron_ratio (0.25), freshness (0.20), trunk_pressure (0.10)`
4. Reclassify: `EMBEDDING_GAP -> SYNAPSE_GAP` (fix via wiring instead of indexing)
5. Cap: Flow Score capped at 0.75

## Bootstrap: No CLAUDE.md

1. Check `README.md` as provisional trunk
2. No README: fall back to directory structure + filenames from `neuraltree_scan()`
3. Create minimal CLAUDE.md: project name, directory listing, key files
4. Proceed with full pipeline — low score is expected

## Bootstrap: No Git

- `neuraltree_backup()` falls back to file copy (automatic)
- `neuraltree_sandbox_create()` falls back to rsync (automatic)
- Warn: `"No git detected. Backups use file copy."`

## Bootstrap: Empty Project

- `neuraltree_scan()` returns minimal file list — expected
- Flow Score ~0.0 — expected and normal
- AutoLoop creates initial structure: CLAUDE.md, directories, wiring
- Emit: `"Empty project detected. Creating initial structure..."`

## Monorepo Detection

- Scope to cwd only — do not scan entire repository
- Flag cross-boundary references but do not follow them
- Run NeuralTree separately in each subproject

## Concurrent Run Protection

- Lock at `.neuraltree/.lock` (ISO 8601 timestamp)
- Stale lock (>1 hour): auto-remove with warning
- Active lock: abort immediately
- ALL exit paths must release lock (try/finally)

## Scale Limits

| Parameter | Limit |
|-----------|-------|
| File scan | 10,000 files |
| Test queries | 50 max |
| AutoLoop iterations | 8 max |
| Leaf file size | 500 lines (FOCUS_GAP) |
| Trunk size | 100 lines (TRUNK_PRESSURE) |
| Backup directory | 100 MB |

## Error Recovery

| Error | Recovery |
|-------|----------|
| MCP crash mid-loop | Release lock, report partial results |
| Viking timeout | Retry once, then switch to DEGRADED_MODE |
| File permission denied | Skip file, continue with rest |
| Disk full during backup | Abort, release lock |
| LLM judge returns garbage | Default to NO (conservative) |
| State file corrupted | Re-initialize from defaults |
| calibration.json corrupted | Delete, restart with accuracy=0.5 |
| queries.json corrupted | Delete, regenerate on next run |

**Cardinal rule:** Never leave the lock held. Never leave the project modified without a backup. Never silently swallow an error.
