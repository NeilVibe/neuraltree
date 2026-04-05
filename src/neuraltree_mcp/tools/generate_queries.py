"""neuraltree_generate_queries — Auto-generate test queries from project context."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from fastmcp import FastMCP

from neuraltree_mcp.text_utils import NON_LESSON_HEADINGS
from neuraltree_mcp.validation import validate_project_root, validate_within_root

# Max queries per individual strategy to prevent any single source from dominating
_MAX_PER_STRATEGY = 15


def _parse_table_column(content: str, header_pattern: str, col_index: int) -> list[str]:
    """Extract values from a markdown table column."""
    values = []
    in_table = False
    for line in content.splitlines():
        if header_pattern in line:
            in_table = True
            continue
        if in_table:
            if line.startswith("|---") or line.startswith("| ---"):
                continue
            if "|" in line:
                cells = [c.strip() for c in line.split("|")]
                # Remove empty first/last from leading/trailing pipes
                cells = [c for c in cells if c]
                if len(cells) > col_index:
                    val = cells[col_index].strip("*").strip()
                    if val:
                        values.append(val)
            else:
                in_table = False
    return values


def _parse_md_links(content: str) -> list[str]:
    """Extract link titles from markdown: - [Title](path)"""
    titles = []
    for m in re.finditer(r'-\s*\[([^\]]+)\]\(', content):
        titles.append(m.group(1))
    return titles


def _parse_headings(content: str) -> list[str]:
    """Extract meaningful ## and ### heading topics from markdown.

    Cleans headings by stripping emoji, normalizing ALL CAPS to title case,
    removing date/version suffixes, and skipping generic structural headings.
    Preserves technical punctuation (+, #, .) in terms like C++, C#, Node.js.
    """
    skip_headings = {
        "what is this", "current status", "architecture", "commands",
        "development protocol", "key principles", "table of contents",
        "dependencies", "project structure", "integration points",
        "specs & plans", "related", "docs", "overview", "contents",
    }
    topics = []
    for m in re.finditer(r'^#{2,3}\s+(.+)', content, re.MULTILINE):
        heading = m.group(1).strip().rstrip("#").strip()
        if heading.lower() in skip_headings:
            continue
        # Strip trailing date/version patterns BEFORE special char removal
        clean = re.sub(r'\s+\d{6,8}$', '', heading)
        clean = re.sub(r'\s+v\d+[\.\d]*$', '', clean, flags=re.IGNORECASE)
        clean = re.sub(r'^v\d+[\.\d]*\s+', '', clean, flags=re.IGNORECASE)
        # Replace structural separators with space, then strip remaining emoji/specials
        # but preserve technical punctuation (+, #, .)
        clean = re.sub(r'[/\\|&:()]', ' ', clean)
        clean = re.sub(r'[^\w\s\-\.+#]', '', clean)
        clean = re.sub(r'\s{2,}', ' ', clean).strip()
        if len(clean) < 4:
            continue
        # Normalize ALL CAPS to title case (keep ≤3 char acronyms like TM, ML, API)
        words = clean.split()
        normalized = []
        for w in words:
            alpha_chars = [c for c in w if c.isalpha()]
            if len(w) > 3 and alpha_chars and all(c.isupper() for c in alpha_chars):
                normalized.append(w.capitalize())
            else:
                normalized.append(w)
        clean = " ".join(normalized)
        # Truncate long headings at word boundary
        if len(clean) > 80:
            truncated = clean[:80].rsplit(" ", 1)[0]
            clean = truncated if len(truncated) >= 4 else clean[:80]
        if len(clean) < 4:
            continue
        topics.append(clean)
    return topics


def _parse_bold_terms(content: str) -> list[str]:
    """Extract **bold terms** that appear at start of bullet points."""
    terms = []
    for m in re.finditer(r'^[\-\*]\s+\*\*([^*]+)\*\*', content, re.MULTILINE):
        term = m.group(1).strip().rstrip(":").strip()
        if 4 <= len(term) <= 60:
            terms.append(term)
    return terms


def _dedup_queries(queries: list[dict]) -> list[dict]:
    """Remove queries with >80% word overlap."""
    result = []
    seen_word_sets: list[set[str]] = []

    for q in queries:
        words = set(q["text"].lower().split())
        is_dup = False
        for seen in seen_word_sets:
            if not words or not seen:
                continue
            overlap = len(words & seen) / max(len(words | seen), 1)
            if overlap > 0.8:
                is_dup = True
                break
        if not is_dup:
            result.append(q)
            seen_word_sets.append(words)
    return result


def _resolve_path(root: Path, user_path: str) -> Path:
    """Resolve a user-supplied path relative to root, with traversal protection."""
    p = Path(user_path)
    if p.is_absolute():
        raise ValueError(f"Path must be relative, got absolute: {user_path!r}")
    resolved = root / p
    validate_within_root(resolved, root)
    return resolved


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def neuraltree_generate_queries(
        project_root: str = ".",
        claude_md_path: str | None = None,
        memory_md_path: str | None = None,
        index_paths: list[str] | None = None,
        git_log_lines: int = 100,
        indexed_doc_count: int = 30,
    ) -> dict:
        """Auto-generate test queries from project context.

        Uses 8 strategies:
        1. CLAUDE.md glossary tables -> "What is {term}?"
        2. CLAUDE.md nav tables -> "How does {topic} work?"
        2b. CLAUDE.md headings (fallback) -> "How does {heading} work?"
        2c. CLAUDE.md bold terms (fallback) -> "What is {term}?"
        3. MEMORY.md links -> "What do we know about {title}?"
        3b. MEMORY.md headings (fallback) -> "What do we know about {heading}?"
        4. _INDEX.md entries -> "Where is {topic} documented?"
        5. git log subjects -> "What changed with {noun}?"

        Args:
            project_root: Project root directory.
            claude_md_path: Relative path to CLAUDE.md (auto-detected if None).
            memory_md_path: Relative path to MEMORY.md (auto-detected if None).
            index_paths: Relative paths to _INDEX.md files (auto-discovered if None).
            git_log_lines: Number of git log lines to parse.
            indexed_doc_count: Estimated indexed docs (for query count scaling).

        Returns:
            dict with queries, sources counts, and total.
        """
        try:
            root = validate_project_root(project_root)
        except (ValueError, OSError) as e:
            return {"queries": [], "sources": {}, "total": 0, "warnings": [], "error": str(e)}
        queries: list[dict] = []
        warnings: list[str] = []

        # Clamp git_log_lines
        git_log_lines = max(1, min(git_log_lines, 500))

        # Target query count: max(20, min(50, indexed_doc_count / 3))
        target_count = max(20, min(50, indexed_doc_count // 3))

        # Strategy 1+2: CLAUDE.md glossary and nav tables
        try:
            claude_path = _resolve_path(root, claude_md_path) if claude_md_path else root / "CLAUDE.md"
        except ValueError as e:
            warnings.append(f"Invalid claude_md_path: {e}")
            claude_path = root / "CLAUDE.md"

        if claude_path.exists():
            try:
                claude_content = claude_path.read_text(encoding="utf-8", errors="replace")
                claude_count = 0

                # Strategy 1: Glossary tables
                terms = _parse_table_column(claude_content, "Term", 0)
                for term in terms[:_MAX_PER_STRATEGY]:
                    queries.append({"text": f"What is {term}?", "source": "claude_md", "category": "what_is"})
                    claude_count += 1

                # Strategy 2: Nav table
                needs = _parse_table_column(claude_content, "Need", 0)
                for need in needs[:_MAX_PER_STRATEGY]:
                    queries.append({"text": f"How does {need} work?", "source": "claude_md", "category": "how_does"})
                    claude_count += 1

                # Strategy 2b: Headings (fallback when no tables found)
                if claude_count == 0:
                    headings = _parse_headings(claude_content)
                    for heading in headings[:_MAX_PER_STRATEGY]:
                        queries.append({"text": f"How does {heading} work?", "source": "claude_md", "category": "how_does"})
                        claude_count += 1

                # Strategy 2c: Bold terms (fallback when still no results)
                if claude_count == 0:
                    bold_terms = _parse_bold_terms(claude_content)
                    for term in bold_terms[:_MAX_PER_STRATEGY]:
                        queries.append({"text": f"What is {term}?", "source": "claude_md", "category": "what_is"})
                        claude_count += 1
            except OSError as e:
                warnings.append(f"Could not read CLAUDE.md: {e}")

        # Strategy 3: MEMORY.md links and headings
        try:
            mem_path = _resolve_path(root, memory_md_path) if memory_md_path else root / "memory" / "MEMORY.md"
        except ValueError as e:
            warnings.append(f"Invalid memory_md_path: {e}")
            mem_path = root / "memory" / "MEMORY.md"

        if mem_path.exists():
            try:
                mem_content = mem_path.read_text(encoding="utf-8", errors="replace")
                mem_count = 0

                titles = _parse_md_links(mem_content)
                for title in titles[:_MAX_PER_STRATEGY]:
                    queries.append({"text": f"What do we know about {title}?", "source": "memory", "category": "what_know"})
                    mem_count += 1

                # Fallback: extract ## headings if no links found
                if mem_count == 0:
                    headings = _parse_headings(mem_content)
                    for heading in headings[:_MAX_PER_STRATEGY]:
                        queries.append({"text": f"What do we know about {heading}?", "source": "memory", "category": "what_know"})
                        mem_count += 1
            except OSError as e:
                warnings.append(f"Could not read MEMORY.md: {e}")

        # Strategy 4: _INDEX.md files
        if index_paths:
            idx_files = []
            for p in index_paths:
                try:
                    idx_files.append(_resolve_path(root, p))
                except ValueError as e:
                    warnings.append(f"Invalid index path {p}: {e}")
        else:
            try:
                idx_files = list(root.rglob("_INDEX.md"))
            except OSError as e:
                warnings.append(f"Could not scan for _INDEX.md files: {e}")
                idx_files = []

        for idx_file in idx_files:
            if not idx_file.exists():
                continue
            try:
                idx_content = idx_file.read_text(encoding="utf-8", errors="replace")
                titles = _parse_md_links(idx_content)
                for title in titles[:_MAX_PER_STRATEGY]:
                    queries.append({"text": f"Where is {title} documented?", "source": "indexes", "category": "where_is"})
            except OSError as e:
                warnings.append(f"Could not read {idx_file}: {e}")

        # Strategy 5: Lesson symptoms (regression queries — higher value, run before git)
        for lessons_candidate in ["memory/lessons", "lessons"]:
            lessons_path = root / lessons_candidate
            if lessons_path.is_dir():
                try:
                    lesson_files = sorted(lessons_path.iterdir())
                except OSError as e:
                    warnings.append(f"Could not list lessons directory {lessons_path}: {e}")
                    continue
                for lf in lesson_files:
                    if not lf.name.endswith(".md") or lf.name == "_INDEX.md":
                        continue
                    try:
                        lf_content = lf.read_text(encoding="utf-8", errors="replace")
                        for line in lf_content.splitlines():
                            if line.startswith("## "):
                                heading = line[3:].strip()
                                heading_lower = heading.lower().split("(")[0].strip()
                                if heading_lower in NON_LESSON_HEADINGS:
                                    continue
                                # Strip date suffix for clean query text
                                clean_heading = heading.split("(")[0].strip()
                                queries.append({
                                    "text": f"Has {clean_heading} recurred?",
                                    "source": "lessons",
                                    "category": "regression",
                                })
                    except OSError as e:
                        warnings.append(f"Could not read lesson file {lf}: {e}")
                break  # only use first found lessons dir

        # Strategy 6: git log
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", f"-{git_log_lines}"],
                capture_output=True, text=True, cwd=str(root), timeout=10,
            )
            if result.returncode == 0:
                skip_prefixes = ("chore:", "ci:", "merge", "version", "trigger", "initial")
                for line in result.stdout.splitlines():
                    parts = line.split(maxsplit=1)
                    if len(parts) < 2:
                        continue
                    subject = parts[1].lower()
                    if any(subject.startswith(p) for p in skip_prefixes):
                        continue
                    # Extract meaningful words
                    words = re.findall(r'[a-zA-Z]{4,}', parts[1])
                    for word in words[:2]:
                        queries.append({"text": f"What changed with {word}?", "source": "git", "category": "what_changed"})
            else:
                warnings.append(f"git log failed (exit {result.returncode}): {result.stderr.strip()}")
        except (subprocess.SubprocessError, OSError) as e:
            warnings.append(f"git log failed: {e}")

        # Dedup and cap
        queries = _dedup_queries(queries)
        if len(queries) > target_count:
            queries = queries[:target_count]

        # Recount sources from final query list (dedup/cap may have removed entries)
        sources: dict[str, int] = {"claude_md": 0, "memory": 0, "indexes": 0, "lessons": 0, "git": 0}
        for q in queries:
            src = q.get("source", "")
            if src in sources:
                sources[src] += 1

        return {
            "queries": queries,
            "sources": sources,
            "total": len(queries),
            "warnings": warnings,
        }
