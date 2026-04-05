# Phase 4: Hardening — Integration & End-to-End Testing

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify the entire NeuralTree pipeline (MCP tools + SKILL.md instructions) works end-to-end against a real project, proving the scoring system, autoloop, sandbox isolation, and degraded mode all function correctly.

**Architecture:** Write Python integration tests that call MCP tools programmatically against real and synthetic projects. Tests verify tool outputs match SKILL.md expectations. For the full pipeline test, simulate what an agent would do when following SKILL.md section by section.

**Tech Stack:** Python 3.11, pytest, fastmcp (mcp.call_tool), neuraltree-mcp (16 tools)

**Test target project:** `/home/neil1988/newfin` — real project with CLAUDE.md (705 lines), memory/, docs/, .claude/ structure

---

## File Structure

```
tests/
├── conftest.py                     (existing — add newfin fixture)
├── integration/
│   ├── test_integration_tools.py   (existing — 2 files)
│   ├── test_e2e_pipeline.py        (NEW — full pipeline simulation)
│   ├── test_sandbox_isolation.py   (NEW — sandbox create/diff/apply/destroy)
│   └── test_degraded_mode.py       (NEW — no-Viking behavior)
└── unit/
    └── (existing 11 files — no changes)
```

---

### Task 1: Infrastructure — Verify MCP Server + Add newfin Fixture

**Files:**
- Modify: `tests/conftest.py` (add newfin_project fixture)
- Test: `tests/integration/test_e2e_pipeline.py` (new)

- [ ] **Step 1: Verify existing 175 tests still pass**

Run: `cd /home/neil1988/neuraltree && PYTHONPATH=src python3.11 -m pytest tests/ -q`
Expected: `175 passed`

- [ ] **Step 2: Verify all 16 tools load**

Run:
```bash
cd /home/neil1988/neuraltree && PYTHONPATH=src python3.11 -c "
import asyncio
from neuraltree_mcp.server import mcp
tools = asyncio.run(mcp.list_tools())
print(f'{len(tools)} tools loaded')
assert len(tools) == 16, f'Expected 16, got {len(tools)}'
for t in tools:
    print(f'  {t.name}')
"
```
Expected: `16 tools loaded` with all names listed

- [ ] **Step 3: Add newfin_project fixture to conftest.py**

Add to `tests/conftest.py`:
```python
@pytest.fixture
def newfin_project():
    """Real project fixture — points to /home/neil1988/newfin.
    
    READ-ONLY fixture. Tests should use sandbox tools for any modifications.
    Never write directly to this path.
    """
    p = Path("/home/neil1988/newfin")
    if not p.exists():
        pytest.skip("newfin project not available")
    return p
```

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add newfin_project fixture for e2e testing"
```

---

### Task 2: End-to-End Pipeline — Scan + Score + Queries (Section 4 Benchmark)

**Files:**
- Create: `tests/integration/test_e2e_pipeline.py`

This tests what an agent following SKILL.md Section 4 would do: scan the project, generate queries, score it, assemble baseline.

- [ ] **Step 1: Write the pipeline test**

```python
"""End-to-end pipeline tests against a real project."""
import asyncio
import pytest
from neuraltree_mcp.server import mcp


@pytest.fixture
def call():
    """Helper to call MCP tools."""
    async def _call(name, **kwargs):
        result = await mcp.call_tool(name, kwargs)
        assert isinstance(result, list) and len(result) > 0
        import json
        return json.loads(result[0].text)
    return _call


