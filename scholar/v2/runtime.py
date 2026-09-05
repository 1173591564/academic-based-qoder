"""Request coordination, deadlines, cancellation, and snapshot pinning."""

from __future__ import annotations

import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field

from scholar import config

from .database import V2Database
from .models import ScholarError


@dataclass
class RequestContext:
    request_id: str
    deadline_monotonic: float
    snapshot: dict
    cancelled: threading.Event = field(default_factory=threading.Event)

    @property
    def snapshot_id(self) -> str:
        return self.snapshot["id"]

    def check(self) -> None:
        if self.cancelled.is_set():
            raise ScholarError("CANCELLED", "request was cancelled")
        if time.monotonic() >= self.deadline_monotonic:
            raise ScholarError("DEADLINE_EXCEEDED", "request deadline exceeded")

    def remaining_ms(self) -> int:
        return max(0, int((self.deadline_monotonic - time.monotonic()) * 1000))


class RequestCoordinator:
    """Bound request concurrency and pin one ready snapshot per request."""

    def __init__(
        self,
        database: V2Database,
        max_inflight: int = 32,
        acquire_timeout_ms: int = 250,
    ):
        self.database = database
        self.acquire_timeout_ms = acquire_timeout_ms
        self._global_permits = threading.BoundedSemaphore(max_inflight)
        self._tool_limits: dict[str, threading.BoundedSemaphore] = {}
        self._lock = threading.Lock()

    def set_tool_limit(self, tool_name: str, limit: int) -> None:
        if limit < 1:
            raise ValueError("tool concurrency limit must be positive")
        with self._lock:
            self._tool_limits[tool_name] = threading.BoundedSemaphore(limit)

    @contextmanager
    def request(
        self,
        tool_name: str,
        timeout_ms: int,
        request_id: str | None = None,
    ):
        if timeout_ms < 1:
            raise ScholarError("INVALID_ARGUMENT", "timeout must be positive")
        deadline = time.monotonic() + timeout_ms / 1000
        acquired_global = self._global_permits.acquire(
            timeout=min(
                self.acquire_timeout_ms / 1000,
                max(0, deadline - time.monotonic()),
            )
        )
        if not acquired_global:
            if time.monotonic() >= deadline:
                raise ScholarError("DEADLINE_EXCEEDED", "request deadline exceeded")
            raise ScholarError("SERVER_BUSY", "Scholar request capacity is saturated")
        tool_permit = self._tool_limits.get(tool_name)
        acquired_tool = False
        try:
            if tool_permit is not None:
                acquired_tool = tool_permit.acquire(
                    timeout=min(
                        self.acquire_timeout_ms / 1000,
                        max(0, deadline - time.monotonic()),
                    )
                )
                if not acquired_tool:
                    if time.monotonic() >= deadline:
                        raise ScholarError(
                            "DEADLINE_EXCEEDED", "request deadline exceeded"
                        )
                    raise ScholarError(
                        "SERVER_BUSY", f"{tool_name} request capacity is saturated"
                    )
            context = RequestContext(
                request_id=request_id or uuid.uuid4().hex,
                deadline_monotonic=deadline,
                snapshot=self.database.active_snapshot(),
            )
            context.check()
            yield context
        finally:
            if acquired_tool and tool_permit is not None:
                tool_permit.release()
            self._global_permits.release()


_database: V2Database | None = None
_coordinator: RequestCoordinator | None = None
_state_lock = threading.RLock()


def get_database() -> V2Database:
    global _database
    if _database is None:
        with _state_lock:
            if _database is None:
                _database = V2Database()
    return _database


def get_coordinator() -> RequestCoordinator:
    global _coordinator
    if _coordinator is None:
        with _state_lock:
            if _coordinator is None:
                coordinator = RequestCoordinator(
                    get_database(),
                    max_inflight=config.V2_MAX_INFLIGHT,
                    acquire_timeout_ms=config.V2_REQUEST_ACQUIRE_TIMEOUT_MS,
                )
                for tool_name in ("scholar_vec_search", "scholar_passages"):
                    coordinator.set_tool_limit(tool_name, config.V2_VECTOR_MAX_INFLIGHT)
                coordinator.set_tool_limit(
                    "compare_results", config.V2_SEMANTIC_MAX_INFLIGHT
                )
                coordinator.set_tool_limit(
                    "verify_claims", config.V2_SEMANTIC_MAX_INFLIGHT
                )
                _coordinator = coordinator
    return _coordinator


def reset_runtime() -> None:
    global _database, _coordinator
    with _state_lock:
        if _database is not None:
            _database.close()
        _database = None
        _coordinator = None
