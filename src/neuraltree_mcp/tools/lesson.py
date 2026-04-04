"""neuraltree_lesson_match and neuraltree_lesson_add — Incident memory / lessons layer."""
from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import FastMCP

from neuraltree_mcp.text_utils import (
    extract_keywords,
    jaccard,
    extract_backtick_paths,
    walk_project_files,
    NON_LESSON_HEADINGS,
)
from neuraltree_mcp.validation import validate_project_root, validate_within_root

DOMAIN_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$')

REQUIRED_KEYS = {"symptom", "root_cause", "fix"}
OPTIONAL_KEYS = {"chain", "key_file", "lesson", "commit"}
ALL_KEYS = REQUIRED_KEYS | OPTIONAL_KEYS
MAX_FIELD_LENGTH = 2000
MAX_LESSON_FILE_BYTES = 512 * 1024  # 512KB per domain file
MAX_SYMPTOMS = 50
MAX_SYMPTOM_LENGTH = 1000


def _find_lessons_dir(root: Path) -> Path | None:
    """Find the lessons directory under root."""
    for candidate in ["memory/lessons", "lessons"]:
        d = root / candidate
        if d.is_dir():
            return d
    return None


def _parse_lesson_entries(content: str) -> list[dict]:
    """Parse lesson entries from a domain file.

    Splits on ## headings, skips non-lesson headings (Related, Docs, Content, Rules).
    Extracts **Bold:** value fields from bullet lines.
    """
    entries = []
    current_heading = None
    current_lines: list[str] = []

    for line in content.splitlines():
        if line.startswith("## "):
            # Flush previous entry
            if current_heading is not None:
                entry = _extract_fields(current_heading, current_lines)
                if entry:
                    entries.append(entry)
            heading_text = line[3:].strip()
            # Skip non-lesson headings
            heading_lower = heading_text.lower().split("(")[0].strip()
            if heading_lower in NON_LESSON_HEADINGS:
                current_heading = None
                current_lines = []
            else:
                current_heading = heading_text
                current_lines = []
        elif current_heading is not None:
            current_lines.append(line)

    # Flush last entry
    if current_heading is not None:
        entry = _extract_fields(current_heading, current_lines)
        if entry:
            entries.append(entry)

    return entries


def _extract_fields(heading: str, lines: list[str]) -> dict | None:
    """Extract structured fields from bullet lines under a heading."""
    fields: dict[str, str] = {}
    for line in lines:
        m = re.match(r'^-\s+\*\*(.+?):\*\*\s*(.+)$', line.strip())
        if m:
            key = m.group(1).lower().replace(" ", "_")
            value = m.group(2).strip().strip('`')
            fields[key] = value

    if not fields:
        return None

    return {"heading": heading, "fields": fields}


def _validate_domain(domain: str) -> str:
    """Validate and normalize domain name."""
    if not domain or not domain.strip():
        raise ValueError("domain must not be empty")
    domain = domain.lower().strip()
    if not DOMAIN_RE.match(domain):
        raise ValueError(
            f"Invalid domain: {domain!r}. "
            "Must be alphanumeric with hyphens/underscores, 1-64 chars."
        )
    return domain


def _validate_lesson(lesson: dict) -> dict:
    """Validate lesson dict schema."""
    if not isinstance(lesson, dict):
        raise ValueError("lesson must be a dict")

    unknown = set(lesson.keys()) - ALL_KEYS
    if unknown:
        raise ValueError(f"Unknown lesson keys: {unknown}")

    missing = REQUIRED_KEYS - set(lesson.keys())
    if missing:
        raise ValueError(f"Missing required keys: {missing}")

    for key, value in lesson.items():
        if not isinstance(value, str):
            raise ValueError(f"Lesson field {key!r} must be a string")
        if len(value) > MAX_FIELD_LENGTH:
            raise ValueError(f"Lesson field {key!r} exceeds {MAX_FIELD_LENGTH} chars")
        # Frontmatter injection prevention (normalize \r\n before checking)
        normalized = value.replace("\r\n", "\n").replace("\r", "\n")
        if normalized.lstrip().startswith("---") or "\n---\n" in normalized:
            raise ValueError(f"Lesson field {key!r} contains frontmatter delimiter")

    return lesson