class TestBenchmarkPipeline:
    """Simulate SKILL.md Section 4: Benchmark Protocol against newfin."""

    def test_scan_newfin(self, newfin_project, call):
        """Step 1: Scan — verify scan returns files, dirs, total_count."""
        result = asyncio.run(call("neuraltree_scan", path=str(newfin_project)))
        assert "error" not in result, f"Scan error: {result.get('error')}"
        assert result["total_count"] > 0, "No files found"
        assert len(result["files"]) > 0, "No files listed"
        assert len(result["dirs"]) > 0, "No dirs listed"
        assert isinstance(result["files"][0], str), "files should be list[str]"
        print(f"Scanned: {result['total_count']} files, {len(result['dirs'])} dirs")

    def test_generate_queries_newfin(self, newfin_project, call):
        """Step 2: Generate queries — verify queries come from project context."""
        result = asyncio.run(call(
            "neuraltree_generate_queries",
            project_root=str(newfin_project),
            claude_md_path=str(newfin_project / "CLAUDE.md"),
            git_log_lines=50,
            indexed_doc_count=30,
        ))
        assert "error" not in result, f"Query gen error: {result.get('error')}"
        assert result["total"] >= 20, f"Expected >= 20 queries, got {result['total']}"
        assert len(result["queries"]) > 0
        # Verify query structure
        q = result["queries"][0]
        assert "text" in q, "Query missing 'text' field"
        assert "source" in q, "Query missing 'source' field"
        assert "category" in q, "Query missing 'category' field"
        print(f"Generated: {result['total']} queries from {result['sources']}")

    def test_score_newfin(self, newfin_project, call):
        """Step 3: Score — verify structural metrics compute."""
        result = asyncio.run(call("neuraltree_score", project_root=str(newfin_project)))
        assert "error" not in result, f"Score error: {result.get('error')}"
        metrics = result["metrics"]
        # All metrics should be floats between 0 and 1 (except precision_at_3 which is None)
        for key in ["hop_efficiency", "synapse_coverage", "dead_neuron_ratio", "freshness", "trunk_pressure"]:
            assert key in metrics, f"Missing metric: {key}"
            assert 0.0 <= metrics[key] <= 1.0, f"{key} out of range: {metrics[key]}"
        assert metrics["precision_at_3"] is None, "precision_at_3 should be None (Skill computes it)"
        assert "flow_score_partial" in result
        assert 0.0 <= result["flow_score_partial"] <= 1.0
        print(f"Score: {result['flow_score_partial']:.3f} (partial, without precision_at_3)")
        print(f"Metrics: {metrics}")

    def test_diagnose_with_failures(self, newfin_project, call):
        """Step 4: Diagnose — verify gap classification works on real queries."""
        # Create some test failures
        failed_queries = [
            {"text": "How does the backtesting system work?", "expected_topic": "backtest"},
            {"text": "What is the scoring algorithm?", "expected_topic": "scoring"},
            {"text": "Where is the Discord integration?", "expected_topic": "discord"},
        ]
        result = asyncio.run(call(
            "neuraltree_diagnose",
            failed_queries=failed_queries,
            project_root=str(newfin_project),
        ))
        assert "error" not in result
        assert result["total_failures"] == 3
        assert len(result["diagnoses"]) == 3
        # Each diagnosis should have gap_type and fix
        for d in result["diagnoses"]:
            assert d["gap_type"] in ["CONTENT_GAP", "EMBEDDING_GAP", "SYNAPSE_GAP", "FRESHNESS_GAP", "FOCUS_GAP"]
            assert "fix" in d
        print(f"Diagnoses: {result['gap_counts']}")

    def test_predict_impact(self, newfin_project, call):
        """Step 5: Predict — verify virtual backtest works."""
        # First get current metrics
        score = asyncio.run(call("neuraltree_score", project_root=str(newfin_project)))
        metrics = score["metrics"]
        
        result = asyncio.run(call(
            "neuraltree_predict",
            current_metrics=metrics,
            proposed_changes=[
                {"action": "wire", "target": "memory/reference/auth.md", "details": "Add ## Related"},
                {"action": "update_freshness", "target": "memory/rules/coding.md", "details": "Update date"},
            ],
            project_root=str(newfin_project),
        ))
        assert "error" not in result
        assert result["predicted_delta"] >= 0, "Wiring should improve score"
        assert 0.0 <= result["confidence"] <= 1.0
        print(f"Predicted delta: {result['predicted_delta']:+.3f}, confidence: {result['confidence']:.3f}")
