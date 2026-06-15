"""
Scholar Studio — Test Fixtures

Shared fixtures for unit, integration, and e2e tests.
Uses tmp_path (pytest built-in) for isolated file operations.
"""
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def project_root():
    """Return the actual project root directory."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def sample_paper_data():
    """A minimal valid parsed paper JSON."""
    return {
        "paper_id": "01KT6MTAT8FQS04JD19VEV2SM1",
        "title": "Attention Is All You Need",
        "authors": ["Ashish Vaswani", "Noam Shazeer"],
        "year": 2017,
        "venue": "NeurIPS",
        "abstract": "The dominant sequence transduction models...",
        "arxiv_id": "1706.03762",
        "doi": "10.48550/arXiv.1706.03762",
        "slug": "attention-is-all-you-need",
        "has_tex": True,
        "parsed_ok": True,
        "sections": [
            {"heading": "Introduction", "level": 1, "content": "Self-attention...", "position": 0},
            {"heading": "Method", "level": 1, "content": "Transformer...", "position": 1},
        ],
        "formulas": [
            {"latex": "\\text{Attention}(Q,K,V) = \\text{softmax}(\\frac{QK^T}{\\sqrt{d_k}})V",
             "label": "eq:attention", "env_type": "equation", "context": "scaled dot-product"},
        ],
        "citations": ["01KT6MTB0ASK5XFMJZF1RDVT34", "01KT6MTB1RRQ9CWQQWN8K33YT6"],
    }


@pytest.fixture
def sample_paper_data_2():
    """A second sample paper for dedup/multi-paper tests."""
    return {
        "paper_id": "01KT6MTB0ASK5XFMJZF1RDVT34",
        "title": "BERT: Pre-training of Deep Bidirectional Transformers",
        "authors": ["Jacob Devlin", "Ming-Wei Chang"],
        "year": 2019,
        "venue": "NAACL",
        "abstract": "We introduce BERT...",
        "arxiv_id": "1810.04805",
        "doi": "",
        "slug": "bert-pre-training",
        "has_tex": True,
        "parsed_ok": True,
        "sections": [{"heading": "Introduction", "level": 1, "content": "Language models...", "position": 0}],
        "formulas": [],
        "citations": ["01KT6MTAT8FQS04JD19VEV2SM1"],
    }


@pytest.fixture
def tmp_parsed_dir(tmp_path):
    """Create a temporary parsed/ directory with sample papers."""
    parsed = tmp_path / "parsed"
    parsed.mkdir()
    return parsed


@pytest.fixture
def tmp_logs_dir(tmp_path):
    """Create a temporary logs/ directory."""
    logs = tmp_path / "logs"
    logs.mkdir()
    return logs


@pytest.fixture
def populate_parsed(tmp_parsed_dir, sample_paper_data, sample_paper_data_2):
    """Write sample papers into tmp_parsed_dir."""
    for data in [sample_paper_data, sample_paper_data_2]:
        path = tmp_parsed_dir / f"{data['paper_id']}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return tmp_parsed_dir


@pytest.fixture
def sample_arxiv_xml():
    """A minimal valid arXiv API XML response."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Sparse Attention for Efficient Transformers</title>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <published>2024-03-15T00:00:00Z</published>
    <id>http://arxiv.org/abs/2403.12345</id>
    <summary>We propose a sparse attention mechanism...</summary>
    <link title="pdf" href="https://arxiv.org/pdf/2403.12345"/>
  </entry>
  <entry>
    <title>MoE Routing with Expert Choice</title>
    <author><name>Charlie Wang</name></author>
    <published>2024-06-01T00:00:00Z</published>
    <id>http://arxiv.org/abs/2406.67890</id>
    <summary>Mixture of experts routing...</summary>
    <link title="pdf" href="https://arxiv.org/pdf/2406.67890"/>
  </entry>
</feed>"""


@pytest.fixture
def sample_week_jsonl():
    """Sample week log entries as a list of dicts."""
    return [
        {"ts": "2026-06-10T10:00:00", "week": "2026-W24", "session": "abc", "text": "调研 Transformer 效率优化"},
        {"ts": "2026-06-10T11:00:00", "week": "2026-W24", "session": "abc", "text": "精读 01KT6MTAT8FQS04JD19VEV2SM1"},
        {"ts": "2026-06-10T12:00:00", "week": "2026-W24", "session": "def", "text": "推到远程仓库"},
        {"ts": "2026-06-11T09:00:00", "week": "2026-W24", "session": "ghi", "text": "MoE 推理优化有没有新论文"},
    ]


@pytest.fixture
def mock_config(tmp_path, tmp_parsed_dir, tmp_logs_dir):
    """Patch scholar.config to use tmp directories."""
    with patch("scholar.config.PARSED_DIR", tmp_parsed_dir), \
         patch("scholar.config.LOGS_DIR", tmp_logs_dir), \
         patch("scholar.config.INTERESTS_FILE", tmp_path / "research-interests.json"), \
         patch("scholar.config.DIGESTS_DIR", tmp_path / "digests"), \
         patch("scholar.config.PAPERS_DIR", tmp_path / "papers"):
        (tmp_path / "digests").mkdir(exist_ok=True)
        (tmp_path / "papers").mkdir(exist_ok=True)
        yield
