"""
Test cite_resolve.py — citation resolution pipeline.
Tests DOI matching, title fuzzy matching, and normalization.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from scholar.cite_resolve import (
    _normalize,
    _title_similarity,
    _HAS_RAPIDFUZZ,
    build_internal_index,
    match_via_doi,
    match_via_title,
    resolve_citations,
)


class TestNormalize:
    """Test _normalize function."""

    def test_lowercase(self):
        assert _normalize("Attention Is All You Need") == "attention is all you need"

    def test_remove_punctuation(self):
        assert _normalize("Hello, World!") == "hello world"

    def test_collapse_whitespace(self):
        assert _normalize("a  b   c") == "a b c"

    def test_empty(self):
        assert _normalize("") == ""

    def test_none(self):
        assert _normalize(None) == ""


class TestTitleSimilarity:
    """Test _title_similarity function."""

    def test_identical(self):
        score = _title_similarity("attention is all you need", "attention is all you need")
        assert score == 100.0

    def test_word_reorder(self):
        """rapidfuzz token_sort_ratio should handle word reordering."""
        score = _title_similarity("attention is all you need", "you need all attention is")
        assert score >= 85

    def test_completely_different(self):
        score = _title_similarity("attention mechanism", "image classification")
        assert score < 50

    def test_partial_match(self):
        score = _title_similarity("bert", "bert pre-training of deep bidirectional transformers")
        # partial_ratio might score high, but token_sort_ratio won't
        # Just check it doesn't crash
        assert isinstance(score, (int, float))


class TestMatchViaDOI:
    """Test match_via_doi function."""

    def test_exact_match(self):
        index = {
            "titles": {},
            "dois": {"10.5555/3295222.3295349": {"ulid": "abc", "title": "Attention", "year": 2017}},
            "count": 1,
        }
        result = match_via_doi("10.5555/3295222.3295349", index)
        assert result is not None
        assert result["ulid"] == "abc"

    def test_case_insensitive(self):
        index = {
            "titles": {},
            "dois": {"10.1000/test": {"ulid": "xyz", "title": "Test", "year": 2024}},
            "count": 1,
        }
        result = match_via_doi("10.1000/TEST", index)
        assert result is not None

    def test_no_match(self):
        index = {"titles": {}, "dois": {}, "count": 0}
        result = match_via_doi("10.9999/nonexistent", index)
        assert result is None

    def test_empty_doi(self):
        index = {"titles": {}, "dois": {"10.1000/test": {"ulid": "x"}}, "count": 1}
        result = match_via_doi("", index)
        assert result is None


class TestMatchViaTitle:
    """Test match_via_title function."""

    def test_exact_normalized_match(self):
        index = {
            "titles": {"attention is all you need": {"ulid": "abc", "title": "Attention Is All You Need", "year": 2017}},
            "dois": {},
            "count": 1,
        }
        result = match_via_title("Attention Is All You Need", index)
        assert result is not None
        assert result["ulid"] == "abc"

    def test_fuzzy_match(self):
        index = {
            "titles": {"deep residual learning for image recognition": {"ulid": "res", "title": "Deep Residual Learning for Image Recognition", "year": 2016}},
            "dois": {},
            "count": 1,
        }
        result = match_via_title("Deep Residual Learning for Image Recognition", index, threshold=85)
        assert result is not None

    def test_no_match_low_similarity(self):
        index = {
            "titles": {"attention is all you need": {"ulid": "att"}},
            "dois": {},
            "count": 1,
        }
        result = match_via_title("completely unrelated title about cooking", index, threshold=85)
        assert result is None

    def test_empty_title(self):
        index = {"titles": {"test": {"ulid": "x"}}, "dois": {}, "count": 1}
        result = match_via_title("", index)
        assert result is None


class TestBuildInternalIndex:
    """Test build_internal_index function."""

    def test_with_mock_data(self, tmp_path):
        """Test index building with mock JSON files."""
        # Create mock parsed JSON files
        paper1 = tmp_path / "paper1.json"
        paper1.write_text(json.dumps({
            "paper_id": "ULID001",
            "title": "Attention Is All You Need",
            "year": 2017,
            "doi": "10.5555/3295222.3295349",
        }), encoding="utf-8")

        paper2 = tmp_path / "paper2.json"
        paper2.write_text(json.dumps({
            "paper_id": "ULID002",
            "title": "BERT",
            "year": 2019,
            "doi": "",
        }), encoding="utf-8")

        index = build_internal_index(tmp_path)

        assert index["count"] == 2
        assert "attention is all you need" in index["titles"]
        assert "bert" in index["titles"]
        assert "10.5555/3295222.3295349" in index["dois"]

    def test_empty_directory(self, tmp_path):
        index = build_internal_index(tmp_path)
        assert index["count"] == 0


class TestResolveCitations:
    """Test resolve_citations pipeline (integration)."""

    def test_dry_run_no_errors(self, tmp_path):
        """Test that dry_run mode doesn't crash and returns stats."""
        # Create a paper with citations
        paper = tmp_path / "paper.json"
        paper.write_text(json.dumps({
            "paper_id": "TEST001",
            "title": "Test Paper",
            "year": 2024,
            "doi": "",
            "citations": ["ref1", "ref2"],
            "bibliography": [
                {"ref_key": "ref1", "title": "Some Paper", "authors": [], "year": 2023, "doi": ""},
                {"ref_key": "ref2", "title": "Another Paper", "authors": [], "year": 2022, "doi": ""},
            ],
        }), encoding="utf-8")

        with patch("scholar.cite_resolve.config.PARSED_DIR", tmp_path):
            with patch("scholar.cite_resolve.config.OUTPUT_DIR", tmp_path):
                result = resolve_citations(parsed_dir=tmp_path, dry_run=True)

        assert result["total_refs"] == 2
        assert "resolution_rate" in result
        assert result["has_rapidfuzz"] == _HAS_RAPIDFUZZ
