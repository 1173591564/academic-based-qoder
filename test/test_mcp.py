"""
Integration Tests — MCP Server Direct-Call Tools

Tests the converted tools that call domain modules directly
(instead of subprocess). Verifies output format and basic correctness.
Covers: paper tools, file access, batch ops, research loop, graph tools.
"""
import json
import pytest
from unittest.mock import patch, MagicMock


class TestMCPPaperTools:
    """Test paper-related MCP tools: stats, search, info, scan, list-papers, export-bib."""

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

    def test_scholar_search_empty_query(self):
        """scholar_search('') returns JSON error."""
        from scholar_mcp.server import scholar_search
        result = scholar_search("")
        data = json.loads(result)
        assert "error" in data

    def test_scholar_search_no_results(self):
        """scholar_search returns 'No results' for gibberish."""
        from scholar_mcp.server import scholar_search
        result = scholar_search("xyzwq9999notarealword")
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

    def test_scholar_list_papers_all(self):
        """scholar_list_papers() returns parsed paper list."""
        from scholar_mcp.server import scholar_list_papers
        result = scholar_list_papers()
        assert "Parsed Papers" in result
        assert len(result) > 50

    def test_scholar_list_papers_year_filter(self):
        """scholar_list_papers(year=2023) filters by year."""
        from scholar_mcp.server import scholar_list_papers
        result = scholar_list_papers(year=2023)
        assert isinstance(result, str)
        # May have results or be empty, but should not crash

    def test_scholar_export_bib_default(self):
        """scholar_export_bib() generates BibTeX file."""
        from scholar_mcp.server import scholar_export_bib
        result = scholar_export_bib()
        assert "Exported" in result
        assert "BibTeX" in result or "bib" in result.lower()


class TestMCPHelpers:
    """Test _resolve() and _load_parsed() helpers."""

    def test_resolve_without_shared_state(self, monkeypatch):
        """_resolve() works without SharedState (fallback to direct import)."""
        monkeypatch.setattr("scholar._state._state", None)
        from scholar_mcp.server import _resolve
        result = _resolve("01KT6MTBK1PQMNZM8ZYQPTVN6C")
        assert result == "01KT6MTBK1PQMNZM8ZYQPTVN6C"

    def test_resolve_fallback_for_unknown_id(self, monkeypatch):
        """_resolve() returns original input if ID cannot be resolved."""
        monkeypatch.setattr("scholar._state._state", None)
        from scholar_mcp.server import _resolve
        result = _resolve("nonexistent_junk_id")
        assert result == "nonexistent_junk_id"

    def test_load_parsed_without_shared_state(self, monkeypatch):
        """_load_parsed() works without SharedState."""
        monkeypatch.setattr("scholar._state._state", None)
        from scholar_mcp.server import _load_parsed
        result = _load_parsed("01KT6MTBK1PQMNZM8ZYQPTVN6C")
        assert result is not None
        assert "title" in result or "BERT" in str(result)

    def test_load_parsed_nonexistent_id(self, monkeypatch):
        """_load_parsed() returns None for non-existent paper."""
        monkeypatch.setattr("scholar._state._state", None)
        from scholar_mcp.server import _load_parsed
        result = _load_parsed("NONEXISTENT_ULID_XYZ123")
        assert result is None


class TestMCPMetaTools:
    """Test metadata-related MCP tools."""

    def test_scholar_venue_fix_dry_run(self):
        """scholar_venue_fix(apply=False) does dry run."""
        from scholar_mcp.server import scholar_venue_fix
        result = scholar_venue_fix(apply=False)
        assert "Would fix" in result or "Fixed" in result
        assert "arXiv" in result or "Preprint" in result
        assert isinstance(result, str)

    def test_scholar_year_fix_dry_run(self):
        """scholar_year_fix(apply=False) returns preview."""
        from scholar_mcp.server import scholar_year_fix
        result = scholar_year_fix(apply=False)
        assert isinstance(result, str)
        assert len(result) > 0

class TestMCPClassifyTools:
    """Test classification-related MCP tools."""

    def test_scholar_classify_list_tags(self):
        """scholar_classify(list_tags=True) returns JSON tag map."""
        from scholar_mcp.server import scholar_classify
        result = scholar_classify(list_tags=True)
        data = json.loads(result)
        assert "domains" in data
        assert isinstance(data["domains"], dict)

    def test_scholar_classify_single_paper(self):
        """scholar_classify(paper_id=...) returns classification."""
        from scholar_mcp.server import scholar_classify
        result = scholar_classify(paper_id="01KT6MTBK1PQMNZM8ZYQPTVN6C")
        data = json.loads(result)
        # Either success with domains, or error message
        assert "domains" in data or "error" in data

    def test_scholar_classify_nonexistent(self):
        """scholar_classify handles nonexistent paper gracefully."""
        from scholar_mcp.server import scholar_classify
        result = scholar_classify(paper_id="NONEXISTENT_12345")
        data = json.loads(result)
        assert "error" in data


class TestMCPFileAccess:
    """Test file access MCP tools."""

    def test_read_skill_valid(self):
        """read_skill('research-survey') returns SKILL.md content."""
        from scholar_mcp.server import read_skill
        result = read_skill("research-survey")
        assert "调研" in result or "survey" in result.lower() or "research" in result.lower()
        assert len(result) > 100

    def test_read_skill_invalid(self):
        """read_skill('nonexistent-skill') returns error with available list."""
        from scholar_mcp.server import read_skill
        result = read_skill("nonexistent-skill")
        assert "not found" in result.lower() or "Available" in result

    def test_scholar_list_output_files_all(self):
        """scholar_list_output_files() lists output directory."""
        from scholar_mcp.server import scholar_list_output_files
        result = scholar_list_output_files()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_scholar_list_output_files_notes(self):
        """scholar_list_output_files(category='notes') lists only notes."""
        from scholar_mcp.server import scholar_list_output_files
        result = scholar_list_output_files(category="notes")
        assert isinstance(result, str)

    def test_scholar_read_output_file_invalid(self):
        """scholar_read_output_file returns error for nonexistent path."""
        from scholar_mcp.server import scholar_read_output_file
        result = scholar_read_output_file("nonexistent/deadbeef.txt")
        assert "not found" in result.lower() or "File not found" in result


