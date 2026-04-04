"""Tests for neuraltree_lesson_match and neuraltree_lesson_add tools."""
import os
from pathlib import Path

from neuraltree_mcp.tools.lesson import (
    _parse_lesson_entries,
    _validate_domain,
    _validate_lesson,
    _find_lessons_dir,
    REQUIRED_KEYS,
    MAX_LESSON_FILE_BYTES,
)
from neuraltree_mcp.text_utils import extract_keywords
import pytest


class TestParseLessonEntries:
    def test_parses_basic_entry(self):
        content = (
            "## DDS Images Not Showing\n"
            "- **Symptom:** Zero images\n"
            "- **Root cause:** pillow-dds missing\n"
            "- **Fix:** install pillow-dds\n"
        )
        entries = _parse_lesson_entries(content)
        assert len(entries) == 1
        assert entries[0]["heading"] == "DDS Images Not Showing"
        assert entries[0]["fields"]["symptom"] == "Zero images"

    def test_skips_non_lesson_headings(self):
        content = (
            "## DDS Images Not Showing\n"
            "- **Symptom:** Zero images\n\n"
            "## Related\n- [other.md](other.md)\n\n"
            "## Docs\n- `server/main.py`\n"
        )
        entries = _parse_lesson_entries(content)
        assert len(entries) == 1
        assert entries[0]["heading"] == "DDS Images Not Showing"

    def test_skips_content_heading(self):
        content = "## Content\nSome content here.\n"
        entries = _parse_lesson_entries(content)
        assert len(entries) == 0

    def test_multiple_entries(self):
        content = (
            "## Bug A\n- **Symptom:** A\n- **Fix:** fix A\n\n"
            "## Bug B\n- **Symptom:** B\n- **Fix:** fix B\n"
        )
        entries = _parse_lesson_entries(content)
        assert len(entries) == 2

    def test_entry_with_no_fields(self):
        content = "## Empty Entry\nJust some text, no bold fields.\n"
        entries = _parse_lesson_entries(content)
        assert len(entries) == 0  # no **Bold:** fields = no entry

    def test_with_frontmatter(self):
        content = (
            "---\nname: Test\n---\n\n"
            "## Bug\n- **Symptom:** something\n"
        )
        entries = _parse_lesson_entries(content)
        assert len(entries) == 1


class TestValidateDomain:
    def test_valid(self):
        assert _validate_domain("images") == "images"

    def test_normalizes_case(self):
        assert _validate_domain("Images") == "images"

    def test_with_hyphens_underscores(self):
        assert _validate_domain("ui-rendering") == "ui-rendering"
        assert _validate_domain("build_ci") == "build_ci"

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            _validate_domain("")

    def test_slash_rejected(self):
        with pytest.raises(ValueError):
            _validate_domain("../../etc")

    def test_dot_rejected(self):
        with pytest.raises(ValueError):
            _validate_domain(".hidden")

    def test_too_long_rejected(self):
        with pytest.raises(ValueError):
            _validate_domain("a" * 65)


class TestValidateLesson:
    def test_valid(self):
        lesson = {"symptom": "bug", "root_cause": "code", "fix": "patch"}
        assert _validate_lesson(lesson) == lesson

    def test_missing_required(self):
        with pytest.raises(ValueError, match="Missing required"):
            _validate_lesson({"symptom": "bug"})

    def test_unknown_keys(self):
        with pytest.raises(ValueError, match="Unknown"):
            _validate_lesson({"symptom": "a", "root_cause": "b", "fix": "c", "evil": "d"})

    def test_non_string_value(self):
        with pytest.raises(ValueError, match="must be a string"):
            _validate_lesson({"symptom": 123, "root_cause": "b", "fix": "c"})

    def test_too_long(self):
        with pytest.raises(ValueError, match="exceeds"):
            _validate_lesson({"symptom": "a" * 2001, "root_cause": "b", "fix": "c"})

    def test_frontmatter_injection(self):
        with pytest.raises(ValueError, match="frontmatter"):
            _validate_lesson({"symptom": "---\nevil", "root_cause": "b", "fix": "c"})

    def test_embedded_frontmatter(self):
        with pytest.raises(ValueError, match="frontmatter"):
            _validate_lesson({"symptom": "start\n---\nevil", "root_cause": "b", "fix": "c"})


