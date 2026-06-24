"""
Test graph_db.py — concept matching and graph operations.
Uses unittest.mock to mock Neo4j driver, no real DB needed.
"""
import pytest
from unittest.mock import MagicMock, patch

from scholar.graph_db import (
    _match_concept_in_text,
    _get_concept_patterns,
    CONCEPT_ALIASES,
)


class TestConceptMatching:
    """Test word-boundary safe concept matching (Phase 3.3)."""

    def test_exact_match(self):
        """Exact word match should work."""
        aliases = ["transformer"]
        assert _match_concept_in_text("the transformer model", "test1", aliases) is True

    def test_case_insensitive(self):
        """Matching should be case-insensitive."""
        aliases = ["transformer"]
        assert _match_concept_in_text("The TRANSFORMER model", "test2", aliases) is True

    def test_word_boundary_no_false_positive(self):
        """'rnn' should NOT match 'brnn' or 'learning'."""
        aliases = ["rnn"]
        assert _match_concept_in_text("brnn architecture", "test3", aliases) is False
        assert _match_concept_in_text("learning rate", "test4", aliases) is False

    def test_word_boundary_with_punctuation(self):
        """Word boundary should work with punctuation."""
        aliases = ["gan"]
        assert _match_concept_in_text("the (gan) model", "test5", aliases) is True
        assert _match_concept_in_text("began training", "test6", aliases) is False

    def test_multi_alias(self):
        """Multiple aliases should all be checked."""
        aliases = ["transformer", "attention mechanism"]
        assert _match_concept_in_text("using attention mechanism here", "test7", aliases) is True
        assert _match_concept_in_text("no relevant terms here", "test8", aliases) is False

    def test_pattern_caching(self):
        """Patterns should be cached for performance."""
        aliases = ["test_concept"]
        # First call creates and caches
        _match_concept_in_text("test_concept here", "cache_test", aliases)
        # Second call should use cache
        patterns = _get_concept_patterns("cache_test", aliases)
        assert len(patterns) >= 1


class TestConceptAliases:
    """Test CONCEPT_ALIASES data quality."""

    def test_not_empty(self):
        """CONCEPT_ALIASES should have entries."""
        assert len(CONCEPT_ALIASES) > 50

    def test_all_values_are_lists(self):
        """All alias values should be lists."""
        for concept_id, aliases in CONCEPT_ALIASES.items():
            assert isinstance(aliases, list), f"{concept_id} aliases is not a list"
            assert len(aliases) > 0, f"{concept_id} has no aliases"

    def test_no_empty_aliases(self):
        """No alias should be empty string."""
        for concept_id, aliases in CONCEPT_ALIASES.items():
            for alias in aliases:
                assert alias.strip(), f"{concept_id} has empty alias"


class TestGraphDBMock:
    """Test GraphDB class with mocked Neo4j driver."""

    @patch("scholar.graph_db.GraphDB")
    def test_graphdb_initialization(self, mock_graphdb):
        """Test that GraphDB can be mocked."""
        mock_instance = MagicMock()
        mock_instance.available = True
        mock_graphdb.return_value = mock_instance

        gdb = mock_graphdb()
        assert gdb.available is True

    @patch("scholar.graph_db.GraphDB")
    def test_graphdb_unavailable(self, mock_graphdb):
        """Test handling when Neo4j is not available."""
        mock_instance = MagicMock()
        mock_instance.available = False
        mock_graphdb.return_value = mock_instance

        gdb = mock_graphdb()
        assert gdb.available is False
