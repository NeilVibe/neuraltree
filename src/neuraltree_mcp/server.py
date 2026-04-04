"""NeuralTree MCP Server — The Muscle.

16 tools for neural tree organization:
  Filesystem: scan, trace, backup, restore
  Intelligence: wire, generate_queries
  Lessons: lesson_match, lesson_add
  Scoring: score, diagnose, predict, update_calibration
  Sandbox: sandbox_create, sandbox_diff, sandbox_apply, sandbox_destroy
"""
from fastmcp import FastMCP

mcp = FastMCP("neuraltree")

# Tools are registered via imports below.
# Each tool module calls @mcp.tool() on the shared mcp instance.

from neuraltree_mcp.tools.scan import register as register_scan
from neuraltree_mcp.tools.trace import register as register_trace
from neuraltree_mcp.tools.backup import register as register_backup
from neuraltree_mcp.tools.wire import register as register_wire
from neuraltree_mcp.tools.generate_queries import register as register_generate_queries
from neuraltree_mcp.tools.lesson import register as register_lesson
from neuraltree_mcp.scoring.score import register as register_score
from neuraltree_mcp.scoring.diagnose import register as register_diagnose
from neuraltree_mcp.scoring.predict import register as register_predict
from neuraltree_mcp.sandbox.sandbox import register as register_sandbox

register_scan(mcp)
register_trace(mcp)
register_backup(mcp)
register_wire(mcp)
register_generate_queries(mcp)
register_lesson(mcp)
register_score(mcp)
register_diagnose(mcp)
register_predict(mcp)
register_sandbox(mcp)


if __name__ == "__main__":
    mcp.run()
