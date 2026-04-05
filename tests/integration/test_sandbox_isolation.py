"""Integration tests — sandbox isolation (create, modify, diff, apply, destroy)."""
import asyncio
import json
import os
import pytest

from neuraltree_mcp.server import mcp


def call_tool(name: str, args: dict) -> dict:
    """Helper to call an MCP tool synchronously and parse the result."""
    result = asyncio.run(mcp.call_tool(name, args))
    if hasattr(result, "structured_content") and result.structured_content is not None:
        return result.structured_content
    if hasattr(result, "content"):
        for block in result.content:
            if hasattr(block, "text"):
                return json.loads(block.text)
    return result


SANDBOX_REL = ".neuraltree/sandbox"


class TestSandboxIsolation:
    """Prove that sandbox tools create true isolation — changes never leak."""

    def test_sandbox_create(self, tmp_project):
        """Create sandbox, verify files exist in sandbox copy."""
        root = str(tmp_project)
        result = call_tool("neuraltree_sandbox_create", {
            "project_root": root,
            "use_git_worktree": False,
        })

        assert "error" not in result
        assert result["method"] == "copy"
        assert result["files_copied"] > 0

        sandbox = tmp_project / SANDBOX_REL
        assert sandbox.exists()
        # CLAUDE.md should be copied
        assert (sandbox / "CLAUDE.md").exists()
        # memory/ tree should be copied
        assert (sandbox / "memory" / "MEMORY.md").exists()
        assert (sandbox / "memory" / "rules" / "coding.md").exists()

        # Clean up
        call_tool("neuraltree_sandbox_destroy", {"project_root": root})

    def test_sandbox_changes_dont_affect_original(self, tmp_project):
        """Modify a file in sandbox — original must be untouched, diff must detect it."""
        root = str(tmp_project)
        call_tool("neuraltree_sandbox_create", {
            "project_root": root,
            "use_git_worktree": False,
        })

        # Read original content
        original_content = (tmp_project / "CLAUDE.md").read_text()

        # Mutate the file inside the sandbox
        sandbox_claude = tmp_project / SANDBOX_REL / "CLAUDE.md"
        sandbox_claude.write_text(original_content + "\n## SANDBOX EDIT\nThis was added in sandbox.\n")

        # Original must be untouched
        assert (tmp_project / "CLAUDE.md").read_text() == original_content

        # Diff should detect the change
        diff = call_tool("neuraltree_sandbox_diff", {"project_root": root})
        assert "error" not in diff
        changed_files = [c["file"] for c in diff["changed"]]
        assert "CLAUDE.md" in changed_files
        assert diff["total_changes"] >= 1

        # Clean up
        call_tool("neuraltree_sandbox_destroy", {"project_root": root})

    def test_sandbox_destroy_cleans_up(self, tmp_project):
        """Destroy removes the sandbox directory entirely."""
        root = str(tmp_project)
        call_tool("neuraltree_sandbox_create", {
            "project_root": root,
            "use_git_worktree": False,
        })

        sandbox = tmp_project / SANDBOX_REL
        assert sandbox.exists()

        result = call_tool("neuraltree_sandbox_destroy", {"project_root": root})
        assert result["status"] == "destroyed"
        assert not sandbox.exists()

    def test_sandbox_apply_selective(self, tmp_project):
        """Create new file in sandbox, apply it, verify it appears in real project."""
        root = str(tmp_project)
        call_tool("neuraltree_sandbox_create", {
            "project_root": root,
            "use_git_worktree": False,
        })

        # Create a brand-new file inside the sandbox
        new_file_rel = os.path.join("memory", "new_insight.md")
        sandbox_new = tmp_project / SANDBOX_REL / new_file_rel
        sandbox_new.write_text("# New Insight\n\nDiscovered during autoloop.\n")

        # The file must NOT exist in the real project yet
        assert not (tmp_project / new_file_rel).exists()

        # Apply only that one file
        apply_result = call_tool("neuraltree_sandbox_apply", {
            "files": [new_file_rel],
            "project_root": root,
        })
        assert apply_result["total_applied"] == 1
        assert new_file_rel in apply_result["applied"]
        assert len(apply_result["errors"]) == 0

        # Now the file must exist in the real project
        real_file = tmp_project / new_file_rel
        assert real_file.exists()
        assert "New Insight" in real_file.read_text()

        # Clean up
        call_tool("neuraltree_sandbox_destroy", {"project_root": root})

    def test_sandbox_apply_all(self, tmp_project):
        """Apply ALL sandbox changes (files=None)."""
        root = str(tmp_project)
        call_tool("neuraltree_sandbox_create", {
            "project_root": root,
            "use_git_worktree": False,
        })
        sandbox_path = tmp_project / SANDBOX_REL

        # Modify existing + create new
        (sandbox_path / "CLAUDE.md").write_text("MODIFIED IN SANDBOX\n")
        (sandbox_path / "memory" / "new_file.md").write_text("New content\n")

        # Apply all (files=None)
        result = call_tool("neuraltree_sandbox_apply", {"project_root": root})
        assert len(result.get("applied", [])) >= 1

        # Verify changes propagated
        assert "MODIFIED IN SANDBOX" in (tmp_project / "CLAUDE.md").read_text()

        # Clean up
        call_tool("neuraltree_sandbox_destroy", {"project_root": root})