def _get_commit_hash(root: Path, warnings: list[str] | None = None) -> str | None:
    """Auto-detect git commit hash. Returns None on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=str(root), timeout=10,
        )
        if result.returncode == 0:
            commit = result.stdout.strip()[:12]
            if re.match(r'^[0-9a-f]{7,40}$', commit):
                return commit
        if warnings is not None:
            warnings.append(f"git rev-parse HEAD failed (rc={result.returncode})")
    except (subprocess.SubprocessError, OSError) as e:
        if warnings is not None:
            warnings.append(f"git commit detection failed: {e}")
    return None


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def neuraltree_lesson_match(symptoms: list[str], project_root: str = ".") -> dict:
        """Search lessons/ for matching past incidents.

        Batch operation: accepts multiple symptom descriptions, returns
        per-symptom match results. Uses keyword extraction + Jaccard similarity.
        Skips non-lesson headings (## Related, ## Docs, etc.).

        Args:
            symptoms: List of symptom descriptions to search for.
            project_root: Project root directory.

        Returns:
            dict with matches (per-symptom), total_matches, warnings.
        """
        warnings: list[str] = []

        try:
            root = validate_project_root(project_root)
        except ValueError as e:
            return {"matches": [], "total_matches": 0, "warnings": [], "error": str(e)}

        # Input validation
        if len(symptoms) > MAX_SYMPTOMS:
            symptoms = symptoms[:MAX_SYMPTOMS]
            warnings.append(f"Capped to {MAX_SYMPTOMS} symptoms")

        symptoms = [s[:MAX_SYMPTOM_LENGTH] for s in symptoms]

        # Find lesson files
        lessons_dir = _find_lessons_dir(root)
        if lessons_dir is None:
            return {
                "matches": [{"symptom_query": s, "lessons": []} for s in symptoms],
                "total_matches": 0,
                "warnings": warnings,
            }

        # Parse all lesson entries from all domain files
        all_entries: list[dict] = []  # {heading, fields, domain, file}
        lesson_files = walk_project_files(lessons_dir, {".md"})

        for lf in lesson_files:
            if lf.name == "_INDEX.md":
                continue
            try:
                validate_within_root(lf, root)
            except ValueError:
                warnings.append(f"Skipping {lf}: escapes project root")
                continue
            try:
                content = lf.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                warnings.append(f"Could not read {lf}: {e}")
                continue

            domain = lf.stem
            rel_file = os.path.relpath(lf, root)
            entries = _parse_lesson_entries(content)
            for entry in entries:
                entry["domain"] = domain
                entry["file"] = rel_file
                all_entries.append(entry)

        # Match each symptom against all entries
        matches_out: list[dict] = []
        total_matches = 0

        for symptom in symptoms:
            symptom_kw = extract_keywords(symptom, min_freq=1)
            scored: list[dict] = []

            for entry in all_entries:
                heading = entry["heading"]
                fields = entry["fields"]
                # Build search text from heading + symptom + root_cause
                search_text = heading + " " + fields.get("symptom", "") + " " + fields.get("root_cause", "")
                entry_kw = extract_keywords(search_text, min_freq=1)

                score = jaccard(symptom_kw, entry_kw)

                # Boost: symptom keyword appears in heading
                heading_lower = heading.lower()
                if any(kw in heading_lower for kw in symptom_kw):
                    score += 0.15

                score = min(1.0, score)

                if score > 0.2:
                    scored.append({
                        "heading": heading,
                        "domain": entry["domain"],
                        "file": entry["file"],
                        "fields": fields,
                        "score": round(score, 3),
                    })

            scored.sort(key=lambda x: x["score"], reverse=True)
            top = scored[:3]
            total_matches += len(top)

            matches_out.append({
                "symptom_query": symptom,
                "lessons": top,
            })

        return {
            "matches": matches_out,
            "total_matches": total_matches,
            "warnings": warnings,
        }

    @mcp.tool()
    def neuraltree_lesson_add(domain: str, lesson: dict, project_root: str = ".") -> dict:
        """Add a lesson entry to a domain file.

        Creates the domain file and lessons/ directory if they don't exist.
        Checks for duplicates, validates schema, enforces file size cap.
        Uses file-level ## Docs section for scanner compatibility.

        Args:
            domain: Domain name (alphanumeric, hyphens, underscores, 1-64 chars).
            lesson: Dict with required keys: symptom, root_cause, fix.
                    Optional: chain, key_file, lesson, commit.
            project_root: Project root directory.

        Returns:
            dict with added, file, domain, duplicate, commit, warnings.
        """
        warnings: list[str] = []

        try:
            root = validate_project_root(project_root)
        except ValueError as e:
            return {"added": False, "error": str(e), "warnings": []}

        # Validate domain
        try:
            domain = _validate_domain(domain)
        except ValueError as e:
            return {"added": False, "error": str(e), "warnings": []}

        # Validate lesson schema
        try:
            lesson = _validate_lesson(lesson)
        except ValueError as e:
            return {"added": False, "error": str(e), "warnings": []}

        # Find or create lessons directory
        lessons_dir = _find_lessons_dir(root)
        if lessons_dir is None:
            # Create under memory/lessons/ if memory/ exists, else lessons/
            if (root / "memory").is_dir():
                lessons_dir = root / "memory" / "lessons"
            else:
                lessons_dir = root / "lessons"

        lessons_dir.mkdir(parents=True, exist_ok=True)
        try:
            validate_within_root(lessons_dir, root)
        except ValueError:
            return {"added": False, "error": "Lessons directory escapes project root", "warnings": []}

        # Construct file path with defense-in-depth validation
        lesson_file = lessons_dir / f"{domain}.md"
        try:
            validate_within_root(lesson_file, root)
        except ValueError:
            return {"added": False, "error": f"Domain path escapes project root: {domain}", "warnings": []}

        # File size cap
        if lesson_file.exists():
            try:
                if lesson_file.stat().st_size > MAX_LESSON_FILE_BYTES:
                    return {"added": False, "error": f"Domain file exceeds {MAX_LESSON_FILE_BYTES // 1024}KB limit",
                            "warnings": []}
            except OSError as e:
                warnings.append(f"Could not stat {lesson_file}: {e}")

        # Read existing content for duplicate check
        existing_content = ""
        if lesson_file.exists():
            try:
                existing_content = lesson_file.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                warnings.append(f"Could not read {lesson_file}: {e}")

        # Duplicate check: >80% word overlap with existing symptom headings
        new_symptom_kw = extract_keywords(lesson["symptom"], min_freq=1)
        existing_entries = _parse_lesson_entries(existing_content)
        for entry in existing_entries:
            # Strip date/phase suffix from heading for comparison
            clean_heading = entry["heading"].split("(")[0].strip()
            existing_kw = extract_keywords(clean_heading, min_freq=1)
            if new_symptom_kw and existing_kw:
                if jaccard(new_symptom_kw, existing_kw) > 0.8:
                    return {
                        "added": False,
                        "file": os.path.relpath(lesson_file, root),
                        "domain": domain,
                        "duplicate": True,
                        "commit": None,
                        "warnings": [f"Duplicate detected: >80% overlap with '{entry['heading']}'"],
                    }

        # Auto-detect commit hash if not provided
        commit = lesson.get("commit") or _get_commit_hash(root, warnings)

        # Build the lesson entry
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        lines = [f"\n## {lesson['symptom']} ({today})"]
        lines.append(f"- **Symptom:** {lesson['symptom']}")
        lines.append(f"- **Root cause:** {lesson['root_cause']}")
        if lesson.get("chain"):
            lines.append(f"- **Chain:** {lesson['chain']}")
        lines.append(f"- **Fix:** {lesson['fix']}")
        if lesson.get("key_file"):
            lines.append(f"- **Key file:** `{lesson['key_file']}`")
        if lesson.get("lesson"):
            lines.append(f"- **Lesson:** {lesson['lesson']}")
        if commit:
            lines.append(f"- **Commit:** {commit}")

        new_entry = "\n".join(lines) + "\n"
        key_file = lesson.get("key_file")

        # Phase 1: Build updated file content — insert entry before file-level sections
        try:
            if existing_content:
                # Find insertion point: before ## Related or ## Docs
                insert_before = None
                for section in ["## Related", "## Docs"]:
                    for m in re.finditer(rf'^{re.escape(section)}\b', existing_content, re.MULTILINE):
                        pos = m.start()
                        if insert_before is None or pos < insert_before:
                            insert_before = pos
                        break

                if insert_before is not None:
                    updated = existing_content[:insert_before] + new_entry + "\n" + existing_content[insert_before:]
                else:
                    updated = existing_content.rstrip() + "\n" + new_entry
            else:
                # New file — add frontmatter
                updated = (
                    f"---\nname: {domain.title()} Lessons\n"
                    f"description: Past {domain} issues\n"
                    f"type: reference\nlast_verified: {today}\n---\n"
                    + new_entry
                )

            # Phase 2: Ensure key_file is in ## Docs (one place, one check)
            if key_file:
                docs_line = f"- `{key_file}` — implementation target"
                if "## Docs" in updated:
                    if docs_line not in updated:
                        updated = updated.rstrip() + "\n" + docs_line + "\n"
                else:
                    updated = updated.rstrip() + f"\n\n## Docs\n{docs_line}\n"

            # Check post-write size
            if len(updated.encode("utf-8")) > MAX_LESSON_FILE_BYTES:
                return {"added": False, "error": f"Would exceed {MAX_LESSON_FILE_BYTES // 1024}KB limit",
                        "warnings": warnings}

            lesson_file.write_text(updated, encoding="utf-8")
        except OSError as e:
            return {"added": False, "error": f"Failed to write {lesson_file}: {e}", "warnings": warnings}

        # Update _INDEX.md if domain is new
        index_file = lessons_dir / "_INDEX.md"
        try:
            if index_file.exists():
                index_content = index_file.read_text(encoding="utf-8", errors="replace")
            else:
                index_content = (
                    "---\nname: Lessons Index\ntype: reference\n"
                    f"last_verified: {today}\n---\n\n"
                )

            domain_link = f"[{domain.title()}]({domain}.md)"
            if domain_link not in index_content:
                index_content = index_content.rstrip() + f"\n- {domain_link} — {domain} lessons\n"
                index_file.write_text(index_content, encoding="utf-8")
        except OSError as e:
            warnings.append(f"Could not update _INDEX.md: {e}")

        rel_file = os.path.relpath(lesson_file, root)
        return {
            "added": True,
            "file": rel_file,
            "domain": domain,
            "duplicate": False,
            "commit": commit,
            "warnings": warnings,
        }