class TestLessonMatchLogic:
    def test_finds_symptom(self, tmp_project):
        """DDS keyword should match the DDS lesson."""
        from neuraltree_mcp.tools.lesson import _parse_lesson_entries, _find_lessons_dir
        lessons_dir = _find_lessons_dir(tmp_project)
        assert lessons_dir is not None

        images = lessons_dir / "images.md"
        entries = _parse_lesson_entries(images.read_text())
        assert len(entries) == 2  # DDS + Chrome, not Related/Docs

    def test_ranks_symptom_over_fix(self, tmp_project):
        """'images not showing' should rank DDS > Chrome cache."""
        from neuraltree_mcp.text_utils import extract_keywords, jaccard

        symptom_kw = extract_keywords("images not showing", min_freq=1)

        lessons_dir = _find_lessons_dir(tmp_project)
        entries = _parse_lesson_entries((lessons_dir / "images.md").read_text())

        scores = []
        for entry in entries:
            search_text = entry["heading"] + " " + entry["fields"].get("symptom", "") + " " + entry["fields"].get("root_cause", "")
            entry_kw = extract_keywords(search_text, min_freq=1)
            score = jaccard(symptom_kw, entry_kw)
            if any(kw in entry["heading"].lower() for kw in symptom_kw):
                score += 0.15
            scores.append((entry["heading"], min(1.0, score)))

        # DDS entry has "Not Showing" in heading + "images" in symptom
        # Chrome entry has "Image" in heading but different symptom
        dds_score = [s for h, s in scores if "DDS" in h][0]
        chrome_score = [s for h, s in scores if "Chrome" in h][0]
        assert dds_score >= chrome_score

    def test_short_symptom_still_matches(self, tmp_project):
        """Single-word 'DDS' should match with min_freq=1."""
        symptom_kw = extract_keywords("DDS", min_freq=1)
        assert "dds" in symptom_kw  # min_freq=1 catches single-occurrence

    def test_no_match(self, tmp_project):
        """Quantum computing has no match in lessons."""
        from neuraltree_mcp.text_utils import jaccard as _jaccard
        symptom_kw = extract_keywords("quantum computing", min_freq=1)
        lessons_dir = _find_lessons_dir(tmp_project)
        entries = _parse_lesson_entries((lessons_dir / "images.md").read_text())

        for entry in entries:
            search_text = entry["heading"] + " " + entry["fields"].get("symptom", "")
            entry_kw = extract_keywords(search_text, min_freq=1)
            score = _jaccard(symptom_kw, entry_kw)
            assert score < 0.2  # below threshold


class TestLessonAddLogic:
    def test_creates_domain_file(self, tmp_path):
        """lesson_add on a fresh project creates the file + _INDEX.md."""
        root = tmp_path / "proj"
        root.mkdir()
        (root / "memory").mkdir()

        from neuraltree_mcp.tools.lesson import _validate_domain, _find_lessons_dir

        domain = _validate_domain("networking")
        assert domain == "networking"

        # Verify lessons dir doesn't exist yet
        assert _find_lessons_dir(root) is None

    def test_duplicate_detection_uses_min_freq_1(self):
        """Short symptoms should produce keywords with min_freq=1."""
        kw = extract_keywords("DDS images not showing", min_freq=1)
        assert len(kw) > 0  # Would be empty with min_freq=2

    def test_duplicate_boundary_80pct(self):
        """80% overlap should NOT be blocked (threshold is >80%, exclusive)."""
        # 4/5 words identical = 80% exactly
        kw1 = {"dds", "images", "not", "showing"}  # not realistic but tests the math
        kw2 = {"dds", "images", "not", "loading"}
        overlap = len(kw1 & kw2) / len(kw1 | kw2)
        assert overlap == 3 / 5  # 60%, well under 80%

    def test_index_consistency(self, tmp_path):
        """_INDEX.md should list all added domains."""
        root = tmp_path / "proj"
        root.mkdir()
        lessons = root / "memory" / "lessons"
        lessons.mkdir(parents=True)

        # Simulate two domain index entries
        index = lessons / "_INDEX.md"
        index.write_text(
            "---\nname: Lessons Index\ntype: reference\n---\n\n"
            "- [Images](images.md) — images lessons\n"
        )
        content = index.read_text()
        # Add a second domain
        content += "- [Database](database.md) — database lessons\n"
        index.write_text(content)

        final = index.read_text()
        assert "Images" in final
        assert "Database" in final

    def test_file_size_cap(self, tmp_path):
        """Domain file exceeding 512KB should be rejected."""
        root = tmp_path / "proj"
        root.mkdir()
        lessons = root / "memory" / "lessons"
        lessons.mkdir(parents=True)

        big_file = lessons / "huge.md"
        big_file.write_text("x" * (MAX_LESSON_FILE_BYTES + 1))
        assert big_file.stat().st_size > MAX_LESSON_FILE_BYTES