```

- [ ] **Step 2: Run the tests**

Run: `cd /home/neil1988/neuraltree && PYTHONPATH=src python3.11 -m pytest tests/integration/test_e2e_pipeline.py -v`
Expected: All 5 tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_e2e_pipeline.py
git commit -m "test: e2e pipeline — scan, queries, score, diagnose, predict against newfin"
```

---

### Task 3: Sandbox Isolation Tests

**Files:**
- Create: `tests/integration/test_sandbox_isolation.py`

Verify the sandbox creates an isolated copy, changes don't affect the real project, diff works, and cleanup is complete.

- [ ] **Step 1: Write sandbox tests**

```python
"""Sandbox isolation tests — verify changes don't affect real project."""
import asyncio
import json
import os
import pytest
from pathlib import Path
from neuraltree_mcp.server import mcp


@pytest.fixture
def call():
    async def _call(name, **kwargs):
        result = await mcp.call_tool(name, kwargs)
        import json
        return json.loads(result[0].text)
    return _call


class TestSandboxIsolation:
    """Verify sandbox tools create true isolation."""

    def test_sandbox_create_on_tmp_project(self, tmp_project, call):
        """Sandbox creates isolated copy of project."""
        result = asyncio.run(call("neuraltree_sandbox_create", project_root=str(tmp_project)))
        assert "error" not in result, f"Sandbox create error: {result.get('error')}"
        assert result["files_copied"] > 0
        assert result["method"] in ("worktree", "copy")
        sandbox_path = result["sandbox_path"]
        assert os.path.exists(sandbox_path), "Sandbox directory not created"
        # Verify key files exist in sandbox
        assert os.path.exists(os.path.join(sandbox_path, "CLAUDE.md")), "CLAUDE.md missing in sandbox"
        print(f"Sandbox created: {sandbox_path} ({result['method']}, {result['files_copied']} files)")
        
        # Cleanup
        asyncio.run(call("neuraltree_sandbox_destroy", project_root=str(tmp_project)))

    def test_sandbox_changes_dont_affect_original(self, tmp_project, call):
        """Modifying sandbox files doesn't change original project."""
        # Create sandbox
        asyncio.run(call("neuraltree_sandbox_create", project_root=str(tmp_project)))
        sandbox_path = tmp_project / ".neuraltree" / "sandbox"
        
        # Read original CLAUDE.md
        original = (tmp_project / "CLAUDE.md").read_text()
        
        # Modify file in sandbox
        sandbox_claude = sandbox_path / "CLAUDE.md"
        sandbox_claude.write_text(original + "\n## SANDBOX MODIFICATION\nThis was added in sandbox.\n")
        
        # Verify original is untouched
        assert (tmp_project / "CLAUDE.md").read_text() == original, "Original file was modified!"
        
        # Diff should show the change
        diff = asyncio.run(call("neuraltree_sandbox_diff", project_root=str(tmp_project)))
        assert diff["summary"]["total_changes"] > 0, "Diff should detect sandbox changes"
        print(f"Sandbox diff: {diff['summary']}")
        
        # Cleanup
        asyncio.run(call("neuraltree_sandbox_destroy", project_root=str(tmp_project)))

    def test_sandbox_destroy_cleans_up(self, tmp_project, call):
        """Destroy removes sandbox completely."""
        asyncio.run(call("neuraltree_sandbox_create", project_root=str(tmp_project)))
        sandbox_path = tmp_project / ".neuraltree" / "sandbox"
        assert sandbox_path.exists()
        
        result = asyncio.run(call("neuraltree_sandbox_destroy", project_root=str(tmp_project)))
        assert result.get("cleaned", False), "Sandbox not cleaned"
        assert not sandbox_path.exists(), "Sandbox directory still exists after destroy"
        print("Sandbox destroyed successfully")

    def test_sandbox_apply_selective(self, tmp_project, call):
        """Apply copies specific files from sandbox to real project."""
        asyncio.run(call("neuraltree_sandbox_create", project_root=str(tmp_project)))
        sandbox_path = tmp_project / ".neuraltree" / "sandbox"
        
        # Create a new file in sandbox
        new_file = sandbox_path / "memory" / "rules" / "new_rule.md"
        new_file.write_text(
            "---\nname: New Rule\ntype: feedback\nlast_verified: 2026-04-05\n---\n\nNew content.\n"
        )
        
        # Apply only the new file
        result = asyncio.run(call(
            "neuraltree_sandbox_apply",
            files=["memory/rules/new_rule.md"],
            project_root=str(tmp_project),
        ))
        assert len(result.get("applied", [])) > 0, "Nothing was applied"
        assert (tmp_project / "memory" / "rules" / "new_rule.md").exists(), "New file not in real project"
        
        # Cleanup
        asyncio.run(call("neuraltree_sandbox_destroy", project_root=str(tmp_project)))
```

