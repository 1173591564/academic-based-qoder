"""
Scholar Studio — Shared State for MCP Server

Provides connection pooling and cached resources for the MCP server's
long-running process. CLI mode does not use this module — each CLI
invocation is a fresh process with no shared state.

Usage (MCP server):
    from scholar._state import init_shared_state, get_state
    init_shared_state()  # call once at startup
    state = get_state()  # use in tool handlers
"""
import threading
from typing import Optional

from . import config
from . import db as dbmod


class SharedState:
    """Process-level shared state for MCP server.

    Holds a PostgreSQL connection pool, cached ID resolver, and
    an LRU cache for parsed JSON files. All expensive one-time
    initializations happen here.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._pool = None            # psycopg2 ThreadedConnectionPool
        self._id_resolver = None     # IDResolver cache (279ms one-time)
        self._parsed_cache: dict[str, dict] = {}
        self._parsed_cache_max = 100

    # ── Database ──────────────────────────────────────────────

    def get_db(self) -> Optional[dbmod.Database]:
        """Get Database instance backed by connection pool (if available)."""
        db = dbmod.Database()
        if self._pool:
            db._pool = self._pool
        return db

    # ── ID Resolver ───────────────────────────────────────────

    def get_id_resolver(self):
        """Get cached ID resolver (loads 555 JSON files once, ~280ms)."""
        if self._id_resolver is None:
            with self._lock:
                if self._id_resolver is None:
                    from .id_resolver import IDResolver
                    resolver = IDResolver()
                    resolver._ensure_loaded()
                    self._id_resolver = resolver
        return self._id_resolver

    def resolve_id(self, paper_id: str) -> Optional[str]:
        """Resolve hybrid ID to ULID using cached resolver."""
        resolver = self.get_id_resolver()
        return resolver.resolve(paper_id)

    # ── Parsed JSON Cache ─────────────────────────────────────

    def get_parsed(self, paper_id: str) -> Optional[dict]:
        """LRU-cached parsed JSON reader."""
        if paper_id in self._parsed_cache:
            return self._parsed_cache[paper_id]
        data = dbmod.load_parsed(paper_id)
        if data:
            if len(self._parsed_cache) >= self._parsed_cache_max:
                # Evict oldest entry (simple FIFO, good enough)
                self._parsed_cache.pop(next(iter(self._parsed_cache)))
            self._parsed_cache[paper_id] = data
        return data

    def invalidate_parsed(self, paper_id: str = None):
        """Invalidate cache for one paper or all."""
        if paper_id:
            self._parsed_cache.pop(paper_id, None)
        else:
            self._parsed_cache.clear()

    # ── Connection Pool ───────────────────────────────────────

    def init_pool(self):
        """Initialize PG connection pool. Safe to call if PG is down."""
        try:
            import psycopg2.pool
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2, maxconn=8,
                host=config.PG_HOST,
                port=config.PG_PORT,
                dbname=config.PG_NAME,
                user=config.PG_USER,
                password=config.PG_PASS,
            )
        except Exception:
            pass  # PG not available — file-only mode

    def close(self):
        """Clean up all resources."""
        if self._pool:
            try:
                self._pool.closeall()
            except Exception:
                pass
            self._pool = None


# ── Module-level singleton ────────────────────────────────────

_state: Optional[SharedState] = None


def init_shared_state():
    """Initialize shared state for MCP server. Call once at startup."""
    global _state
    _state = SharedState()
    _state.init_pool()
    _state.get_id_resolver()  # preload (280ms, one-time)


def get_state() -> Optional[SharedState]:
    """Get the shared state instance, or None if not initialized."""
    return _state
