"""Unit Tests — _state.py"""
import pytest
from unittest.mock import MagicMock


class TestSharedStateInit:

    def test_get_state_none_before_init(self, monkeypatch):
        monkeypatch.setattr("scholar._state._state", None)
        from scholar._state import get_state
        assert get_state() is None

    def test_init_shared_state_creates_singleton(self, monkeypatch):
        import scholar._state
        scholar._state._state = None
        monkeypatch.setattr(scholar._state.SharedState, "init_pool", lambda s: None)
        monkeypatch.setattr(scholar._state.SharedState, "get_id_resolver", lambda s: None)
        scholar._state.init_shared_state()
        from scholar._state import get_state
        assert get_state() is not None

    def test_close_clears_pool(self):
        import scholar._state
        mock_pool = MagicMock()
        state = scholar._state.SharedState()
        state._pool = mock_pool
        state.close()
        mock_pool.closeall.assert_called_once()


class TestGetDB:

    def test_without_pool(self):
        from scholar._state import SharedState
        from scholar.db import Database
        state = SharedState()
        db = state.get_db()
        assert isinstance(db, Database)
        assert db._pool is None

    def test_with_pool_injects_it(self):
        from scholar._state import SharedState
        mock_pool = MagicMock()
        state = SharedState()
        state._pool = mock_pool
        db = state.get_db()
        assert db._pool is mock_pool


class TestLRUCache:

    def _make_fake_data(self, pid):
        return {"paper_id": pid, "title": f"Paper {pid}"}

    def _patch_dbmod(self, monkeypatch, load_fn):
        mock = MagicMock()
        mock.load_parsed = load_fn
        monkeypatch.setattr("scholar._state.dbmod", mock)

    def test_caches_result(self, monkeypatch):
        from scholar._state import SharedState
        call_count = [0]
        def fake(pid):
            call_count[0] += 1
            return self._make_fake_data(pid)
        self._patch_dbmod(monkeypatch, fake)

        state = SharedState()
        data1 = state.get_parsed("A")
        assert data1 is not None
        assert call_count[0] == 1
        data2 = state.get_parsed("A")
        assert data2 is not None
        assert call_count[0] == 1  # cache hit

    def test_evicts_lru_when_full(self, monkeypatch):
        from scholar._state import SharedState
        calls = [0]
        def fake(pid):
            calls[0] += 1
            return self._make_fake_data(pid)
        self._patch_dbmod(monkeypatch, fake)

        state = SharedState()
        state._parsed_cache_max = 3
        state.get_parsed("A"); state.get_parsed("B"); state.get_parsed("C")
        assert calls[0] == 3
        state.get_parsed("A"); state.get_parsed("B")  # touch, C becomes LRU
        assert calls[0] == 3
        state.get_parsed("D")  # evicts C
        assert calls[0] == 4
        state.get_parsed("A")
        assert calls[0] == 4  # hit
        state.get_parsed("C")
        assert calls[0] == 5  # miss, reloaded

    def test_invalidate_one(self, monkeypatch):
        from scholar._state import SharedState
        self._patch_dbmod(monkeypatch, lambda pid: {"paper_id": pid})
        state = SharedState()
        state.get_parsed("A"); state.get_parsed("B")
        state.invalidate_parsed("A")
        assert "B" in state._parsed_cache
        assert "A" not in state._parsed_cache

    def test_invalidate_all(self, monkeypatch):
        from scholar._state import SharedState
        self._patch_dbmod(monkeypatch, lambda pid: {"paper_id": pid})
        state = SharedState()
        state.get_parsed("A"); state.get_parsed("B")
        state.invalidate_parsed()
        assert len(state._parsed_cache) == 0


class TestIDResolver:

    def test_uses_cache(self):
        from scholar._state import SharedState
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = "01RESOLVED1234567890123456"
        state = SharedState()
        state._id_resolver = mock_resolver
        result = state.resolve_id("2401.04088")
        assert result == "01RESOLVED1234567890123456"
        mock_resolver.resolve.assert_called_once_with("2401.04088")
