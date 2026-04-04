"""Shared test fixtures for neuraltree tests."""
import os
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_project(tmp_path):
    """Create a mock project structure for testing.

    Returns a Path to a temporary directory with:
    - CLAUDE.md (nav hub with glossary)
    - memory/MEMORY.md (trunk)
    - memory/rules/_INDEX.md (branch index)
    - memory/rules/coding.md (leaf with ## Related + ## Docs)
    - memory/rules/testing.md (leaf with ## Related + ## Docs)
    - memory/reference/auth.md (leaf, NO wiring — orphan)
    - docs/INDEX.md
    - docs/architecture/SUMMARY.md
    - server/main.py (source file)
    - .github/workflows/build.yml (CI workflow)
    """
    p = tmp_path / "mock_project"
    p.mkdir()

    # CLAUDE.md
    (p / "CLAUDE.md").write_text(
        "# CLAUDE.md\n\n"
        "## Glossary\n\n"
        "| Term | Meaning |\n"
        "|------|---------|\n"
        "| **TM** | Translation Memory |\n"
        "| **LDM** | Language Data Manager |\n"
        "| **GDP** | Granular Debug Protocol |\n\n"
        "## Quick Navigation\n\n"
        "| Need | Go To |\n"
        "|------|-------|\n"
        "| **Architecture** | docs/architecture/SUMMARY.md |\n"
        "| **Current task** | memory/active/_INDEX.md |\n"
    )

    # memory/
    mem = p / "memory"
    mem.mkdir()
    (mem / "MEMORY.md").write_text(
        "# Memory Trunk\n\n"
        "- [Rules](rules/_INDEX.md) — behavioral rules\n"
        "- [Reference](reference/) — stable facts\n"
    )

    rules = mem / "rules"
    rules.mkdir()
    (rules / "_INDEX.md").write_text(
        "---\nname: Rules Index\ntype: reference\nlast_verified: 2026-04-04\n---\n\n"
        "| Topic | File |\n"
        "|-------|------|\n"
        "| Coding | [coding.md](coding.md) |\n"
        "| Testing | [testing.md](testing.md) |\n"
    )
    (rules / "coding.md").write_text(
        "---\nname: Coding Rules\ntype: feedback\nlast_verified: 2026-04-04\n---\n\n"
        "## Rules\n- Always use type hints\n- Read source before modifying\n\n"
        "## Related\n- [testing.md](testing.md) — test patterns\n\n"
        "## Docs\n- `server/main.py` — backend entry point\n"
    )
    (rules / "testing.md").write_text(
        "---\nname: Testing Rules\ntype: feedback\nlast_verified: 2026-03-01\n---\n\n"
        "## Rules\n- API-first testing\n- Playwright screenshots\n\n"
        "## Related\n- [coding.md](coding.md) — code patterns\n\n"
        "## Docs\n- `tests/` — test suites\n"
    )

    ref = mem / "reference"
    ref.mkdir()
    # Orphan file — no ## Related, no ## Docs, not in any index
    (ref / "auth.md").write_text(
        "---\nname: Auth Model\ntype: reference\nlast_verified: 2025-12-01\n---\n\n"
        "## Content\nLAN auth uses IP-lock admin.\n"
    )

    # docs/
    docs = p / "docs"
    docs.mkdir()
    (docs / "INDEX.md").write_text(
        "# Docs Index\n\n"
        "- [architecture/SUMMARY.md](architecture/SUMMARY.md)\n"
    )
    arch = docs / "architecture"
    arch.mkdir()
    (arch / "SUMMARY.md").write_text("# Architecture Summary\n\n99% client-side.\n")

    # server/
    server = p / "server"
    server.mkdir()
    (server / "main.py").write_text("# FastAPI backend\nfrom fastapi import FastAPI\napp = FastAPI()\n")

    # .github/workflows/
    gh = p / ".github" / "workflows"
    gh.mkdir(parents=True)
    (gh / "build.yml").write_text(
        "name: Build\non: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - uses: actions/checkout@v4\n"
    )

    # empty dir (should be detected by scan)
    (p / "archive" / "old_code").mkdir(parents=True)

    # memory/lessons/ — incident memory layer
    lessons = mem / "lessons"
    lessons.mkdir()
    (lessons / "_INDEX.md").write_text(
        "---\nname: Lessons Index\ntype: reference\nlast_verified: 2026-04-04\n---\n\n"
        "- [Images](images.md) — image pipeline lessons\n"
        "- [Database](database.md) — DB/PG lessons\n"
    )
    (lessons / "images.md").write_text(
        "---\nname: Image Lessons\ndescription: Past image issues\n"
        "type: reference\nlast_verified: 2026-04-04\n---\n\n"
        "## DDS Images Not Showing (Phase 113)\n"
        "- **Symptom:** Zero images in Codex on PEARL\n"
        "- **Root cause:** pillow-dds not installed\n"
        "- **Fix:** import pillow_dds in media_converter.py\n"
        "- **Key file:** `server/tools/media_converter.py`\n"
        "- **Lesson:** Always check if format handlers are installed\n\n"
        "## Chrome Image Cache Bug (DOC-003)\n"
        "- **Symptom:** Old images persist after update\n"
        "- **Root cause:** Chrome caches 404 responses permanently\n"
        "- **Fix:** Cache-bust with ?v=${Date.now()} on image URLs\n"
        "- **Key file:** `locaNext/src/components/ImageViewer.svelte`\n"
        "- **Lesson:** Chrome caches ERRORS too, not just successes\n\n"
        "## Related\n- [database.md](database.md) — cross-domain\n\n"
        "## Docs\n- `server/tools/media_converter.py` — DDS conversion\n"
        "- `locaNext/src/components/ImageViewer.svelte` — image display\n"
    )
    # database.md — stale, unwired (no ## Related, no ## Docs)
    (lessons / "database.md").write_text(
        "---\nname: Database Lessons\ndescription: Past DB issues\n"
        "type: reference\nlast_verified: 2025-06-01\n---\n\n"
        "## PG Connection Refused\n"
        "- **Symptom:** Cannot connect to PostgreSQL after router reboot\n"
        "- **Root cause:** LAN IP changed, pg_hba.conf had old IP\n"
        "- **Fix:** Update pg_hba.conf with new subnet range\n"
        "- **Key file:** `config/pg_hba.conf`\n"
    )

    return p


@pytest.fixture
def tmp_project_large(tmp_path):
    """Create a large mock project (100+ files) for scale testing."""
    p = tmp_path / "large_project"
    p.mkdir()
    (p / "CLAUDE.md").write_text("# Large Project\n")

    # Create 150 files across dirs
    for i in range(15):
        d = p / f"module_{i}"
        d.mkdir()
        for j in range(10):
            (d / f"file_{j}.py").write_text(f"# Module {i}, File {j}\n")

    return p


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
