"""neuraltree_plan_move — Plan a file move with reference updates."""
from __future__ import annotations

from fastmcp import FastMCP

from neuraltree_mcp.validation import validate_project_root, validate_within_root
from ._helpers import _find_all_references, _compute_rewrites


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def neuraltree_plan_move(
        source: str,
        destination: str,
        project_root: str = ".",
    ) -> dict:
        """Plan a file move with all reference updates.

        Traces all references to the source file, computes the text rewrites
        needed to update them to the new destination, and returns a plan.
        Does NOT execute anything — returns the plan for review.

        Args:
            source: Relative path of the file to move (e.g. "docs/old_guide.md").
            destination: Relative path of the new location (e.g. "docs/guides/setup.md").
            project_root: Project root directory.

        Returns:
            dict with source, destination, references_found, rewrites, and warnings.
        """
        try:
            root = validate_project_root(project_root)
        except (ValueError, OSError) as e:
            return {"error": str(e)}

        # Validate both paths are within root
        try:
            src_path = root / source
            validate_within_root(src_path, root)
            dst_path = root / destination
            validate_within_root(dst_path, root)
        except ValueError as e:
            return {"error": f"Path escapes project root: {e}"}

        if not src_path.exists():
            return {"error": f"Source does not exist: {source}"}

        warnings = []
        if dst_path.exists():
            warnings.append(f"Destination already exists: {destination}")

        # Find all references
        references, ref_warnings = _find_all_references(root, source)
        warnings.extend(ref_warnings)
        rewrites = _compute_rewrites(references, source, destination)

        return {
            "source": source,
            "destination": destination,
            "references_found": len(references),
            "rewrites": rewrites,
            "warnings": warnings,
        }
