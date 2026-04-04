"""Shared text processing utilities for NeuralTree MCP tools.

Extracted from tools/wire.py to be shared by wire, diagnose, score, scan, trace, lesson.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

STOPWORDS = frozenset({
    "the", "a", "is", "are", "was", "were", "be", "been", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "this", "that", "it", "and",
    "or", "but", "not", "as", "an", "will", "can", "do", "has", "have",
    "had", "would", "should", "could", "may", "might", "shall", "must",
    "no", "yes", "all", "each", "every", "any", "if", "then", "so", "up",
    "about", "into", "through", "during", "before", "after", "above",
    "below", "between", "out", "off", "over", "under", "again", "further",
    "once", "here", "there", "when", "where", "why", "how", "what", "which",
    "who", "whom", "its", "you", "your", "we", "our", "they", "their",
    "he", "she", "him", "her", "me", "my", "i",
})

# Superset from scan.py — intentionally includes .tox and htmlcov
# so test artifacts are never indexed across any tool.
SKIP_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".neuraltree",
    ".venv", "venv", ".tox", "htmlcov",
})

BACKTICK_PATH_RE = re.compile(r'`([a-zA-Z0-9_./\-]+\.[a-zA-Z0-9]+)`')

# Non-lesson headings that should NOT be parsed as lesson entries
NON_LESSON_HEADINGS = frozenset({
    "related", "docs", "content", "rules",
})


def extract_keywords(content: str, min_freq: int = 2) -> set[str]:
    """Extract topic keywords from content.

    Words appearing min_freq+ times, minus stopwords.
    Use min_freq=1 for short text (symptoms, queries).
    Use min_freq=2 for long text (file content, wiring comparison).

    Args:
        content: Text to extract keywords from.
        min_freq: Minimum frequency threshold.

    Returns:
        Set of lowercase keyword strings.
    """
    words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]{2,}', content.lower())
    freq: dict[str, int] = {}
    for w in words:
        if w not in STOPWORDS and len(w) > 2:
            freq[w] = freq.get(w, 0) + 1
    return {w for w, c in freq.items() if c >= min_freq}


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two keyword sets. Returns 0.0 if both empty."""
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def extract_backtick_paths(content: str) -> list[str]:
    """Extract file paths from `backtick` references."""
    return [m.group(1) for m in BACKTICK_PATH_RE.finditer(content)]


def walk_project_files(root: Path, extensions: set[str] | None = None) -> list[Path]:
    """Walk project tree, skip SKIP_DIRS, optionally filter by extension.

    Args:
        root: Root directory to walk.
        extensions: If provided, only return files with these extensions (e.g., {".md"}).

    Returns:
        List of matching file paths.
    """
    results = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            p = Path(dirpath) / fname
            if extensions is None or p.suffix.lower() in extensions:
                results.append(p)
    return results
