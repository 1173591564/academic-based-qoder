"""
Unit Tests — research_loop.py

Tests: interests CRUD, log analysis, week marking, sync_direction logic.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scholar import research_loop as rl


class TestInterestsCRUD:
    """Test add/remove/list interest operations."""

    def test_load_empty_interests(self, tmp_path):
        """No file → returns empty template."""
        interests_file = tmp_path / "research-interests.json"
        with patch.object(rl.config, "INTERESTS_FILE", interests_file):
            data = rl.load_interests()
        assert data["version"] == 1
        assert data["interests"] == []
        assert data["history"] == []

    def test_save_and_load_interests(self, tmp_path):
        interests_file = tmp_path / "research-interests.json"
        with patch.object(rl.config, "INTERESTS_FILE", interests_file):
            data = rl.load_interests()
            data["interests"].append({
                "category": "LLM Efficiency",
                "keywords": "sparse attention, pruning",
                "max_results": 10,
            })
            rl.save_interests(data)
            loaded = rl.load_interests()
        assert len(loaded["interests"]) == 1
        assert loaded["interests"][0]["category"] == "LLM Efficiency"
        assert "updated_at" in loaded

    def test_save_is_atomic(self, tmp_path):
        """Verify .tmp file doesn't linger after save."""
        interests_file = tmp_path / "research-interests.json"
        with patch.object(rl.config, "INTERESTS_FILE", interests_file):
            rl.save_interests({"version": 1, "interests": [], "history": [], "updated_at": ""})
        assert interests_file.exists()
        assert not interests_file.with_suffix(".tmp").exists()

    def test_add_interest_new_category(self, tmp_path):
        interests_file = tmp_path / "research-interests.json"
        with patch.object(rl.config, "INTERESTS_FILE", interests_file):
            data = rl.add_interest("sparse attention, efficient transformer", "LLM Efficiency")
        assert len(data["interests"]) == 1
        assert data["interests"][0]["category"] == "LLM Efficiency"
        assert data["interests"][0]["keywords"] == "sparse attention, efficient transformer"

    def test_add_interest_merge_keywords(self, tmp_path):
        """Adding to existing category should merge keywords, no duplicates."""
        interests_file = tmp_path / "research-interests.json"
        with patch.object(rl.config, "INTERESTS_FILE", interests_file):
            rl.add_interest("sparse attention", "LLM Efficiency")
            data = rl.add_interest("sparse attention, pruning, quantization", "LLM Efficiency")
        kw = data["interests"][0]["keywords"]
        assert "sparse attention" in kw
        assert "pruning" in kw
        assert "quantization" in kw
        # No duplicates
        parts = [k.strip().lower() for k in kw.split(",")]
        assert len(parts) == len(set(parts))

    def test_add_interest_case_insensitive_category(self, tmp_path):
        interests_file = tmp_path / "research-interests.json"
        with patch.object(rl.config, "INTERESTS_FILE", interests_file):
            rl.add_interest("keyword1", "LLM Efficiency")
            data = rl.add_interest("keyword2", "llm efficiency")
        assert len(data["interests"]) == 1  # merged, not duplicate

    def test_remove_interest_exists(self, tmp_path):
        interests_file = tmp_path / "research-interests.json"
        with patch.object(rl.config, "INTERESTS_FILE", interests_file):
            rl.add_interest("test", "TestCategory")
            data, removed = rl.remove_interest("TestCategory")
        assert removed is True
        assert len(data["interests"]) == 0

    def test_remove_interest_not_exists(self, tmp_path):
        interests_file = tmp_path / "research-interests.json"
        with patch.object(rl.config, "INTERESTS_FILE", interests_file):
            rl.add_interest("test", "TestCategory")
            data, removed = rl.remove_interest("NonExistent")
        assert removed is False
        assert len(data["interests"]) == 1

    def test_remove_interest_case_insensitive(self, tmp_path):
        interests_file = tmp_path / "research-interests.json"
        with patch.object(rl.config, "INTERESTS_FILE", interests_file):
            rl.add_interest("test", "LLM Efficiency")
            data, removed = rl.remove_interest("llm efficiency")
        assert removed is True


