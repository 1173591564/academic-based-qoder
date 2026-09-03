"""Quota service contracts and deterministic window calculations."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class QuotaLimit:
    """Effective request limit for one tenant."""

    quota_class: str
    request_limit: int
    period_seconds: int
    enforcement_enabled: bool


@dataclass(frozen=True)
class QuotaReservation:
    """Result of atomically reserving one request."""

    tenant_id: str
    window_start: datetime
    period_seconds: int
    remaining: int
    enforced: bool


class QuotaService(Protocol):
    """Persistence boundary for request quota accounting."""

    def reserve(
        self,
        session: Session,
        tenant_id: str,
        limit: QuotaLimit,
        at: datetime,
    ) -> QuotaReservation:
        """Reserve one request before contacting Scholar."""

    def complete(
        self,
        session: Session,
        reservation: QuotaReservation,
        *,
        succeeded: bool,
    ) -> None:
        """Record the terminal result of a reserved request."""


def quota_window_start(at: datetime, period_seconds: int) -> datetime:
    """Return the UTC start of the quota period containing a timestamp."""
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("quota timestamps must be timezone-aware")
    if period_seconds <= 0:
        raise ValueError("quota period must be positive")
    epoch_seconds = int(at.timestamp())
    start_seconds = epoch_seconds - (epoch_seconds % period_seconds)
    return datetime.fromtimestamp(start_seconds, tz=timezone.utc)


def remaining_requests(request_limit: int, reserved_count: int) -> int:
    """Return a non-negative number of requests still available."""
    if request_limit < 0 or reserved_count < 0:
        raise ValueError("quota counters must be non-negative")
    return max(request_limit - reserved_count, 0)
