"""neuraltree_backup and neuraltree_restore — Safe file backup/restore."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from fastmcp import FastMCP

from neuraltree_mcp.validation import validate_project_root, validate_within_root

BACKUP_DIR = ".neuraltree/.tmp/backup"
MAX_BACKUP_BYTES = 100 * 1024 * 1024  # 100MB


def _backup_root(project_root: str) -> Path:
    return Path(project_root).resolve() / BACKUP_DIR


def _backup_size(backup_dir: Path) -> int:
    total = 0
    if backup_dir.exists():
        for f in backup_dir.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except OSError:
                    pass
    return total


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def neuraltree_backup(files: list[str], project_root: str = ".") -> dict:
        """Backup files before autoloop changes.

        Copies files to .neuraltree/.tmp/backup/ preserving relative path
        structure. Capped at 100MB total backup size.
        Never touches git stash.

        Args:
            files: List of file paths (relative to project_root) to back up.
            project_root: Project root directory.

        Returns:
            dict with backed_up, skipped, backup_dir, total_size, warnings.
        """
        try:
            root = validate_project_root(project_root)
        except ValueError as e:
            return {"backed_up": [], "skipped": [], "backup_dir": "", "total_size": "0MB",
                    "warnings": [], "error": str(e)}
        bdir = _backup_root(project_root)
        bdir.mkdir(parents=True, exist_ok=True)

        backed_up: list[str] = []
        skipped: list[str] = []
        warnings: list[str] = []
        current_size = _backup_size(bdir)

        for fpath in files:
            # Path traversal guard
            src = root / fpath
            try:
                validate_within_root(src, root)
            except ValueError:
                skipped.append(f"{fpath} (path traversal blocked)")
                continue

            if not src.exists():
                skipped.append(f"{fpath} (not found)")
                continue
            if not src.is_file():
                skipped.append(f"{fpath} (not a file)")
                continue

            try:
                fsize = src.stat().st_size
            except OSError as e:
                skipped.append(f"{fpath} (stat failed: {e})")
                continue

            if current_size + fsize > MAX_BACKUP_BYTES:
                skipped.append(f"{fpath} (would exceed 100MB cap)")
                continue

            dest = bdir / fpath
            try:
                validate_within_root(dest, bdir)
            except ValueError:
                skipped.append(f"{fpath} (path traversal blocked)")
                continue

            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(dest))
                backed_up.append(fpath)
                current_size += fsize
            except OSError as e:
                warnings.append(f"Failed to backup {fpath}: {e}")

        total_mb = round(current_size / (1024 * 1024), 2)
        return {
            "backed_up": backed_up,
            "skipped": skipped,
            "backup_dir": str(bdir),
            "total_size": f"{total_mb}MB",
            "warnings": warnings,
        }

    @mcp.tool()
    def neuraltree_restore(files: list[str] | None = None, project_root: str = ".") -> dict:
        """Restore files from backup.

        If files is None, restores ALL backed-up files.
        Copies from .neuraltree/.tmp/backup/ back to original locations.

        Args:
            files: Specific files to restore, or None for all.
            project_root: Project root directory.

        Returns:
            dict with restored, not_found, integrity_errors, warnings.
        """
        try:
            root = validate_project_root(project_root)
        except ValueError as e:
            return {"restored": [], "not_found": [], "integrity_errors": [],
                    "warnings": [], "error": str(e)}
        bdir = _backup_root(project_root)

        if not bdir.exists():
            return {"restored": [], "not_found": [], "error": "No backup directory found"}

        restored: list[str] = []
        not_found: list[str] = []
        integrity_errors: list[str] = []
        warnings: list[str] = []

        if files is None:
            targets = []
            for f in bdir.rglob("*"):
                if f.is_file():
                    targets.append(os.path.relpath(f, bdir))
        else:
            targets = files

        for fpath in targets:
            src = bdir / fpath
            if not src.exists():
                not_found.append(fpath)
                continue

            dest = root / fpath
            # Path traversal guard
            try:
                validate_within_root(dest, root)
            except ValueError:
                warnings.append(f"{fpath}: path traversal blocked")
                continue

            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(dest))
            except OSError as e:
                warnings.append(f"Failed to restore {fpath}: {e}")
                continue

            # Integrity check
            try:
                if src.read_bytes() == dest.read_bytes():
                    restored.append(fpath)
                else:
                    integrity_errors.append(fpath)
            except OSError as e:
                warnings.append(f"Integrity check failed for {fpath}: {e}")

        return {
            "restored": restored,
            "not_found": not_found,
            "integrity_errors": integrity_errors,
            "warnings": warnings,
        }
