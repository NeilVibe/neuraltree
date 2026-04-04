"""Tests for shared text utilities."""
from neuraltree_mcp.text_utils import (
    extract_keywords, jaccard, extract_backtick_paths, walk_project_files,
    STOPWORDS, SKIP_DIRS,
)


class TestExtractKeywords:
    def test_basic(self):
        content = "The server auth module handles auth logic for server requests."
        kw = extract_keywords(content)
        assert "auth" in kw
        assert "server" in kw

    def test_stopwords_removed(self):
        content = "The the the is is is for for for."
        assert len(extract_keywords(content)) == 0

    def test_min_freq_1(self):
        content = "unique_word appears once."
        kw = extract_keywords(content, min_freq=1)
        assert "unique_word" in kw

    def test_min_freq_2_default(self):
        content = "unique_word appears once."
        kw = extract_keywords(content)  # default min_freq=2
        assert "unique_word" not in kw

    def test_empty_content(self):
        assert len(extract_keywords("")) == 0


class TestJaccard:
    def test_identical(self):
        assert jaccard({"a", "b", "c"}, {"a", "b", "c"}) == 1.0

    def test_disjoint(self):
        assert jaccard({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial(self):
        result = jaccard({"a", "b"}, {"b", "c"})
        assert abs(result - 1 / 3) < 0.01

    def test_empty(self):
        assert jaccard(set(), set()) == 0.0


class TestExtractBacktickPaths:
    def test_basic(self):
        content = "See `server/main.py` and `config/settings.json`."
        paths = extract_backtick_paths(content)
        assert "server/main.py" in paths
        assert "config/settings.json" in paths

    def test_no_paths(self):
        assert len(extract_backtick_paths("No paths here.")) == 0


class TestWalkProjectFiles:
    def test_finds_files(self, tmp_project):
        files = walk_project_files(tmp_project)
        assert len(files) > 0

    def test_skips_dirs(self, tmp_project):
        # Create a __pycache__ with a file
        pycache = tmp_project / "__pycache__"
        pycache.mkdir()
        (pycache / "mod.pyc").write_text("bytecode")

        files = walk_project_files(tmp_project)
        assert not any("__pycache__" in str(f) for f in files)

    def test_extension_filter(self, tmp_project):
        md_files = walk_project_files(tmp_project, {".md"})
        assert all(f.suffix == ".md" for f in md_files)
        assert len(md_files) > 0

    def test_empty_dir(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert walk_project_files(empty) == []
