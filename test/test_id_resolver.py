"""
Unit Tests — id_resolver.py

Tests Hybrid ID resolution: ULID, arXiv ID, DOI, slug.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from scholar.id_resolver import IDResolver


class TestIDResolverInit:
    """Test resolver initialization and cache loading."""

    def test_empty_resolver(self):
        r = IDResolver()
        assert r._loaded is False
        assert r._cache == {}

    def test_ensure_loaded_scans_parsed_dir(self, tmp_path):
        """Resolver scans all JSON files in PARSED_DIR on first resolve."""
        parsed_dir = tmp_path / "parsed"
        parsed_dir.mkdir()
        data = {
            "paper_id": "01TEST123456789012345678",
            "arxiv_id": "2401.99999",
            "doi": "10.1234/test",
            "slug": "test-paper",
        }
        (parsed_dir / f"{data['paper_id']}.json").write_text(
            json.dumps(data), encoding="utf-8"
        )

        with patch("scholar.id_resolver.config") as mock_cfg:
            mock_cfg.PARSED_DIR = parsed_dir
            r = IDResolver()
            r._ensure_loaded()

        assert r._loaded is True
        assert "01TEST123456789012345678" in r._cache
        assert "2401.99999" in r._cache
        assert "10.1234/test" in r._cache
        assert "test-paper" in r._cache

    def test_refresh_clears_cache(self):
        r = IDResolver()
        r._cache["test"] = "value"
        r._loaded = True
        r.refresh()
        assert r._cache == {}
        assert r._loaded is False


class TestIDResolverResolve:
    """Test ID resolution for all supported formats."""

    @pytest.fixture
    def resolver_with_data(self, tmp_path):
        """Create a resolver pre-loaded with test data."""
        parsed_dir = tmp_path / "parsed"
        parsed_dir.mkdir()
        papers = [
            {"paper_id": "01KT6MTAT8FQS04JD19VEV2SM1", "arxiv_id": "1706.03762",
             "doi": "10.48550/arXiv.1706.03762", "slug": "attention-is-all-you-need"},
            {"paper_id": "01KT6MTB0ASK5XFMJZF1RDVT34", "arxiv_id": "1810.04805",
             "doi": "", "slug": "bert-pre-training"},
        ]
        for p in papers:
            (parsed_dir / f"{p['paper_id']}.json").write_text(
                json.dumps(p), encoding="utf-8"
            )

        r = IDResolver()
        with patch.object(r, '_ensure_loaded'):
            # Manually populate cache
            for p in papers:
                ulid = p["paper_id"]
                r._cache[ulid] = ulid
                if p.get("arxiv_id"):
                    r._cache[p["arxiv_id"]] = ulid
                if p.get("doi"):
                    r._cache[p["doi"]] = ulid
                if p.get("slug"):
                    r._cache[p["slug"]] = ulid
            r._loaded = True
            yield r

    def test_resolve_by_ulid(self, resolver_with_data):
        result = resolver_with_data.resolve("01KT6MTAT8FQS04JD19VEV2SM1")
        assert result == "01KT6MTAT8FQS04JD19VEV2SM1"

    def test_resolve_by_arxiv_id(self, resolver_with_data):
        result = resolver_with_data.resolve("1706.03762")
        assert result == "01KT6MTAT8FQS04JD19VEV2SM1"

    def test_resolve_arxiv_id_with_version(self, resolver_with_data):
        """arXiv IDs with version suffix should normalize (v1 stripped)."""
        result = resolver_with_data.resolve("1706.03762v1")
        assert result == "01KT6MTAT8FQS04JD19VEV2SM1"

    def test_resolve_by_doi(self, resolver_with_data):
        result = resolver_with_data.resolve("10.48550/arXiv.1706.03762")
        assert result == "01KT6MTAT8FQS04JD19VEV2SM1"

    def test_resolve_by_doi_url(self, resolver_with_data):
        """Full DOI URL should be normalized."""
        result = resolver_with_data.resolve("https://doi.org/10.48550/arXiv.1706.03762")
        assert result == "01KT6MTAT8FQS04JD19VEV2SM1"

    def test_resolve_by_slug(self, resolver_with_data):
        result = resolver_with_data.resolve("attention-is-all-you-need")
        assert result == "01KT6MTAT8FQS04JD19VEV2SM1"

    def test_resolve_by_slug_fuzzy(self, resolver_with_data):
        """Slug fuzzy match: partial keyword."""
        result = resolver_with_data.resolve("attention")
        assert result == "01KT6MTAT8FQS04JD19VEV2SM1"

    def test_resolve_unknown_returns_none(self, resolver_with_data):
        result = resolver_with_data.resolve("nonexistent-paper-xyz")
        assert result is None

    def test_resolve_empty_returns_none(self, resolver_with_data):
        assert resolver_with_data.resolve("") is None
        assert resolver_with_data.resolve(None) is None

    def test_resolve_strips_whitespace(self, resolver_with_data):
        result = resolver_with_data.resolve("  1706.03762  ")
        assert result == "01KT6MTAT8FQS04JD19VEV2SM1"

    def test_list_all_ulids(self, resolver_with_data):
        ulids = resolver_with_data.list_all_ulids()
        assert "01KT6MTAT8FQS04JD19VEV2SM1" in ulids
        assert "01KT6MTB0ASK5XFMJZF1RDVT34" in ulids
        # arXiv IDs and slugs should NOT appear as ULIDs
        assert "1706.03762" not in ulids
        assert "attention-is-all-you-need" not in ulids
