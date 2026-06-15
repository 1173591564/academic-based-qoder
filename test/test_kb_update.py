"""
Unit Tests — kb_update.py

Tests: arXiv XML parsing, ULID generation, batch_ingest logic, arxiv_download dedup.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scholar import kb_update


class TestArxivXMLParsing:
    """Test _parse_arxiv_entries with sample XML."""

    def test_parse_valid_xml(self, sample_arxiv_xml):
        entries = kb_update._parse_arxiv_entries(sample_arxiv_xml)
        assert len(entries) == 2
        assert entries[0]["title"] == "Sparse Attention for Efficient Transformers"
        assert entries[0]["arxiv_id"] == "2403.12345"
        assert entries[0]["year"] == "2024"
        assert "Alice Smith" in entries[0]["authors"]
        assert "Bob Jones" in entries[0]["authors"]

    def test_parse_extracts_pdf_url(self, sample_arxiv_xml):
        entries = kb_update._parse_arxiv_entries(sample_arxiv_xml)
        assert entries[0]["pdf_url"] == "https://arxiv.org/pdf/2403.12345"

    def test_parse_single_author(self, sample_arxiv_xml):
        entries = kb_update._parse_arxiv_entries(sample_arxiv_xml)
        assert entries[1]["authors"] == ["Charlie Wang"]

    def test_parse_empty_xml(self):
        xml = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        entries = kb_update._parse_arxiv_entries(xml)
        assert entries == []

    def test_parse_arxiv_id_normalized(self):
        """arXiv IDs should be normalized (strip version, extract from URL)."""
        xml = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Test</title>
            <id>http://arxiv.org/abs/2403.12345v2</id>
            <published>2024-01-01T00:00:00Z</published>
            <summary>test</summary>
          </entry>
        </feed>"""
        entries = kb_update._parse_arxiv_entries(xml)
        assert entries[0]["arxiv_id"] == "2403.12345"


class TestULIDGeneration:
    """Test ULID generation."""

    def test_generate_ulid_length(self):
        ulid = kb_update._generate_ulid()
        assert len(ulid) == 26

    def test_generate_ulid_unique(self):
        ulids = {kb_update._generate_ulid() for _ in range(100)}
        assert len(ulids) == 100  # all unique

    def test_generate_ulid_alphanumeric(self):
        ulid = kb_update._generate_ulid()
        assert ulid.isalnum()


class TestBatchIngest:
    """Test batch_ingest logic with mocked dependencies."""

    def test_batch_ingest_empty_list_explicit(self, tmp_path):
        """batch_ingest(ulids=[]) should process 0 papers, not fall through."""
        # Empty list = explicit "nothing to process"
        result = kb_update.batch_ingest(ulids=[])
        assert result["total"] == 0
        assert result["parsed"] == 0

    def test_batch_ingest_none_scans_unparsed(self, tmp_path):
        """batch_ingest(ulids=None) should scan for unparsed papers."""
        papers_dir = tmp_path / "papers"
        papers_dir.mkdir()
        parsed_dir = tmp_path / "parsed"
        parsed_dir.mkdir()

        # Create one paper dir with source but no parsed JSON
        ulid = "01TEST123456789012345678"
        (papers_dir / ulid).mkdir()
        (papers_dir / ulid / "source.tar.gz").write_bytes(b"fake")

        with patch.object(kb_update.config, "PAPERS_DIR", papers_dir), \
             patch.object(kb_update.config, "PARSED_DIR", parsed_dir):
            result = kb_update.batch_ingest(ulids=None)
        # Should find the one unparsed paper (even if parse fails, total should be 1)
        assert result["total"] == 1

    def test_batch_ingest_with_specific_ulids(self, tmp_path):
        """batch_ingest with specific ULIDs should process exactly those."""
        papers_dir = tmp_path / "papers"
        papers_dir.mkdir()
        parsed_dir = tmp_path / "parsed"
        parsed_dir.mkdir()

        with patch.object(kb_update.config, "PAPERS_DIR", papers_dir), \
             patch.object(kb_update.config, "PARSED_DIR", parsed_dir):
            result = kb_update.batch_ingest(ulids=["ULID1", "ULID2"])
        # Should have attempted exactly 2 papers (they'll fail to parse, but total=2)
        assert result["total"] == 2
        assert len(result["errors"]) == 2


class TestArxivDownloadDedup:
    """Test arxiv_download deduplication logic."""

    def test_dedup_skips_existing_arxiv_ids(self, tmp_path, sample_arxiv_xml):
        """Papers with existing arxiv_id should be marked already_exists."""
        parsed_dir = tmp_path / "parsed"
        parsed_dir.mkdir()
        papers_dir = tmp_path / "papers"
        papers_dir.mkdir()

        # Create an existing parsed paper with arxiv_id 2403.12345
        existing = {"paper_id": "EXISTING123", "arxiv_id": "2403.12345"}
        (parsed_dir / "EXISTING123.json").write_text(
            json.dumps(existing), encoding="utf-8"
        )

        with patch.object(kb_update.config, "PARSED_DIR", parsed_dir), \
             patch.object(kb_update.config, "PAPERS_DIR", papers_dir), \
             patch.object(kb_update.config, "arxiv_request", return_value=sample_arxiv_xml):
            results = kb_update.arxiv_download("test", max_results=5)

        # First paper should be already_exists, second should attempt download
        statuses = [r["status"] for r in results]
        assert "already_exists" in statuses
