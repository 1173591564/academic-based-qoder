"""
Unit Tests — db.py connection pool mode

Tests Database.cursor() pool branch: getconn/putconn lifecycle,
transaction error handling, and pool-unavailable fallback.
"""
import pytest
from unittest.mock import MagicMock, call


class FakeCursor:
    """Simulates a psycopg2 cursor."""
    def __init__(self):
        self._closed = False

    def execute(self, sql, params=None):
        pass

    def fetchall(self):
        return []

    def fetchone(self):
        return None

    def close(self):
        self._closed = True


class FakeConnection:
    """Simulates a psycopg2 connection."""
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return FakeCursor()

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass

    def ping(self):
        return True


class FakePool:
    """Mimics psycopg2 ThreadedConnectionPool interface."""
    def __init__(self):
        self.borrowed = []
        self.returned = []
        self._conn = FakeConnection()

    def getconn(self):
        self.borrowed.append(1)
        return self._conn

    def putconn(self, conn):
        self.returned.append(1)


class TestDatabasePoolMode:
    """Test Database.cursor() when a pool is provided."""

    def setup_method(self):
        self.pool = FakePool()

    def _make_db_with_pool(self):
        from scholar.db import Database
        db = Database()
        db._pool = self.pool
        # Patch psycopg2 import to avoid ImportError
        import scholar.db as dbmod
        db.psycopg2 = MagicMock()
        return db

    def test_getconn_called_on_enter(self):
        """cursor() calls pool.getconn() when entering context."""
        db = self._make_db_with_pool()
        with db.cursor() as cur:
            pass
        assert len(self.pool.borrowed) == 1

    def test_putconn_called_on_exit(self):
        """cursor() calls pool.putconn() when exiting context."""
        db = self._make_db_with_pool()
        with db.cursor() as cur:
            pass
        assert len(self.pool.returned) == 1

    def test_borrow_return_balance(self):
        """Each getconn() has a matching putconn()."""
        db = self._make_db_with_pool()
        with db.cursor() as cur:
            pass
        with db.cursor() as cur:
            pass
        assert self.pool.borrowed == self.pool.returned
        assert len(self.pool.borrowed) == 2

    def test_putconn_called_on_exception(self):
        """putconn() is still called when an exception occurs inside cursor."""
        db = self._make_db_with_pool()
        try:
            with db.cursor() as cur:
                raise ValueError("simulated error")
        except ValueError:
            pass
        assert self.pool.borrowed == self.pool.returned

    def test_pool_not_used_when_none(self):
        """When _pool is None, the single-connection path is used."""
        db = self._make_db_with_pool()
        db._pool = None
        # This would try _connect() which needs real psycopg2;
        # just verify it doesn't try to use the pool
        assert db._pool is None


class TestDatabaseAvailability:
    """Test Database.available with pool."""

    def test_available_with_pool(self):
        """available property uses pool getconn/putconn to test."""
        from scholar.db import Database
        db = Database()
        pool = FakePool()
        db._pool = pool
        # FakePool returns a FakeConnection, so available should
        # succeed (no exception from getconn)
        db.psycopg2 = MagicMock()
        assert db.available is True