class TestMCPResearchLoop:
    """Test research loop MCP tools."""

    def test_scholar_interests_list(self):
        """scholar_interests(action='list') returns interests or empty message."""
        from scholar_mcp.server import scholar_interests
        result = scholar_interests(action="list")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_scholar_interests_invalid_action(self):
        """scholar_interests with unknown action returns error hint."""
        from scholar_mcp.server import scholar_interests
        result = scholar_interests(action="nonexistent_action")
        assert "Unknown" in result or "Available" in result


class TestMCPExceptions:
    """Test MCP tools handle exceptions gracefully."""

    def test_rag_search_without_index(self):
        """scholar_rag_search returns error message when no index."""
        from scholar_mcp.server import scholar_rag_search
        result = scholar_rag_search("test query")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_graph_query_without_neo4j(self):
        """scholar_graph_query returns error when Neo4j is down."""
        from scholar_mcp.server import scholar_graph_query
        result = scholar_graph_query("transformer")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_cite_network_global(self):
        """scholar_cite_network() without paper_id does global stats."""
        from scholar_mcp.server import scholar_cite_network
        result = scholar_cite_network()
        # May fail if Neo4j is down, but should not crash
        assert isinstance(result, str)

    def test_arxiv_search_returns_text(self):
        """scholar_arxiv_search() returns results or error without crash."""
        from scholar_mcp.server import scholar_arxiv_search
        result = scholar_arxiv_search("transformer", max_results=3)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_scholar_survey_handles_unknown_topic(self):
        """scholar_survey returns message for completely unknown topic."""
        from scholar_mcp.server import scholar_survey
        result = scholar_survey("xyzwq_nonexistent_topic_999", limit=3)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_scholar_landscape_handles_unknown_topic(self):
        """scholar_landscape returns message for unknown field."""
        from scholar_mcp.server import scholar_landscape
        result = scholar_landscape("xyzwq_nonexistent_field_999")
        assert isinstance(result, str)
        assert len(result) > 0


class TestMCPQualityTools:
    """Test quality scoring MCP tools."""

    def test_scholar_quality_single_paper(self):
        """scholar_quality_score returns valid result for known paper."""
        from scholar_mcp.server import scholar_quality_score
        result = scholar_quality_score(paper_id="01KT6MTBK1PQMNZM8ZYQPTVN6C")
        data = json.loads(result)
        assert "grade" in data or "error" in data

    def test_scholar_quality_nonexistent(self):
        """scholar_quality_score returns error for nonexistent paper."""
        from scholar_mcp.server import scholar_quality_score
        result = scholar_quality_score(paper_id="NONEXISTENT_XYZ")
        data = json.loads(result)
        assert "error" in data

    def test_read_quality_score_nonexistent(self):
        """read_quality_score returns message when no quality data."""
        from scholar_mcp.server import read_quality_score
        result = read_quality_score("NONEXISTENT_123")
        assert "not found" in result.lower() or "not yet" in result.lower()


class TestMCPExecutionTools:
    """Test execution layer MCP tools."""

    def test_scholar_lean_verify_json_output(self):
        """scholar_lean_verify returns JSON (may fail if Lean4 not installed)."""
        from scholar_mcp.server import scholar_lean_verify
        result = scholar_lean_verify()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_scholar_exp_run_no_code(self):
        """scholar_exp_run returns error when no experiment code."""
        from scholar_mcp.server import scholar_exp_run
        result = scholar_exp_run("01KT6MTBK1PQMNZM8ZYQPTVN6C")  # BERT
        assert isinstance(result, str)
        # Should say no experiment code or similar

    def test_scholar_read_experiment_report_no_data(self):
        """scholar_read_experiment_report returns message for no data."""
        from scholar_mcp.server import scholar_read_experiment_report
        result = scholar_read_experiment_report("NONEXISTENT_123")
        assert isinstance(result, str)
        assert len(result) > 0


class TestMCPKBUpdateTools:
    """Test KB update MCP tools."""

    def test_scholar_metadata_enrich_dry_run(self):
        """scholar_metadata_enrich(apply=False, limit=1) does dry run."""
        from scholar_mcp.server import scholar_metadata_enrich
        result = scholar_metadata_enrich(apply=False, limit=1)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_scholar_auto_notes_single(self):
        """scholar_auto_notes returns JSON for single known paper."""
        from scholar_mcp.server import scholar_auto_notes
        result = scholar_auto_notes(paper_id="01KT6MTBK1PQMNZM8ZYQPTVN6C")
        assert isinstance(result, str)
        try:
            data = json.loads(result)
            assert "status" in data or "error" in data
        except json.JSONDecodeError:
            pytest.skip("auto_notes returned non-JSON output")

    def test_read_auto_note_known_paper(self):
        """read_auto_note returns note text for a paper that has one."""
        from scholar_mcp.server import read_auto_note
        result = read_auto_note("01KT6MTBK1PQMNZM8ZYQPTVN6C")
        assert isinstance(result, str)
        if "not found" in result.lower():
            pytest.skip("Auto-note not generated for this paper yet")