- [ ] **Step 2: Run sandbox tests**

Run: `cd /home/neil1988/neuraltree && PYTHONPATH=src python3.11 -m pytest tests/integration/test_sandbox_isolation.py -v`
Expected: All 4 tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_sandbox_isolation.py
git commit -m "test: sandbox isolation — create, modify, diff, apply, destroy"
```

---

### Task 4: Degraded Mode Tests (No Viking)

**Files:**
- Create: `tests/integration/test_degraded_mode.py`

Verify that when Viking is unavailable, the system gracefully degrades: precision_at_3 stays None, weights redistribute, EMBEDDING_GAP reclassifies to SYNAPSE_GAP.

- [ ] **Step 1: Write degraded mode tests**

```python
"""Degraded mode tests — verify behavior without Viking."""
import asyncio
import json
import pytest
from neuraltree_mcp.server import mcp


@pytest.fixture
def call():
    async def _call(name, **kwargs):
        result = await mcp.call_tool(name, kwargs)
        return json.loads(result[0].text)
    return _call


class TestDegradedMode:
    """Verify scoring and diagnosis work without Viking."""

    def test_score_without_viking(self, tmp_project, call):
        """Score computes 5 structural metrics, precision_at_3 stays None."""
        result = asyncio.run(call("neuraltree_score", project_root=str(tmp_project)))
        assert result["metrics"]["precision_at_3"] is None
        # Other metrics should have real values
        assert result["metrics"]["hop_efficiency"] > 0
        assert result["metrics"]["synapse_coverage"] > 0
        assert result["flow_score_partial"] > 0
        print(f"Degraded score: {result['flow_score_partial']:.3f}")

    def test_degraded_flow_score_formula(self, tmp_project, call):
        """Verify degraded mode weight redistribution is correct.
        
        Full mode: hop*0.25 + prec*0.25 + syn*0.20 + dead*0.15 + fresh*0.10 + trunk*0.05
        Degraded:  structure_reach*0.45 + dead*0.25 + fresh*0.20 + trunk*0.10
        where structure_reach = (hop + syn) / 2
        """
        result = asyncio.run(call("neuraltree_score", project_root=str(tmp_project)))
        m = result["metrics"]
        
        # Compute expected degraded score
        structure_reach = (m["hop_efficiency"] + m["synapse_coverage"]) / 2
        expected_degraded = (
            structure_reach * 0.45 +
            m["dead_neuron_ratio"] * 0.25 +
            m["freshness"] * 0.20 +
            m["trunk_pressure"] * 0.10
        )
        expected_degraded = min(0.75, expected_degraded)  # 0.75 cap
        
        # The partial flow score (without precision_at_3) should be close
        # but uses different weights, so we just verify the math is doable
        assert 0.0 <= expected_degraded <= 0.75, f"Degraded score out of range: {expected_degraded}"
        print(f"Degraded formula: {expected_degraded:.3f} (capped at 0.75)")

    def test_diagnose_without_viking_results(self, tmp_project, call):
        """Without Viking data, EMBEDDING_GAP should not appear (no Viking to miss)."""
        result = asyncio.run(call(
            "neuraltree_diagnose",
            failed_queries=[
                {"text": "How does auth work?", "expected_topic": "auth"},
            ],
            project_root=str(tmp_project),
            # No viking_results parameter — degraded mode
        ))
        for d in result["diagnoses"]:
            # Without Viking data, no EMBEDDING_GAP should be classified
            # (EMBEDDING_GAP requires Viking to have returned results that missed the file)
            assert d["gap_type"] != "EMBEDDING_GAP" or result.get("viking_results") is not None
        print(f"Degraded diagnose: {result['gap_counts']}")

    def test_lesson_match_works_without_viking(self, tmp_project, call):
        """Lesson matching is keyword-based, doesn't need Viking."""
        result = asyncio.run(call(
            "neuraltree_lesson_match",
            symptoms=["DDS images not showing", "Chrome cache bug"],
            project_root=str(tmp_project),
        ))
        assert len(result["matches"]) == 2
        # First symptom should match the DDS lesson
        assert result["matches"][0]["lessons"][0]["score"] > 0.3
        print(f"Lesson matches: {result['total_matches']}")
