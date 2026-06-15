"""
Unit Tests — db.py (file-only fallback layer)

Tests: save_parsed, load_parsed, list_parsed without requiring PostgreSQL.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scholar import db as dbmod


class TestFileOnlyOperations:
    """Test file-based save/load/list without DB."""

    def test_save_parsed_creates_json(self, tmp_path, sample_paper_data):
        parsed_dir = tmp_path / "parsed"
        parsed_dir.mkdir()
        path = dbmod.save_parsed(sample_paper_data, parsed_dir=parsed_dir)
        assert path.exists()
        assert path.name == f"{sample_paper_data['paper_id']}.json"

    def test_save_and_load_roundtrip(self, tmp_path, sample_paper_data):
        parsed_dir = tmp_path / "parsed"
        parsed_dir.mkdir()
        dbmod.save_parsed(sample_paper_data, parsed_dir=parsed_dir)
        loaded = dbmod.load_parsed(sample_paper_data["paper_id"], parsed_dir=parsed_dir)
        assert loaded is not None
        assert loaded["paper_id"] == sample_paper_data["paper_id"]
        assert loaded["title"] == sample_paper_data["title"]
        assert loaded["year"] == sample_paper_data["year"]
        assert len(loaded["sections"]) == 2
        assert len(loaded["formulas"]) == 1
        assert len(loaded["citations"]) == 2

    def test_load_nonexistent_returns_none(self, tmp_path):
        parsed_dir = tmp_path / "parsed"
        parsed_dir.mkdir()
        result = dbmod.load_parsed("NONEXISTENT_ULID", parsed_dir=parsed_dir)
        assert result is None

    def test_list_parsed_returns_all_ids(self, tmp_path, sample_paper_data, sample_paper_data_2):
        parsed_dir = tmp_path / "parsed"
        parsed_dir.mkdir()
        dbmod.save_parsed(sample_paper_data, parsed_dir=parsed_dir)
        dbmod.save_parsed(sample_paper_data_2, parsed_dir=parsed_dir)
        ids = dbmod.list_parsed(parsed_dir=parsed_dir)
        assert sample_paper_data["paper_id"] in ids
        assert sample_paper_data_2["paper_id"] in ids
        assert len(ids) == 2

    def test_list_parsed_empty_dir(self, tmp_path):
        parsed_dir = tmp_path / "parsed"
        parsed_dir.mkdir()
        ids = dbmod.list_parsed(parsed_dir=parsed_dir)
        assert ids == []

    def test_save_parsed_overwrites_existing(self, tmp_path, sample_paper_data):
        parsed_dir = tmp_path / "parsed"
        parsed_dir.mkdir()
        dbmod.save_parsed(sample_paper_data, parsed_dir=parsed_dir)
        # Modify and save again
        sample_paper_data["title"] = "Updated Title"
        dbmod.save_parsed(sample_paper_data, parsed_dir=parsed_dir)
        loaded = dbmod.load_parsed(sample_paper_data["paper_id"], parsed_dir=parsed_dir)
        assert loaded["title"] == "Updated Title"

    def test_save_parsed_preserves_unicode(self, tmp_path):
        parsed_dir = tmp_path / "parsed"
        parsed_dir.mkdir()
        data = {"paper_id": "TEST_UNICODE_123", "title": "中文标题测试", "abstract": "La résumé"}
        dbmod.save_parsed(data, parsed_dir=parsed_dir)
        loaded = dbmod.load_parsed("TEST_UNICODE_123", parsed_dir=parsed_dir)
        assert loaded["title"] == "中文标题测试"
        assert loaded["abstract"] == "La résumé"

    def test_save_parsed_fails_if_parent_missing(self, tmp_path, sample_paper_data):
        """save_parsed uses exist_ok=True but not parents=True."""
        parsed_dir = tmp_path / "nonexistent" / "parsed"
        with pytest.raises(FileNotFoundError):
            dbmod.save_parsed(sample_paper_data, parsed_dir=parsed_dir)


class TestDatabaseAvailability:
    """Test Database class availability check (mocked psycopg2)."""

    def test_db_unavailable_without_psycopg2(self):
        db = dbmod.Database()
        db.psycopg2 = None
        assert db.available is False

    def test_db_available_with_mock_connection(self):
        db = dbmod.Database()
        mock_psycopg2 = MagicMock()
        mock_conn = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        db.psycopg2 = mock_psycopg2
        assert db.available is True
        mock_conn.close.assert_called_once()

    def test_db_unavailable_on_connection_error(self):
        db = dbmod.Database()
        mock_psycopg2 = MagicMock()
        mock_psycopg2.connect.side_effect = Exception("connection refused")
        db.psycopg2 = mock_psycopg2
        assert db.available is False
