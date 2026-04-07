"""neuraltree_scan — Fast filesystem inventory with scale cap."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import FastMCP

from neuraltree_mcp.text_utils import SKIP_DIRS
from neuraltree_mcp.validation import validate_project_root


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def neuraltree_scan(
        path: str = ".",
        max_files: int = 10000,
        exclude_patterns: list[str] | None = None,
    ) -> dict:
        """Fast filesystem inventory.

        Walks the project tree collecting dirs, files, sizes, dates, and
        empty directories. Skips .git, node_modules, __pycache__, .neuraltree.
        Caps at max_files to prevent OOM on huge repos.

        Args:
            path: Root directory to scan (default: current dir).
            max_files: Maximum files to enumerate before capping.
            exclude_patterns: Additional directory prefixes to skip
                (e.g. [".planning", ".claude/agents", "docs/archive"]).
                Matched against relative paths from project root.

        Returns:
            dict with dirs, files, sizes, dates, empty_dirs, total_count, capped.
        """
        try:
            root = validate_project_root(path)
        except ValueError as e:
            return {"error": str(e)}

        # Normalize exclude patterns (strip trailing slashes)
        extra_excludes = set()
        if exclude_patterns:
            for pat in exclude_patterns:
                extra_excludes.add(pat.rstrip("/"))

        dirs: list[str] = []
        files: list[str] = []
        sizes: dict[str, int] = {}
        dates: dict[str, str] = {}
        empty_dirs: list[str] = []
        warnings: list[str] = []
        capped = False
        file_count = 0

        for dirpath, dirnames, filenames in os.walk(root):
            # Prune skipped directories in-place
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

            # Prune extra exclude patterns by relative path prefix
            if extra_excludes:
                rel_dir = os.path.relpath(dirpath, root)
                if rel_dir == ".":
                    rel_dir = ""
                dirnames[:] = [
                    d for d in dirnames
                    if os.path.join(rel_dir, d).replace("\\", "/") not in extra_excludes
                    and rel_dir not in extra_excludes
                ]
                # Skip this directory entirely if it matches
                if rel_dir and any(
                    rel_dir == pat or rel_dir.startswith(pat + "/")
                    for pat in extra_excludes
                ):
                    continue

            rel_dir = os.path.relpath(dirpath, root)
            if rel_dir == ".":
                rel_dir = ""

            if rel_dir:
                dirs.append(rel_dir + "/")

            if not filenames and not dirnames:
                empty_dirs.append((rel_dir + "/") if rel_dir else "/")

            for fname in filenames:
                if file_count >= max_files:
                    capped = True
                    break

                full = os.path.join(dirpath, fname)
                rel = os.path.relpath(full, root)
                files.append(rel)

                try:
                    st = os.stat(full)
                    sizes[rel] = st.st_size
                    mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
                    dates[rel] = mtime.strftime("%Y-%m-%d")
                except OSError as e:
                    sizes[rel] = 0
                    dates[rel] = "unknown"
                    warnings.append(f"stat failed for {rel}: {e}")

                file_count += 1

            if capped:
                break

        return {
            "dirs": sorted(dirs),
            "files": sorted(files),
            "sizes": sizes,
            "dates": dates,
            "empty_dirs": sorted(empty_dirs),
            "total_count": file_count,
            "capped": capped,
            "warnings": warnings,
        }