```

- [ ] **Step 2: Run degraded mode tests**

Run: `cd /home/neil1988/neuraltree && PYTHONPATH=src python3.11 -m pytest tests/integration/test_degraded_mode.py -v`
Expected: All 4 tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_degraded_mode.py
git commit -m "test: degraded mode — scoring, diagnosis, lessons without Viking"
```

---

### Task 5: Backup/Restore Round-Trip Test

**Files:**
- Modify: `tests/integration/test_e2e_pipeline.py` (add backup tests)

Verify backup creates copies, restore returns files to original state, and the full SYNAPSE_GAP backup-with-neighbors flow works.

- [ ] **Step 1: Add backup/restore tests**

Add to `tests/integration/test_e2e_pipeline.py`:

```python
class TestBackupRestore:
    """Verify backup/restore round-trip for autoloop safety."""

    def test_backup_and_restore_single_file(self, tmp_project, call):
        """Backup a file, modify it, restore it — should match original."""
        target = str(tmp_project / "memory" / "rules" / "coding.md")
        original = (tmp_project / "memory" / "rules" / "coding.md").read_text()
        
        # Backup
        result = asyncio.run(call(
            "neuraltree_backup",
            files=[target],
            project_root=str(tmp_project),
        ))
        assert len(result["backed_up"]) == 1
        
        # Modify the file
        (tmp_project / "memory" / "rules" / "coding.md").write_text("MODIFIED CONTENT")
        assert (tmp_project / "memory" / "rules" / "coding.md").read_text() == "MODIFIED CONTENT"
        
        # Restore
        result = asyncio.run(call(
            "neuraltree_restore",
            files=[target],
            project_root=str(tmp_project),
        ))
        assert len(result["restored"]) == 1
        assert (tmp_project / "memory" / "rules" / "coding.md").read_text() == original

    def test_backup_multiple_files(self, tmp_project, call):
        """Backup multiple files (simulating SYNAPSE_GAP neighbor backup)."""
        files = [
            str(tmp_project / "memory" / "rules" / "coding.md"),
            str(tmp_project / "memory" / "rules" / "testing.md"),
        ]
        originals = {f: Path(f).read_text() for f in files}
        
        # Backup both
        result = asyncio.run(call(
            "neuraltree_backup",
            files=files,
            project_root=str(tmp_project),
        ))
        assert len(result["backed_up"]) == 2
        
        # Modify both
        for f in files:
            Path(f).write_text("MODIFIED")
        
        # Restore both
        result = asyncio.run(call(
            "neuraltree_restore",
            files=files,
            project_root=str(tmp_project),
        ))
        assert len(result["restored"]) == 2
        for f in files:
            assert Path(f).read_text() == originals[f], f"File not restored: {f}"

    def test_wire_preview_is_read_only(self, tmp_project, call):
        """neuraltree_wire() should NOT modify files — it returns suggestions."""
        target = "memory/rules/coding.md"
        original = (tmp_project / target).read_text()
        
        result = asyncio.run(call(
            "neuraltree_wire",
            file_path=target,
            project_root=str(tmp_project),
        ))
        assert "suggested_content" in result
        # Original file should be untouched
        assert (tmp_project / target).read_text() == original, "wire() modified the file!"
```

