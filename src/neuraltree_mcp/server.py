"""NeuralTree MCP Server — The Muscle.

26 tools for neural tree organization:
  Filesystem: scan, trace, backup, restore
  Intelligence: wire, generate_queries
  Knowledge Map: neuraltree_knowledge_map (save/load/query)
  Reorganize: plan_move, plan_split, find_dead, generate_index, shrink_and_wire, split_and_wire
  Lessons: lesson_match, lesson_add
  Scoring: score, diagnose
  Semantic: precision (Viking search + LLM judge), viking_index (batch indexing)
  Wiki: wiki_lint, compile (write wiki pages), wiki_read (read wiki state)
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
from neuraltree_mcp.tools.reorganize import register as register_reorganize
from neuraltree_mcp.tools.lesson import register as register_lesson
from neuraltree_mcp.scoring.score import register as register_score
from neuraltree_mcp.scoring.diagnose import register as register_diagnose
from neuraltree_mcp.sandbox.sandbox import register as register_sandbox
from neuraltree_mcp.tools.precision import register as register_precision
from neuraltree_mcp.tools.viking_index import register as register_viking_index
from neuraltree_mcp.tools.knowledge_map import register as register_knowledge_map
from neuraltree_mcp.tools.wiki_lint import register as register_wiki_lint
from neuraltree_mcp.tools.compile import register as register_compile

register_scan(mcp)
register_trace(mcp)
register_backup(mcp)
register_wire(mcp)
register_generate_queries(mcp)
register_reorganize(mcp)
register_lesson(mcp)
register_score(mcp)
register_diagnose(mcp)
register_sandbox(mcp)
register_precision(mcp)
register_viking_index(mcp)
register_knowledge_map(mcp)
register_wiki_lint(mcp)
register_compile(mcp)


if __name__ == "__main__":
    mcp.run()
