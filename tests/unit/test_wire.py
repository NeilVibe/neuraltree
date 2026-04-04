"""Tests for neuraltree_wire tool."""
from neuraltree_mcp.text_utils import extract_keywords as _extract_keywords, jaccard as _jaccard, extract_backtick_paths as _extract_backtick_paths


class TestExtractKeywords:
    def test_basic_extraction(self):
        content = "The server auth module handles auth logic for server requests."
        keywords = _extract_keywords(content)
        assert "auth" in keywords
        assert "server" in keywords

    def test_stopwords_removed(self):
        content = "The the the is is is for for for."
        keywords = _extract_keywords(content)
        assert len(keywords) == 0

    def test_min_frequency(self):
        content = "unique_word appears once. repeated_word appears repeated_word again."
        keywords = _extract_keywords(content)
        assert "unique_word" not in keywords  # only once
        assert "repeated_word" in keywords  # twice

    def test_empty_content(self):
        keywords = _extract_keywords("")
        assert len(keywords) == 0

    def test_short_words_excluded(self):
        content = "go to do it is me go to do it"
        keywords = _extract_keywords(content)
        assert len(keywords) == 0  # all <= 2 chars or stopwords


class TestJaccard:
    def test_identical_sets(self):
        assert _jaccard({"a", "b", "c"}, {"a", "b", "c"}) == 1.0

    def test_disjoint_sets(self):
        assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        # {a, b} & {b, c} = {b}, union = {a, b, c} => 1/3
        result = _jaccard({"a", "b"}, {"b", "c"})
        assert abs(result - 1 / 3) < 0.01

    def test_empty_sets(self):
        assert _jaccard(set(), set()) == 0.0

    def test_one_empty(self):
        assert _jaccard({"a"}, set()) == 0.0


class TestExtractBacktickPaths:
    def test_basic_paths(self):
        content = "See `server/main.py` and `config/settings.json` for details."
        paths = _extract_backtick_paths(content)
        assert "server/main.py" in paths
        assert "config/settings.json" in paths

    def test_no_paths(self):
        content = "No backtick paths here."
        paths = _extract_backtick_paths(content)
        assert len(paths) == 0

    def test_code_blocks_ignored(self):
        # Simple backtick code without file extension
        content = "Use `print()` for debugging."
        paths = _extract_backtick_paths(content)
        # print() doesn't match the pattern (no file extension)
        assert "print()" not in paths


class TestWireIntegration:
    def test_coding_and_testing_are_related(self, tmp_project):
        """coding.md and testing.md share keywords and should score as related."""
        coding = tmp_project / "memory" / "rules" / "coding.md"
        testing = tmp_project / "memory" / "rules" / "testing.md"

        coding_kw = _extract_keywords(coding.read_text())
        testing_kw = _extract_keywords(testing.read_text())

        # They should have SOME shared keywords (rules, related, etc.)
        shared = coding_kw & testing_kw
        score = _jaccard(coding_kw, testing_kw)

        # With directory boost (+0.05) and potential docs boost (+0.1),
        # these should be related
        assert score > 0 or len(shared) > 0

    def test_orphan_has_low_connectivity(self, tmp_project):
        """auth.md (orphan) should have lower keyword overlap with wired files."""
        auth = tmp_project / "memory" / "reference" / "auth.md"
        coding = tmp_project / "memory" / "rules" / "coding.md"

        auth_kw = _extract_keywords(auth.read_text())
        coding_kw = _extract_keywords(coding.read_text())

        score = _jaccard(auth_kw, coding_kw)
        # Orphan should have low similarity with wired files
        assert score < 0.5

    def test_backtick_docs_extracted(self, tmp_project):
        """coding.md should have server/main.py as a ## Docs reference."""
        coding = tmp_project / "memory" / "rules" / "coding.md"
        paths = _extract_backtick_paths(coding.read_text())
        assert "server/main.py" in paths
