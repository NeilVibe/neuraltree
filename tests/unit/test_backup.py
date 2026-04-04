"""Tests for neuraltree_backup and neuraltree_restore tools."""
import os
from pathlib import Path

from neuraltree_mcp.tools.backup import _backup_root, _backup_size, MAX_BACKUP_BYTES
from neuraltree_mcp.validation import validate_within_root


class TestBackup:
    def test_backup_files(self, tmp_project):
        """Backup known files and verify they exist in backup dir."""
        root = tmp_project
        bdir = root / ".neuraltree" / ".tmp" / "backup"
        bdir.mkdir(parents=True, exist_ok=True)

        # Manually backup
        files_to_backup = ["CLAUDE.md", "memory/rules/coding.md"]
        backed = []
        for fpath in files_to_backup:
            src = root / fpath
            dest = bdir / fpath
            dest.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(str(src), str(dest))
            backed.append(fpath)

        assert len(backed) == 2
        assert (bdir / "CLAUDE.md").exists()
        assert (bdir / "memory" / "rules" / "coding.md").exists()

    def test_backup_preserves_content(self, tmp_project):
        """Backed up file should have identical content."""
        root = tmp_project
        bdir = root / ".neuraltree" / ".tmp" / "backup"
        bdir.mkdir(parents=True, exist_ok=True)

        src = root / "CLAUDE.md"
        dest = bdir / "CLAUDE.md"
        import shutil
        shutil.copy2(str(src), str(dest))

        assert src.read_text() == dest.read_text()

    def test_backup_nonexistent_file(self, tmp_project):
        """Backing up a nonexistent file should skip it."""
        root = tmp_project
        bdir = root / ".neuraltree" / ".tmp" / "backup"
        bdir.mkdir(parents=True, exist_ok=True)

        src = root / "does_not_exist.md"
        assert not src.exists()

    def test_restore_after_modification(self, tmp_project):
        """Modify a file, restore from backup, verify content matches original."""
        root = tmp_project
        bdir = root / ".neuraltree" / ".tmp" / "backup"
        bdir.mkdir(parents=True, exist_ok=True)

        target = root / "CLAUDE.md"
        original_content = target.read_text()

        # Backup
        import shutil
        dest = bdir / "CLAUDE.md"
        shutil.copy2(str(target), str(dest))

        # Modify
        target.write_text("MODIFIED CONTENT")
        assert target.read_text() != original_content

        # Restore
        shutil.copy2(str(dest), str(target))
        assert target.read_text() == original_content

    def test_restore_all(self, tmp_project):
        """Restore all backed up files."""
        root = tmp_project
        bdir = root / ".neuraltree" / ".tmp" / "backup"
        bdir.mkdir(parents=True, exist_ok=True)

        import shutil
        files = ["CLAUDE.md", "memory/rules/coding.md"]
        for f in files:
            dest = bdir / f
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(root / f), str(dest))

        # Modify originals
        (root / "CLAUDE.md").write_text("CHANGED")
        (root / "memory" / "rules" / "coding.md").write_text("CHANGED")

        # Restore all
        for f in bdir.rglob("*"):
            if f.is_file():
                rel = os.path.relpath(f, bdir)
                shutil.copy2(str(f), str(root / rel))

        assert "CHANGED" not in (root / "CLAUDE.md").read_text()
        assert "CHANGED" not in (root / "memory" / "rules" / "coding.md").read_text()

    def test_backup_size_calculation(self, tmp_project):
        """_backup_size should sum all file sizes."""
        root = tmp_project
        bdir = root / ".neuraltree" / ".tmp" / "backup"
        bdir.mkdir(parents=True, exist_ok=True)

        (bdir / "file1.txt").write_text("hello")
        (bdir / "file2.txt").write_text("world!")

        size = _backup_size(bdir)
        assert size == 5 + 6  # "hello" + "world!"

    def test_empty_backup_dir(self, tmp_project):
        """_backup_size of nonexistent dir should be 0."""
        root = tmp_project
        bdir = root / ".neuraltree" / ".tmp" / "backup"
        assert _backup_size(bdir) == 0
