"""PostgreSQL runtime primitives for immutable Scholar v2 projections."""

from __future__ import annotations

import hashlib
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import psycopg2
import psycopg2.extras
import psycopg2.pool

from scholar import config

from .models import ScholarError


@dataclass(frozen=True)
class DatabaseSettings:
    min_connections: int = 1
    max_connections: int = 8
    acquire_timeout_ms: int = 2_000
    statement_timeout_ms: int = 15_000
    lock_timeout_ms: int = 1_000

    @classmethod
    def from_config(cls) -> "DatabaseSettings":
        return cls(
            min_connections=config.V2_PG_POOL_MIN,
            max_connections=config.V2_PG_POOL_MAX,
            acquire_timeout_ms=config.V2_PG_ACQUIRE_TIMEOUT_MS,
            statement_timeout_ms=config.V2_PG_STATEMENT_TIMEOUT_MS,
            lock_timeout_ms=config.V2_PG_LOCK_TIMEOUT_MS,
        )


class V2Database:
    """Pool-backed database facade with bounded acquisition and transactions."""

    def __init__(self, pool=None, settings: DatabaseSettings | None = None):
        self.settings = settings or DatabaseSettings.from_config()
        self._pool = pool
        self._permits = threading.BoundedSemaphore(self.settings.max_connections)
        self._pool_lock = threading.Lock()

    def initialize_pool(self) -> None:
        if self._pool is not None:
            return
        with self._pool_lock:
            if self._pool is not None:
                return
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=self.settings.min_connections,
                maxconn=self.settings.max_connections,
                host=config.PG_HOST,
                port=config.PG_PORT,
                dbname=config.PG_NAME,
                user=config.PG_USER,
                password=config.PG_PASS,
                connect_timeout=max(1, config.V2_PG_CONNECT_TIMEOUT_MS // 1000),
                application_name="scholar-v2",
            )

    @property
    def available(self) -> bool:
        try:
            with self.cursor(read_only=True) as cur:
                cur.execute("SELECT 1")
                return cur.fetchone()[0] == 1
        except Exception:
            return False

    @contextmanager
    def connection(self, read_only: bool = False):
        self.initialize_pool()
        timeout = self.settings.acquire_timeout_ms / 1000
        if not self._permits.acquire(timeout=timeout):
            raise ScholarError("SERVER_BUSY", "database connection pool is saturated")
        conn = None
        try:
            try:
                conn = self._pool.getconn()
            except psycopg2.pool.PoolError as error:
                raise ScholarError(
                    "SERVER_BUSY", "database connection pool is saturated"
                ) from error
            conn.autocommit = False
            conn.set_session(readonly=read_only)
            with conn.cursor() as cur:
                cur.execute(
                    "SET LOCAL statement_timeout = %s",
                    (self.settings.statement_timeout_ms,),
                )
                cur.execute(
                    "SET LOCAL lock_timeout = %s",
                    (self.settings.lock_timeout_ms,),
                )
            yield conn
            conn.commit()
        except ScholarError:
            if conn is not None:
                self._rollback(conn)
            raise
        except psycopg2.errors.QueryCanceled as error:
            if conn is not None:
                self._rollback(conn)
            raise ScholarError(
                "DEADLINE_EXCEEDED", "database statement deadline exceeded"
            ) from error
        except psycopg2.errors.LockNotAvailable as error:
            if conn is not None:
                self._rollback(conn)
            raise ScholarError(
                "SERVER_BUSY", "database lock timeout exceeded"
            ) from error
        except Exception:
            if conn is not None:
                self._rollback(conn)
            raise
        finally:
            try:
                if conn is not None:
                    try:
                        conn.set_session(readonly=False)
                    except psycopg2.Error:
                        self._pool.putconn(conn, close=True)
                    else:
                        self._pool.putconn(conn)
            finally:
                self._permits.release()

    @staticmethod
    def _rollback(conn) -> None:
        try:
            conn.rollback()
        except psycopg2.Error:
            pass

    @contextmanager
    def cursor(self, read_only: bool = False, dict_rows: bool = False):
        factory = psycopg2.extras.RealDictCursor if dict_rows else None
        with self.connection(read_only=read_only) as conn:
            with conn.cursor(cursor_factory=factory) as cur:
                yield cur

    def close(self) -> None:
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None

    def apply_schema(self) -> None:
        schema_path = Path(__file__).with_name("schema.sql")
        schema = schema_path.read_text(encoding="utf-8")
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(schema)

    def initialize(self) -> None:
        self.apply_schema()

    @contextmanager
    def advisory_lock(self, key: str) -> Iterator[None]:
        """Acquire a session advisory lock without indefinite waiting."""
        deadline = time.monotonic() + self.settings.lock_timeout_ms / 1000
        lock_id = int.from_bytes(
            hashlib.sha256(key.encode("utf-8")).digest()[:8],
            byteorder="big",
            signed=True,
        )
        with self.connection() as conn:
            acquired = False
            try:
                with conn.cursor() as cur:
                    while time.monotonic() < deadline:
                        cur.execute("SELECT pg_try_advisory_lock(%s)", (lock_id,))
                        if cur.fetchone()[0]:
                            acquired = True
                            break
                        time.sleep(0.05)
                if not acquired:
                    raise ScholarError(
                        "SERVER_BUSY", "projection build is already running"
                    )
                yield
            finally:
                if acquired:
                    with conn.cursor() as cur:
                        cur.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))

    def active_snapshot(self, channel: str | None = None) -> dict:
        channel = channel or config.V2_SERVING_CHANNEL
        with self.cursor(read_only=True, dict_rows=True) as cur:
            cur.execute(
                """
                SELECT s.*, c.revision AS channel_revision, b.schema_version
                FROM scholar_v2_serving_channels c
                JOIN scholar_v2_serving_snapshots s ON s.id = c.snapshot_id
                JOIN scholar_v2_projection_builds b
                  ON b.id = s.relational_build_id
                WHERE c.name = %s AND s.status = 'ready'
                """,
                (channel,),
            )
            row = cur.fetchone()
        if not row:
            raise ScholarError(
                "SNAPSHOT_UNAVAILABLE",
                f"no ready Scholar v2 snapshot is active on channel {channel}",
            )
        return dict(row)

    def activate_snapshot(
        self,
        snapshot_id: str,
        channel: str | None = None,
        expected_revision: int | None = None,
    ) -> int:
        channel = channel or config.V2_SERVING_CHANNEL
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM scholar_v2_serving_snapshots
                    WHERE id = %s AND status = 'ready'
                    """,
                    (snapshot_id,),
                )
                if not cur.fetchone():
                    raise ScholarError("SNAPSHOT_UNAVAILABLE", "snapshot is not ready")
                cur.execute(
                    """
                    INSERT INTO scholar_v2_serving_channels(name, snapshot_id, revision)
                    VALUES (%s, %s, 1)
                    ON CONFLICT (name) DO NOTHING
                    RETURNING revision
                    """,
                    (channel, snapshot_id),
                )
                inserted = cur.fetchone()
                if inserted:
                    if expected_revision not in (None, 0):
                        raise ScholarError(
                            "SERVER_BUSY",
                            "serving channel did not exist at the expected revision",
                        )
                    return inserted[0]
                cur.execute(
                    """
                    SELECT revision FROM scholar_v2_serving_channels
                    WHERE name = %s FOR UPDATE
                    """,
                    (channel,),
                )
                revision = cur.fetchone()[0]
                if expected_revision is not None and revision != expected_revision:
                    raise ScholarError(
                        "SERVER_BUSY", "serving channel changed during activation"
                    )
                next_revision = revision + 1
                cur.execute(
                    """
                    UPDATE scholar_v2_serving_channels
                    SET snapshot_id = %s, revision = %s, updated_at = now()
                    WHERE name = %s
                    """,
                    (snapshot_id, next_revision, channel),
                )
                return next_revision

    def lease_job(
        self, worker_id: str, lease_seconds: int = 120, job_type: str | None = None
    ) -> dict | None:
        """Atomically lease one runnable job using SKIP LOCKED."""
        if not worker_id or lease_seconds < 1:
            raise ScholarError("INVALID_ARGUMENT", "invalid job lease")
        with self.connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    WITH candidate AS (
                        SELECT id
                        FROM scholar_v2_projection_jobs
                        WHERE (
                                status IN ('pending', 'retry')
                                OR (
                                    status = 'running'
                                    AND lease_expires_at < now()
                                )
                              )
                          AND attempt_count < max_attempts
                          AND run_after <= now()
                          AND (%s IS NULL OR job_type = %s)
                        ORDER BY priority DESC, created_at
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    UPDATE scholar_v2_projection_jobs j
                    SET status = 'running',
                        lease_owner = %s,
                        lease_expires_at = now() + make_interval(secs => %s),
                        heartbeat_at = now(),
                        attempt_count = attempt_count + 1,
                        updated_at = now()
                    FROM candidate
                    WHERE j.id = candidate.id
                    RETURNING j.*
                    """,
                    (job_type, job_type, worker_id, lease_seconds),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def heartbeat_job(
        self, job_id: str, worker_id: str, lease_seconds: int = 120
    ) -> bool:
        if not job_id or not worker_id or lease_seconds < 1:
            raise ScholarError("INVALID_ARGUMENT", "invalid job heartbeat")
        with self.cursor() as cur:
            cur.execute(
                """
                UPDATE scholar_v2_projection_jobs
                SET lease_expires_at = now() + make_interval(secs => %s),
                    heartbeat_at = now(),
                    updated_at = now()
                WHERE id = %s AND lease_owner = %s AND status = 'running'
                  AND lease_expires_at >= now()
                """,
                (lease_seconds, job_id, worker_id),
            )
            return cur.rowcount == 1
