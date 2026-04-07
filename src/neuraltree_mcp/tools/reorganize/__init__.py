"""neuraltree_reorganize — Structural operations: move, split, archive, create index.

All operations are read-only analysis by default. They return a PLAN of what would change.
The Skill (or user) decides whether to execute the plan.

Split into individual modules for maintainability (was 809-line monolith).
"""
from __future__ import annotations

from fastmcp import FastMCP

# Re-export helpers for backward compatibility (tests import these)
from ._helpers import _find_all_references, _compute_rewrites, _strip_ref_fragment

from . import plan_move, plan_split, find_dead, generate_index, shrink_and_wire, split_and_wire


def register(mcp: FastMCP) -> None:
    plan_move.register(mcp)
    plan_split.register(mcp)
    find_dead.register(mcp)
    generate_index.register(mcp)
    shrink_and_wire.register(mcp)
    split_and_wire.register(mcp)
