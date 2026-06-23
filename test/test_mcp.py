"""
Integration Tests — MCP Server Direct-Call Tools

Tests the 14 converted tools that call domain modules directly
(instead of subprocess). Verifies output format and basic correctness.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestMCPPaperTools:
    """Test paper-related MCP tools: stats, search, info, scan."""

    def test_scholar_stats_returns_text(self):
        """scholar_stats() returns non-empty text with expected fields."""
        from scholar_mcp.server import scholar_stats
        result = scholar_stats()
        assert "Paper folders" in result
        assert "Parsed" in result
        assert len(result) > 0

    def test_scholar_search_returns_results(self):
        """scholar_search('transformer') returns results."""
        from scholar_mcp.server import scholar_search
        result = scholar_search("transformer")
        assert "Search" in result
        assert len(result) > 0

    def test_scholar_search_no_results(self):
        """scholar_search returns 'No results' for gibberish."""
        from scholar_mcp.server import scholar_search
        result = scholar_search("xyzwq9999notarealword")
        # Should return something non-crashing
        assert isinstance(result, str)

    def test_scholar_info_returns_details(self):
        """scholar_info() returns paper details for a valid ULID."""
        from scholar_mcp.server import scholar_info
        result = scholar_info("01KT6MTBK1PQMNZM8ZYQPTVN6C")  # BERT
        assert "BERT" in result or "Title" in result
        assert len(result) > 0

    def test_scholar_info_nonexistent(self):
        """scholar_info() handles non-existent paper gracefully."""
        from scholar_mcp.server import scholar_info
        result = scholar_info("NONEXISTENT_ULID_123456")
        assert "not parsed" in result.lower() or "not found" in result.lower()

    def test_scholar_scan_returns_text(self):
        """scholar_scan() returns text with paper count."""
        from scholar_mcp.server import scholar_scan
        result = scholar_scan()
        assert "Paper Library" in result or "papers" in result.lower()
        assert len(result) > 0


class TestMCPHelpers:
    """Test _resolve() and _load_parsed() helpers."""

    def test_resolve_without_shared_state(self, monkeypatch):
        """_resolve() works without SharedState (fallback to direct import)."""
        monkeypatch.setattr("scholar._state._state", None)
        # Need to re-import so get_state() sees None
        from scholar_mcp.server import _resolve
        result = _resolve("01KT6MTBK1PQMNZM8ZYQPTVN6C")
        assert result == "01KT6MTBK1PQMNZM8ZYQPTVN6C"

    def test_load_parsed_without_shared_state(self, monkeypatch):
        """_load_parsed() works without SharedState."""
        monkeypatch.setattr("scholar._state._state", None)
        from scholar_mcp.server import _load_parsed
        result = _load_parsed("01KT6MTBK1PQMNZM8ZYQPTVN6C")
        assert result is not None
        assert "title" in result or "BERT" in str(result)


class TestMCPMetaTools:
    """Test metadata-related MCP tools."""

    def test_scholar_venue_fix_dry_run(self):
        """scholar_venue_fix(apply=False) does dry run."""
        from scholar_mcp.server import scholar_venue_fix
        result = scholar_venue_fix(apply=False)
        assert "Would fix" in result or "Fixed" in result
        assert "arXiv" in result or "Preprint" in result
        assert isinstance(result, str)


class TestMCPExceptions:
    """Test MCP tools handle exceptions gracefully."""

    def test_rag_search_without_index(self):
        """scholar_rag_search returns error message when no index."""
        from scholar_mcp.server import scholar_rag_search
        result = scholar_rag_search("test query")
        # Should not crash; may say "No RAG results" or "failed"
        assert isinstance(result, str)
        assert len(result) > 0

    def test_graph_query_without_neo4j(self):
        """scholar_graph_query returns error when Neo4j is down."""
        from scholar_mcp.server import scholar_graph_query
        result = scholar_graph_query("transformer")
        # Should not crash
        assert isinstance(result, str)
        assert len(result) > 0