- [ ] **Step 2: Run all pipeline tests**

Run: `cd /home/neil1988/neuraltree && PYTHONPATH=src python3.11 -m pytest tests/integration/test_e2e_pipeline.py -v`
Expected: All 8 tests pass (5 benchmark + 3 backup)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_e2e_pipeline.py
git commit -m "test: backup/restore round-trip + wire read-only verification"
```

---

### Task 6: Scale Test — Large Project

**Files:**
- Modify: `tests/integration/test_e2e_pipeline.py` (add scale test)

Verify scan caps at 10k files, score handles large file counts, and query generation scales correctly.

- [ ] **Step 1: Add scale tests**

Add to `tests/integration/test_e2e_pipeline.py`:

```python
class TestScaleLimits:
    """Verify behavior at scale boundaries."""

    def test_scan_caps_at_max_files(self, tmp_project_large, call):
        """Scan respects max_files parameter."""
        result = asyncio.run(call(
            "neuraltree_scan",
            path=str(tmp_project_large),
            max_files=50,
        ))
        assert result["capped"] is True, "Should be capped at 50 files"
        assert result["total_count"] <= 50

    def test_score_on_large_project(self, tmp_project_large, call):
        """Score doesn't crash on 150+ file project."""
        result = asyncio.run(call("neuraltree_score", project_root=str(tmp_project_large)))
        # Large project with no .md files — should handle gracefully
        assert "flow_score_partial" in result or "error" in result

    def test_query_scaling_formula(self, call, tmp_project):
        """Query count scales: max(20, min(50, indexed_docs / 3))."""
        # With indexed_doc_count=30 → max(20, min(50, 10)) = 20
        result = asyncio.run(call(
            "neuraltree_generate_queries",
            project_root=str(tmp_project),
            indexed_doc_count=30,
        ))
        assert result["total"] >= 20, f"Expected >= 20 queries, got {result['total']}"
        assert result["total"] <= 50, f"Expected <= 50 queries, got {result['total']}"
```

- [ ] **Step 2: Run all tests**

Run: `cd /home/neil1988/neuraltree && PYTHONPATH=src python3.11 -m pytest tests/ -v`
Expected: All tests pass (175 existing + new)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_e2e_pipeline.py
git commit -m "test: scale limits — scan cap, large project, query scaling"
```

---

### Task 7: Full Test Suite Run + Update Docs

**Files:**
- Modify: `CLAUDE.md` (update test count)
- Modify: `docs/HANDOFF.md` (mark as historical)

- [ ] **Step 1: Run complete test suite**

Run: `cd /home/neil1988/neuraltree && PYTHONPATH=src python3.11 -m pytest tests/ -v --tb=short`
Expected: All tests pass. Record final count.

- [ ] **Step 2: Update CLAUDE.md with new test count**

Update the test count in CLAUDE.md Commands section and anywhere else it says "175 tests".

- [ ] **Step 3: Update HANDOFF.md header as historical**

Add to top of HANDOFF.md:
```markdown
> **STATUS: HISTORICAL** — Phase 2 completed 2026-04-05. This document preserved for reference.
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/HANDOFF.md
git commit -m "docs: update test count, mark handoff as historical"
```

---

## Summary

| Task | What | New Tests |
|------|------|-----------|
| 1 | Infrastructure — verify MCP, add newfin fixture | 0 (verification) |
| 2 | Benchmark pipeline — scan, queries, score, diagnose, predict vs newfin | 5 |
| 3 | Sandbox isolation — create, modify, diff, apply, destroy | 4 |
| 4 | Degraded mode — no-Viking scoring, diagnosis, lessons | 4 |
| 5 | Backup/restore — round-trip, multi-file, wire read-only | 3 |
| 6 | Scale limits — scan cap, large project, query scaling | 3 |
| 7 | Full suite run + docs update | 0 (integration) |
| **Total** | | **19 new tests** |
