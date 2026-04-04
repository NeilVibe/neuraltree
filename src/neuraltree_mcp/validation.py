"""Centralized path validation for NeuralTree MCP tools.

Prevents path traversal attacks by ensuring all resolved paths
stay within the project root directory.
"""
from __future__ import annotations

import os
from pathlib import Path


def validate_project_root(project_root: str) -> Path:
    """Resolve project_root to an absolute path.

    Args:
        project_root: The project root directory.

    Returns:
        Resolved absolute Path.

    Raises:
        ValueError: If project_root is not a directory.
    """
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise ValueError(f"project_root is not a directory: {root}")
    return root


def validate_within_root(path: Path, root: Path) -> Path:
    """Ensure a resolved path stays within the project root.

    Catches path traversal (../../etc/passwd) and symlink escapes.

    Args:
        path: The path to validate (will be resolved).
        root: The project root (must already be resolved).

    Returns:
        The resolved path if valid.

    Raises:
        ValueError: If the path escapes the root.
    """
    resolved = path.resolve()
    root_str = str(root)
    resolved_str = str(resolved)

    if resolved == root:
        return resolved
    if not resolved_str.startswith(root_str + os.sep):
        raise ValueError(f"Path escapes project root: {resolved} is not under {root}")
    return resolved
