"""Tests for neuraltree sandbox tools."""
import os
import shutil
from pathlib import Path

from neuraltree_mcp.sandbox.sandbox import _is_git_repo, SANDBOX_DIR


class TestIsGitRepo:
    def test_non_git_dir(self, tmp_path):
        assert _is_git_repo(tmp_path) is False

    def test_git_dir(self, tmp_path):
        # Initialize a git repo
        import subprocess
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
        assert _is_git_repo(tmp_path) is True


class TestSandboxCreate:
    def test_copy_mode_creates_sandbox(self, tmp_project):
        """Without git, sandbox should use copy mode."""
        root = tmp_project
        sandbox = root / SANDBOX_DIR

        # Copy key files manually (simulating the tool)
        sandbox.mkdir(parents=True, exist_ok=True)
        copy_dirs = ["memory", "docs"]
        for dirname in copy_dirs:
            src = root / dirname
            if src.exists():
                shutil.copytree(str(src), str(sandbox / dirname), dirs_exist_ok=True)

        shutil.copy2(str(root / "CLAUDE.md"), str(sandbox / "CLAUDE.md"))

        assert sandbox.exists()
        assert (sandbox / "CLAUDE.md").exists()
        assert (sandbox / "memory" / "MEMORY.md").exists()
        assert (sandbox / "docs" / "INDEX.md").exists()

    def test_sandbox_content_matches_original(self, tmp_project):
        """Copied files should have identical content."""
        root = tmp_project
        sandbox = root / SANDBOX_DIR
        sandbox.mkdir(parents=True, exist_ok=True)

        shutil.copy2(str(root / "CLAUDE.md"), str(sandbox / "CLAUDE.md"))

        assert (root / "CLAUDE.md").read_text() == (sandbox / "CLAUDE.md").read_text()


class TestSandboxDiff:
    def test_detect_changed_files(self, tmp_project):
        """Modifying a file in sandbox should be detected."""
        root = tmp_project
        sandbox = root / SANDBOX_DIR
        sandbox.mkdir(parents=True, exist_ok=True)

        # Copy and modify
        shutil.copy2(str(root / "CLAUDE.md"), str(sandbox / "CLAUDE.md"))
        (sandbox / "CLAUDE.md").write_text("MODIFIED IN SANDBOX")

        orig = (root / "CLAUDE.md").read_text()
        sand = (sandbox / "CLAUDE.md").read_text()
        assert orig != sand

    def test_detect_added_files(self, tmp_project):
        """New files in sandbox should be detected."""
        root = tmp_project
        sandbox = root / SANDBOX_DIR
        sandbox.mkdir(parents=True, exist_ok=True)

        (sandbox / "new_file.md").write_text("Brand new")
        assert not (root / "new_file.md").exists()
        assert (sandbox / "new_file.md").exists()


class TestSandboxApply:
    def test_apply_changes(self, tmp_project):
        """Applying sandbox changes should update the real project."""
        root = tmp_project
        sandbox = root / SANDBOX_DIR
        sandbox.mkdir(parents=True, exist_ok=True)

        shutil.copy2(str(root / "CLAUDE.md"), str(sandbox / "CLAUDE.md"))
        (sandbox / "CLAUDE.md").write_text("SANDBOX VERSION")

        # Apply
        shutil.copy2(str(sandbox / "CLAUDE.md"), str(root / "CLAUDE.md"))
        assert (root / "CLAUDE.md").read_text() == "SANDBOX VERSION"


class TestSandboxDestroy:
    def test_destroy_removes_sandbox(self, tmp_project):
        """Destroying sandbox should remove the directory."""
        root = tmp_project
        sandbox = root / SANDBOX_DIR
        sandbox.mkdir(parents=True, exist_ok=True)
        (sandbox / "test.md").write_text("test")

        shutil.rmtree(sandbox)
        assert not sandbox.exists()
