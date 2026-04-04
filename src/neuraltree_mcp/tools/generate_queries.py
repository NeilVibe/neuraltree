"""neuraltree_generate_queries — Auto-generate test queries from project context."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from fastmcp import FastMCP

from neuraltree_mcp.text_utils import NON_LESSON_HEADINGS
from neuraltree_mcp.validation import validate_project_root


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

        Uses 5 strategies:
        1. CLAUDE.md glossary tables -> "What is {term}?"
        2. CLAUDE.md nav tables -> "How does {topic} work?"
        3. MEMORY.md links -> "What do we know about {title}?"
        4. _INDEX.md entries -> "Where is {topic} documented?"
        5. git log subjects -> "What changed with {noun}?"

        Args:
            project_root: Project root directory.
            claude_md_path: Path to CLAUDE.md (auto-detected if None).
            memory_md_path: Path to MEMORY.md (auto-detected if None).
            index_paths: Paths to _INDEX.md files (auto-discovered if None).
            git_log_lines: Number of git log lines to parse.
            indexed_doc_count: Estimated indexed docs (for query count scaling).

        Returns:
            dict with queries, sources counts, and total.
        """
        try:
            root = validate_project_root(project_root)
        except ValueError as e:
            return {"queries": [], "sources": {}, "total": 0, "warnings": [], "error": str(e)}
        queries: list[dict] = []
        sources: dict[str, int] = {"claude_md": 0, "memory": 0, "indexes": 0, "lessons": 0, "git": 0}
        warnings: list[str] = []

        # Clamp git_log_lines
        git_log_lines = max(1, min(git_log_lines, 500))

        # Target query count: max(20, min(50, indexed_doc_count / 3))
        target_count = max(20, min(50, indexed_doc_count // 3))

        # Strategy 1: CLAUDE.md glossary
        claude_path = Path(claude_md_path) if claude_md_path else root / "CLAUDE.md"
        if claude_path.exists():
            try:
                claude_content = claude_path.read_text(encoding="utf-8", errors="replace")
                terms = _parse_table_column(claude_content, "Term", 0)
                for term in terms:
                    queries.append({"text": f"What is {term}?", "source": "claude_md", "category": "what_is"})
                    sources["claude_md"] += 1

                # Strategy 2: Nav table
                needs = _parse_table_column(claude_content, "Need", 0)
                for need in needs:
                    queries.append({"text": f"How does {need} work?", "source": "claude_md", "category": "how_does"})
                    sources["claude_md"] += 1
            except OSError as e:
                warnings.append(f"Could not read CLAUDE.md: {e}")

        # Strategy 3: MEMORY.md links
        mem_path = Path(memory_md_path) if memory_md_path else root / "memory" / "MEMORY.md"
        if mem_path.exists():
            try:
                mem_content = mem_path.read_text(encoding="utf-8", errors="replace")
                titles = _parse_md_links(mem_content)
                for title in titles:
                    queries.append({"text": f"What do we know about {title}?", "source": "memory", "category": "what_know"})
                    sources["memory"] += 1
            except OSError as e:
                warnings.append(f"Could not read MEMORY.md: {e}")

        # Strategy 4: _INDEX.md files
        if index_paths:
            idx_files = [root / p for p in index_paths]
        else:
            idx_files = list(root.rglob("_INDEX.md"))

        for idx_file in idx_files:
            if not idx_file.exists():
                continue
            try:
                idx_content = idx_file.read_text(encoding="utf-8", errors="replace")
                titles = _parse_md_links(idx_content)
                for title in titles:
                    queries.append({"text": f"Where is {title} documented?", "source": "indexes", "category": "where_is"})
                    sources["indexes"] += 1
            except OSError as e:
                warnings.append(f"Could not read {idx_file}: {e}")

        # Strategy 5: Lesson symptoms (regression queries — higher value, run before git)
        for lessons_candidate in ["memory/lessons", "lessons"]:
            lessons_path = root / lessons_candidate
            if lessons_path.is_dir():
                for lf in sorted(lessons_path.iterdir()):
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
                                sources["lessons"] += 1
                    except OSError as e:
                        warnings.append(f"Could not read lesson file {lf}: {e}")
                break  # only use first found lessons dir

        # Strategy 6: git log
        try:
            result = subprocess.run(
                ["git", "log", f"--oneline", f"-{git_log_lines}"],
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
                        sources["git"] += 1
        except (subprocess.SubprocessError, OSError) as e:
            warnings.append(f"git log failed: {e}")

        # Dedup and cap
        queries = _dedup_queries(queries)
        if len(queries) > target_count:
            queries = queries[:target_count]

        return {
            "queries": queries,
            "sources": sources,
            "total": len(queries),
            "warnings": warnings,
        }
