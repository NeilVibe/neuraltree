"""neuraltree sandbox — Isolated worktree/rsync sandbox for autoloop."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from fastmcp import FastMCP

from neuraltree_mcp.validation import validate_project_root, validate_within_root

SANDBOX_DIR = ".neuraltree/sandbox"
SANDBOX_BRANCH = "neuraltree-sandbox"

# Directories to copy when git is not available
COPY_DIRS = ["memory", "docs", ".claude"]
COPY_FILES = ["CLAUDE.md", "AGENTS.md", "GEMINI.md", "README.md", "MEMORY.md"]


def _is_git_repo(root: Path) -> bool:
    """Check if root is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, cwd=str(root), timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _sandbox_path(project_root: str) -> Path:
    return Path(project_root).resolve() / SANDBOX_DIR


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def neuraltree_sandbox_create(project_root: str = ".", use_git_worktree: bool = True) -> dict:
        """Create an isolated sandbox for autoloop execution.

        If git is available and use_git_worktree=True, creates a git worktree.
        Otherwise, uses rsync/copy of key directories.

        Args:
            project_root: Project root directory.
            use_git_worktree: Prefer git worktree if available.

        Returns:
            dict with sandbox_path, method (worktree/copy), and files_copied.
        """
        try:
            root = validate_project_root(project_root)
        except ValueError as e:
            return {"error": str(e), "sandbox_path": "", "method": "", "files_copied": 0}
        sandbox = _sandbox_path(project_root)

        # Clean up any existing sandbox
        if sandbox.exists():
            shutil.rmtree(sandbox)

        method = "copy"
        files_copied = 0
        worktree_warnings: list[str] = []

        if use_git_worktree and _is_git_repo(root):
            try:
                # Remove stale worktree reference if exists
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(sandbox)],
                    capture_output=True, text=True, cwd=str(root), timeout=10,
                )
            except (subprocess.SubprocessError, OSError):
                pass

            try:
                # Try to delete old branch
                subprocess.run(
                    ["git", "branch", "-D", SANDBOX_BRANCH],
                    capture_output=True, text=True, cwd=str(root), timeout=5,
                )
            except (subprocess.SubprocessError, OSError):
                pass

            try:
                result = subprocess.run(
                    ["git", "worktree", "add", "-b", SANDBOX_BRANCH, str(sandbox), "HEAD"],
                    capture_output=True, text=True, cwd=str(root), timeout=30,
                )
                if result.returncode == 0:
                    method = "worktree"
                    # Count files
                    for _, _, fnames in os.walk(sandbox):
                        files_copied += len(fnames)
                else:
                    worktree_warnings.append(
                        f"git worktree failed (rc={result.returncode}), falling back to copy. "
                        f"stderr: {result.stderr.strip()}"
                    )
            except (subprocess.SubprocessError, OSError) as e:
                worktree_warnings.append(f"git worktree exception, falling back to copy: {e}")

        if method == "copy":
            sandbox.mkdir(parents=True, exist_ok=True)

            # Copy key directories
            for dirname in COPY_DIRS:
                src = root / dirname
                if src.exists() and src.is_dir():
                    dst = sandbox / dirname
                    shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
                    for _, _, fnames in os.walk(dst):
                        files_copied += len(fnames)

            # Copy key files
            for fname in COPY_FILES:
                src = root / fname
                if src.exists() and src.is_file():
                    shutil.copy2(str(src), str(sandbox / fname))
                    files_copied += 1

        return {
            "sandbox_path": str(sandbox),
            "method": method,
            "files_copied": files_copied,
            "warnings": worktree_warnings,
        }

    @mcp.tool()
    def neuraltree_sandbox_diff(project_root: str = ".") -> dict:
        """Compare sandbox vs original project.

        Generates a file-by-file diff showing what the autoloop changed.

        Args:
            project_root: Project root directory.

        Returns:
            dict with changed, added, deleted files and their diffs.
        """
        try:
            root = validate_project_root(project_root)
        except ValueError as e:
            return {"error": str(e)}
        sandbox = _sandbox_path(project_root)

        if not sandbox.exists():
            return {"error": "No sandbox found. Run neuraltree_sandbox_create first."}

        changed: list[dict] = []
        added: list[str] = []
        deleted: list[str] = []
        warnings: list[str] = []

        # Walk sandbox and compare
        sandbox_files: set[str] = set()
        for dirpath, _, filenames in os.walk(sandbox):
            rel_dir = os.path.relpath(dirpath, sandbox)
            if rel_dir.startswith(".git"):
                continue
            for fname in filenames:
                if fname == ".git":
                    continue
                rel = os.path.join(rel_dir, fname) if rel_dir != "." else fname
                sandbox_files.add(rel)

                original = root / rel
                sandbox_file = sandbox / rel

                if not original.exists():
                    added.append(rel)
                else:
                    try:
                        orig_content = original.read_text(encoding="utf-8", errors="replace")
                        sand_content = sandbox_file.read_text(encoding="utf-8", errors="replace")
                        if orig_content != sand_content:
                            changed.append({
                                "file": rel,
                                "original_lines": len(orig_content.splitlines()),
                                "sandbox_lines": len(sand_content.splitlines()),
                            })
                    except OSError as e:
                        warnings.append(f"Could not compare {rel}: {e}")

        # Check for files in original that were deleted in sandbox
        for dirname in COPY_DIRS:
            orig_dir = root / dirname
            if not orig_dir.exists():
                continue
            for dirpath, _, filenames in os.walk(orig_dir):
                rel_dir = os.path.relpath(dirpath, root)
                for fname in filenames:
                    rel = os.path.join(rel_dir, fname)
                    if rel not in sandbox_files and not (sandbox / rel).exists():
                        deleted.append(rel)

        return {
            "changed": changed,
            "added": added,
            "deleted": deleted,
            "total_changes": len(changed) + len(added) + len(deleted),
            "warnings": warnings,
        }

    @mcp.tool()
    def neuraltree_sandbox_apply(files: list[str] | None = None, project_root: str = ".") -> dict:
        """Apply approved changes from sandbox to real project.

        If files is None, applies ALL changes. Otherwise applies only specified files.

        Args:
            files: Specific files to apply, or None for all.
            project_root: Project root directory.

        Returns:
            dict with applied files and any errors.
        """
        try:
            root = validate_project_root(project_root)
        except ValueError as e:
            return {"error": str(e)}
        sandbox = _sandbox_path(project_root)

        if not sandbox.exists():
            return {"error": "No sandbox found."}

        applied: list[str] = []
        errors: list[str] = []

        if files is None:
            # Collect all files from sandbox (single walk)
            targets = []
            for dirpath, _, filenames in os.walk(sandbox):
                rel_dir = os.path.relpath(dirpath, sandbox)
                if rel_dir.startswith(".git"):
                    continue
                for fname in filenames:
                    if fname == ".git":
                        continue
                    rel = os.path.join(rel_dir, fname) if rel_dir != "." else fname
                    targets.append(rel)
        else:
            targets = files

        for rel in targets:
            src = sandbox / rel
            dst = root / rel
            # Path traversal guard — validate BOTH source and destination
            try:
                validate_within_root(src, sandbox)
            except ValueError:
                errors.append(f"{rel}: source path traversal blocked (escapes sandbox)")
                continue
            try:
                validate_within_root(dst, root)
            except ValueError:
                errors.append(f"{rel}: path traversal blocked (escapes project root)")
                continue
            if not src.exists():
                errors.append(f"{rel}: not found in sandbox")
                continue
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(dst))
                applied.append(rel)
            except OSError as e:
                errors.append(f"{rel}: {e}")

        return {
            "applied": applied,
            "errors": errors,
            "total_applied": len(applied),
        }

    @mcp.tool()
    def neuraltree_sandbox_destroy(project_root: str = ".") -> dict:
        """Destroy the sandbox and clean up.

        Removes git worktree (if used) and deletes the sandbox directory.

        Args:
            project_root: Project root directory.

        Returns:
            dict with status and cleanup details.
        """
        try:
            root = validate_project_root(project_root)
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        sandbox = _sandbox_path(project_root)

        if not sandbox.exists():
            return {"status": "no_sandbox", "message": "No sandbox to destroy."}

        # Try git worktree removal first
        cleanup_warnings: list[str] = []
        if _is_git_repo(root):
            try:
                result = subprocess.run(
                    ["git", "worktree", "remove", "--force", str(sandbox)],
                    capture_output=True, text=True, cwd=str(root), timeout=10,
                )
                if result.returncode != 0:
                    cleanup_warnings.append(f"git worktree remove failed: {result.stderr.strip()}")
                # Clean up branch
                result = subprocess.run(
                    ["git", "branch", "-D", SANDBOX_BRANCH],
                    capture_output=True, text=True, cwd=str(root), timeout=5,
                )
                if result.returncode != 0:
                    cleanup_warnings.append(f"git branch -D failed: {result.stderr.strip()}")
            except (subprocess.SubprocessError, OSError) as e:
                cleanup_warnings.append(f"git cleanup exception: {e}")

        # Force delete if still exists
        if sandbox.exists():
            try:
                shutil.rmtree(sandbox)
            except OSError as e:
                cleanup_warnings.append(f"rmtree failed: {e}")

        # Verify cleanup actually worked
        if sandbox.exists():
            return {
                "status": "failed",
                "message": f"Sandbox at {sandbox} could not be fully removed.",
                "warnings": cleanup_warnings,
            }

        return {
            "status": "destroyed",
            "message": f"Sandbox at {sandbox} removed.",
            "warnings": cleanup_warnings,
        }