class TestLogAnalysis:
    """Test log file parsing and analysis tracking."""

    def test_get_unanalyzed_logs_no_files(self, tmp_path):
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        with patch.object(rl.config, "LOGS_DIR", logs_dir):
            result = rl.get_unanalyzed_logs()
        assert result == {}

    def test_get_unanalyzed_logs_returns_earliest(self, tmp_path):
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        # Create two week files
        (logs_dir / "week-2026-W24.jsonl").write_text(
            '{"ts":"2026-06-10T10:00:00","week":"2026-W24","text":"test1"}\n'
            '{"ts":"2026-06-10T11:00:00","week":"2026-W24","text":"test2"}\n',
            encoding="utf-8"
        )
        (logs_dir / "week-2026-W25.jsonl").write_text(
            '{"ts":"2026-06-15T10:00:00","week":"2026-W25","text":"test3"}\n',
            encoding="utf-8"
        )
        with patch.object(rl.config, "LOGS_DIR", logs_dir):
            result = rl.get_unanalyzed_logs()
        assert len(result) == 1
        path, entries = list(result.values())[0]
        assert "W24" in path.name
        assert len(entries) == 2
        assert entries[0]["text"] == "test1"

    def test_get_unanalyzed_skips_analyzed(self, tmp_path):
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "week-2026-W24.jsonl").write_text(
            '{"text":"old"}\n', encoding="utf-8"
        )
        (logs_dir / "week-2026-W25.jsonl").write_text(
            '{"text":"new"}\n', encoding="utf-8"
        )
        # Mark W24 as analyzed
        (logs_dir / "analyzed.json").write_text(
            json.dumps({"2026-W24": {"analyzed_at": "2026-06-14T10:00:00"}}),
            encoding="utf-8"
        )
        with patch.object(rl.config, "LOGS_DIR", logs_dir):
            result = rl.get_unanalyzed_logs()
        assert len(result) == 1
        path, entries = list(result.values())[0]
        assert "W25" in path.name

    def test_get_unanalyzed_skips_malformed_lines(self, tmp_path):
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "week-2026-W24.jsonl").write_text(
            '{"text":"valid"}\n'
            'this is not json\n'
            '{"text":"also valid"}\n',
            encoding="utf-8"
        )
        with patch.object(rl.config, "LOGS_DIR", logs_dir):
            result = rl.get_unanalyzed_logs()
        assert len(result) == 1
        path, entries = list(result.values())[0]
        assert len(entries) == 2

    def test_mark_week_analyzed(self, tmp_path):
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        with patch.object(rl.config, "LOGS_DIR", logs_dir):
            rl.mark_week_analyzed("2026-W24", interests_found=3, entries=10)
        analyzed = json.loads((logs_dir / "analyzed.json").read_text(encoding="utf-8"))
        assert "2026-W24" in analyzed
        assert analyzed["2026-W24"]["interests_found"] == 3
        assert analyzed["2026-W24"]["entries"] == 10

    def test_mark_week_analyzed_idempotent(self, tmp_path):
        """Marking same week twice should update, not duplicate."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        with patch.object(rl.config, "LOGS_DIR", logs_dir):
            rl.mark_week_analyzed("2026-W24", 2, 5)
            rl.mark_week_analyzed("2026-W24", 3, 8)
        analyzed = json.loads((logs_dir / "analyzed.json").read_text(encoding="utf-8"))
        assert analyzed["2026-W24"]["interests_found"] == 3


class TestSyncDirection:
    """Test sync_direction with mocked kb_update calls."""

    def test_sync_nonexistent_category(self, tmp_path):
        interests_file = tmp_path / "research-interests.json"
        interests_file.write_text(json.dumps({
            "version": 1, "interests": [], "history": [], "updated_at": ""
        }), encoding="utf-8")
        with patch.object(rl.config, "INTERESTS_FILE", interests_file):
            result = rl.sync_direction("NonExistent")
        assert result["downloaded"] == 0
        assert len(result["errors"]) > 0
        assert "未找到" in result["errors"][0]

    def test_sync_direction_calls_arxiv_and_ingest(self, tmp_path):
        """sync_direction should call arxiv_download then batch_ingest."""
        interests_file = tmp_path / "research-interests.json"
        interests_file.write_text(json.dumps({
            "version": 1,
            "interests": [{
                "category": "Sparse Attention",
                "keywords": "sparse attention",
                "max_results": 5,
                "search_count": 0,
                "last_searched": None,
            }],
            "history": [],
            "updated_at": ""
        }), encoding="utf-8")

        mock_dl_result = [{
            "ulid": "01NEWPAPER1234567890123456",
            "arxiv_id": "2403.12345",
            "title": "Sparse Attention Paper",
            "status": "downloaded",
        }]

        with patch.object(rl.config, "INTERESTS_FILE", interests_file), \
             patch.object(rl.config, "DIGESTS_DIR", tmp_path / "digests"), \
             patch.object(rl.kb_update, "arxiv_download", return_value=mock_dl_result), \
             patch.object(rl.kb_update, "batch_ingest", return_value={"parsed": 1, "errors": []}):
            (tmp_path / "digests").mkdir(exist_ok=True)
            result = rl.sync_direction("Sparse Attention", max_results=5)

        assert result["downloaded"] == 1
        assert result["ingested"] == 1
        assert len(result["errors"]) == 0

    def test_sync_all_empty_interests(self, tmp_path):
        interests_file = tmp_path / "research-interests.json"
        interests_file.write_text(json.dumps({
            "version": 1, "interests": [], "history": [], "updated_at": ""
        }), encoding="utf-8")
        with patch.object(rl.config, "INTERESTS_FILE", interests_file):
            result = rl.sync_all_directions()
        assert result["total_categories"] == 0
        assert "interests" in result.get("message", "").lower() or result["total_categories"] == 0
