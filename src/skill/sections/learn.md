# Learn Phase — Record What You Learned

> Fix a bug once, remember it forever. Knowledge compounds.

**Trigger:** `/neuraltree learn` after fixing a bug or discovering something worth remembering.
**Input:** The user just fixed something. You know the symptom, root cause, fix, and key file.
**Output:** Lesson recorded, wiki updated if warranted, Viking indexed, retrieval verified.

This is NOT a pipeline phase. It's a standalone subcommand that runs anytime.

---

## Step 1: Gather the Fix

Ask the user (or extract from conversation context) these fields:

| Field | Required | Description |
|-------|----------|-------------|
| `symptom` | YES | What went wrong — the observable behavior |
| `root_cause` | YES | Why it went wrong — the actual cause |
| `fix` | YES | What fixed it — the action taken |
| `domain` | YES | Category (e.g., `frontend-wiring`, `viking`, `auth`, `tmx`) |
| `chain` | no | The causal chain: A → B → C → symptom |
| `key_file` | no | The file that was changed to fix it |

If the conversation already contains all of this (you just helped fix the bug),
extract it directly — don't ask the user to repeat themselves.

## Step 2: Check for Duplicates

```
result = neuraltree_lesson_match(
    symptoms=["{symptom}"],
    project_root="."
)
```

If a match scores > 0.8, tell the user: "This looks like a duplicate of {existing lesson}. Add anyway?" If they say no, stop.

## Step 3: Record the Lesson

```
result = neuraltree_lesson_add(
    domain="{domain}",
    lesson={
        "symptom": "{symptom}",
        "root_cause": "{root_cause}",
        "fix": "{fix}",
        "chain": "{chain}",         # if available
        "key_file": "{key_file}"    # if available
    },
    project_root="."
)
```

Confirm: `Lesson added to {result.file}`.

## Step 4: Wiki Compilation (if warranted)

Check how many lessons exist in this domain:

```
# Read the domain file that was just updated
content = read_file(result.file)
# Count ## headings (each is a lesson entry)
```

**If 3+ lessons in the same domain**, compile a wiki page:

```
neuraltree_compile(
    topic="{Domain} Patterns",
    content="{synthesized page covering all lessons in this domain}",
    sources=["{result.file}"],
    project_root="."
)
```

The wiki page should synthesize patterns across lessons, not just list them.
"These 4 auth bugs all stem from the same JWT timing issue" > "Bug 1, Bug 2, Bug 3, Bug 4".

**If < 3 lessons**, skip compilation. Say: "Domain has {N} lesson(s) — will compile wiki page at 3."

## Step 5: Index into Viking

Index the new/updated files so they're semantically searchable:

```
files_to_index = [result.file]
# If a wiki page was compiled in Step 4, add it too
neuraltree_viking_index(
    file_paths=files_to_index,
    project_root="."
)
```

If Viking is unavailable (DEGRADED_MODE), skip with warning. Lessons still work without Viking — they're keyword-matched by `lesson_match`.

## Step 6: Verify Retrieval

Confirm the lesson is findable:

```
verify = neuraltree_lesson_match(
    symptoms=["{symptom}"],
    project_root="."
)
```

The just-added lesson MUST appear in results. If it doesn't, warn:
"Lesson was saved but retrieval failed — check keyword overlap in symptom field."

## Step 7: Emit Summary

```
/neuraltree learn — Complete
  Lesson: {symptom} (domain: {domain})
  File:   {result.file}
  Wiki:   {compiled / skipped (N lessons, need 3)}
  Viking: {indexed / unavailable}
  Verify: {found at score X / NOT FOUND}
```

---

## When to Use This

- After fixing any bug (the whole point)
- After discovering a non-obvious pattern ("oh, this framework always does X")
- After a debugging session reveals a causal chain worth remembering
- After a production incident is resolved

## When NOT to Use This

- Code patterns and conventions (those go in CLAUDE.md)
- Architecture decisions (those go in docs/)
- One-time setup steps (those go in README)
- Things that are obvious from reading the code
