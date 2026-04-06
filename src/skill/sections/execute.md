# Execute Phase — Apply Changes in Sandbox

> Sandbox first. Measure after. User confirms.

**Input:** `approved_actions` from Plan phase.
**Output:** Changes applied to sandbox, ready for verification.

## Step 1: Create Sandbox

```
sandbox = neuraltree_sandbox_create(project_root=".")
sandbox_root = sandbox["sandbox_path"]
```

## Step 2: Backup Affected Files

```
all_files = set()
for action in approved_actions:
    all_files.update(action["files"])
neuraltree_backup(files=sorted(all_files), project_root=sandbox_root)
```

## Step 3: Execute Actions

Process in order: wire first, then move, then split, then delete.

```
ACTION_ORDER = {"wire": 0, "add_frontmatter": 1, "add_index": 2, "move": 3, "split": 4, "shrink": 5, "delete": 6}
for action in sorted(approved_actions, key=lambda a: ACTION_ORDER[a["type"]]):
    emit(f"  Executing: {action['description']}")

    if action["type"] == "wire":
        for file in action["files"]:
            wire_result = neuraltree_wire(file_path=file, project_root=sandbox_root)
            apply_suggested_content(sandbox_root / file, wire_result["suggested_content"])

    elif action["type"] == "move":
        neuraltree_plan_move(
            source=action["source"],
            destination=action["destination"],
            project_root=sandbox_root,
        )

    elif action["type"] == "split":
        neuraltree_split_and_wire(
            target=action["file"],
            project_root=sandbox_root,
        )

    elif action["type"] == "shrink":
        neuraltree_shrink_and_wire(
            target=action["file"],
            sections_to_extract=action["sections"],
            project_root=sandbox_root,
        )

    elif action["type"] == "add_frontmatter":
        for file in action["files"]:
            update_frontmatter(sandbox_root / file, {
                "last_verified": today_iso8601(),
            })

    elif action["type"] == "add_index":
        neuraltree_generate_index(
            directory=action["directory"],
            project_root=sandbox_root,
        )
```

## Step 4: Re-index Viking

```
if not DEGRADED_MODE:
    modified_files = [f for a in approved_actions for f in a["files"]]
    neuraltree_viking_index(
        file_paths=modified_files,
        project_root=sandbox_root,
    )
```

## Step 5: Verify No Broken References

```
dead = neuraltree_find_dead(project_root=sandbox_root)
if dead["total_dead"] > 0:
    emit(f"WARNING: {dead['total_dead']} orphan files after execution")
    for df in dead["dead_files"]:
        emit(f"  - {df['path']}")
```

**Proceed to Verify (read `sections/verify.md`).**
