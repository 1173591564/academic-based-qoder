"""
End-to-End Tests — Full Pipeline Workflows

Tests complete workflows from start to finish with mocked external services.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scholar import research_loop as rl
from scholar import kb_update
from scholar import db as dbmod


class TestIngestPipeline:
    """E2E: Paper enters the system → parsed JSON is created → searchable."""

    def test_save_then_search_paper(self, tmp_path, sample_paper_data):
        """Save a paper, then verify it's findable via list_parsed."""
        parsed_dir = tmp_path / "parsed"
        parsed_dir.mkdir()

        # 1. Save parsed paper
        path = dbmod.save_parsed(sample_paper_data, parsed_dir=parsed_dir)
        assert path.exists()

        # 2. Load it back
        loaded = dbmod.load_parsed(sample_paper_data["paper_id"], parsed_dir=parsed_dir)
        assert loaded is not None
        assert loaded["title"] == "Attention Is All You Need"
        assert loaded["year"] == 2017
        assert len(loaded["sections"]) == 2
        assert len(loaded["formulas"]) == 1

        # 3. List all parsed
        ids = dbmod.list_parsed(parsed_dir=parsed_dir)
        assert sample_paper_data["paper_id"] in ids

    def test_multi_paper_roundtrip(self, tmp_path, sample_paper_data, sample_paper_data_2):
        """Save multiple papers, verify all are accessible."""
        parsed_dir = tmp_path / "parsed"
        parsed_dir.mkdir()

        dbmod.save_parsed(sample_paper_data, parsed_dir=parsed_dir)
        dbmod.save_parsed(sample_paper_data_2, parsed_dir=parsed_dir)

        ids = dbmod.list_parsed(parsed_dir=parsed_dir)
        assert len(ids) == 2

        # Load each
        for pid in ids:
            data = dbmod.load_parsed(pid, parsed_dir=parsed_dir)
            assert data is not None
            assert "title" in data
            assert "sections" in data


class TestAdaptiveResearchLoop:
    """E2E: Full adaptive research loop cycle."""

    def test_full_cycle_logs_to_interests_to_sync(self, tmp_path):
        """
        Simulate: write logs → analyze → add interests → mark analyzed → sync.
        All with mocked external services (arXiv, network).
        """
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        interests_file = tmp_path / "research-interests.json"
        digests_dir = tmp_path / "digests"
        digests_dir.mkdir()
        parsed_dir = tmp_path / "parsed"
        parsed_dir.mkdir()
        papers_dir = tmp_path / "papers"
        papers_dir.mkdir()

        # Step 1: Write week log file
        (logs_dir / "week-2026-W25.jsonl").write_text(
            '{"ts":"2026-06-15T10:00:00","week":"2026-W25","session":"s1","text":"调研 MoE 推理优化"}\n'
            '{"ts":"2026-06-15T11:00:00","week":"2026-W25","session":"s1","text":"sparse attention 有没有新论文"}\n'
            '{"ts":"2026-06-15T12:00:00","week":"2026-W25","session":"s2","text":"推到远程仓库"}\n',
            encoding="utf-8"
        )

        with patch.object(rl.config, "LOGS_DIR", logs_dir), \
             patch.object(rl.config, "INTERESTS_FILE", interests_file):

            # Step 2: Read unanalyzed logs
            path, entries = rl.get_unanalyzed_logs()
            assert "W25" in path.name
            assert len(entries) == 3

            # Step 3: "Agent" extracts interests from logs (simulated)
            rl.add_interest("MoE 推理优化, sparse attention", "LLM Efficiency")
            data = rl.load_interests()
            assert len(data["interests"]) == 1
            assert data["interests"][0]["category"] == "LLM Efficiency"

            # Step 4: Mark week as analyzed
            rl.mark_week_analyzed("2026-W25", interests_found=1, entries=3)

            # Verify: week no longer shows up as unanalyzed
            path2, entries2 = rl.get_unanalyzed_logs()
            assert path2 == Path("")

        # Step 5: Sync (mocked arXiv + ingest)
        mock_dl = [{
            "ulid": "01NEWPAPER1234567890123456",
            "arxiv_id": "2403.99999",
            "title": "Fast MoE Inference",
            "status": "downloaded",
        }]

        with patch.object(rl.config, "INTERESTS_FILE", interests_file), \
             patch.object(rl.config, "DIGESTS_DIR", digests_dir), \
             patch.object(rl.kb_update, "arxiv_download", return_value=mock_dl), \
             patch.object(rl.kb_update, "batch_ingest", return_value={"parsed": 1, "errors": []}):
            result = rl.sync_direction("LLM Efficiency", max_results=5)

        assert result["downloaded"] == 1
        assert result["ingested"] == 1
        assert len(result["errors"]) == 0

        # Verify sync report was created
        reports = list(digests_dir.glob("sync-*.md"))
        assert len(reports) >= 1

        # Verify interests stats updated
        with patch.object(rl.config, "INTERESTS_FILE", interests_file):
            final = rl.load_interests()
        assert final["interests"][0]["search_count"] == 1
        assert final["interests"][0]["last_searched"] is not None
        assert len(final["history"]) == 1


class TestInterestsPersistence:
    """E2E: Interests survive save/load cycles."""

    def test_add_remove_persist(self, tmp_path):
        interests_file = tmp_path / "research-interests.json"

        with patch.object(rl.config, "INTERESTS_FILE", interests_file):
            # Add 3 interests
            rl.add_interest("sparse attention", "Direction A")
            rl.add_interest("MoE routing", "Direction B")
            rl.add_interest("knowledge distillation", "Direction C")

            data = rl.load_interests()
            assert len(data["interests"]) == 3

            # Remove one
            rl.remove_interest("Direction B")
            data = rl.load_interests()
            assert len(data["interests"]) == 2
            categories = {i["category"] for i in data["interests"]}
            assert "Direction B" not in categories
            assert "Direction A" in categories
            assert "Direction C" in categories

            # Verify file on disk matches
            disk_data = json.loads(interests_file.read_text(encoding="utf-8"))
            assert len(disk_data["interests"]) == 2
