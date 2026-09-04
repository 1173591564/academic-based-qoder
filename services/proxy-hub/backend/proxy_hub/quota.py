"""Atomic request quota reservations and concurrency leases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Protocol

from sqlalchemy import case, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from proxy_hub.models import (
    AccessKeyUsageWindow,
    QuotaPolicy,
    QuotaReservationRecord,
    QuotaWindow,
    new_id,
)

MAX_RETRY_AFTER_SECONDS = 86_400


@dataclass(frozen=True)
class QuotaLimit:
    """Effective request and concurrency limits for one tenant."""

    quota_class: str
    request_limit: int
    period_seconds: int
    concurrency_limit: int
    enforcement_enabled: bool


@dataclass(frozen=True)
class QuotaReservation:
    """Result of atomically reserving one request."""

    reservation_id: str | None
    tenant_id: str
    window_start: datetime
    period_seconds: int
    remaining: int | None
    enforced: bool
    expires_at: datetime | None


class QuotaConfigurationError(RuntimeError):
    """A persisted quota policy cannot be enforced safely."""


class QuotaExceeded(RuntimeError):
    """A request or concurrency limit rejected a reservation."""

    def __init__(self, reason: str, retry_after_seconds: int) -> None:
        self.reason = reason
        self.retry_after_seconds = retry_after_seconds
        super().__init__(reason)


class QuotaService(Protocol):
    """Persistence boundary for request quota accounting."""

    def reserve(
        self,
        session: Session,
        tenant_id: str,
        limit: QuotaLimit | None,
        at: datetime,
    ) -> QuotaReservation:
        """Reserve one request before contacting Scholar."""

    def complete(
        self,
        session: Session,
        reservation: QuotaReservation,
        *,
        succeeded: bool,
        at: datetime,
    ) -> None:
        """Record the terminal result of a reserved request."""

    def refresh(
        self,
        session: Session,
        reservation: QuotaReservation,
        *,
        at: datetime,
    ) -> QuotaReservation:
        """Extend one active reservation lease."""


class DatabaseQuotaService:
    """SQL-backed quota service using conditional atomic updates."""

    def __init__(self, reservation_ttl: timedelta) -> None:
        if reservation_ttl <= timedelta(0):
            raise ValueError("reservation TTL must be positive")
        self._reservation_ttl = reservation_ttl

    def reserve(
        self,
        session: Session,
        tenant_id: str,
        limit: QuotaLimit | None,
        at: datetime,
    ) -> QuotaReservation:
        """Reserve request and concurrency capacity before upstream contact."""
        _require_aware(at)
        if limit is None or not limit.enforcement_enabled:
            return QuotaReservation(
                reservation_id=None,
                tenant_id=tenant_id,
                window_start=at,
                period_seconds=0,
                remaining=None,
                enforced=False,
                expires_at=None,
            )
        validate_quota_limit(limit)
        window_start = quota_window_start(at, limit.period_seconds)
        _ensure_window(session, tenant_id, window_start, limit.period_seconds)
        self._reap_expired(
            session,
            tenant_id,
            window_start,
            limit.period_seconds,
            at,
        )
        row = session.execute(
            update(QuotaWindow)
            .where(
                QuotaWindow.tenant_id == tenant_id,
                QuotaWindow.window_start == window_start,
                QuotaWindow.period_seconds == limit.period_seconds,
                QuotaWindow.reserved_count < limit.request_limit,
                QuotaWindow.active_count < limit.concurrency_limit,
            )
            .values(
                reserved_count=QuotaWindow.reserved_count + 1,
                active_count=QuotaWindow.active_count + 1,
                updated_at=at,
            )
            .returning(
                QuotaWindow.reserved_count,
                QuotaWindow.active_count,
            )
            .execution_options(synchronize_session=False)
        ).one_or_none()
        if row is None:
            window = session.get(
                QuotaWindow,
                (tenant_id, window_start, limit.period_seconds),
                populate_existing=True,
            )
            if window is None:
                raise QuotaConfigurationError("quota_window_missing")
            reason = (
                "request_limit_exceeded"
                if window.reserved_count >= limit.request_limit
                else "concurrency_limit_exceeded"
            )
            retry_after = (
                retry_after_seconds(window_start, limit.period_seconds, at)
                if reason == "request_limit_exceeded"
                else 1
            )
            raise QuotaExceeded(reason, retry_after)

        reservation_id = new_id("qres")
        expires_at = at + self._reservation_ttl
        session.add(
            QuotaReservationRecord(
                id=reservation_id,
                tenant_id=tenant_id,
                window_start=window_start,
                period_seconds=limit.period_seconds,
                expires_at=expires_at,
            )
        )
        return QuotaReservation(
            reservation_id=reservation_id,
            tenant_id=tenant_id,
            window_start=window_start,
            period_seconds=limit.period_seconds,
            remaining=remaining_requests(limit.request_limit, row.reserved_count),
            enforced=True,
            expires_at=expires_at,
        )

    def complete(
        self,
        session: Session,
        reservation: QuotaReservation,
        *,
        succeeded: bool,
        at: datetime,
    ) -> None:
        """Release concurrency once and classify the terminal result."""
        _require_aware(at)
        if not reservation.enforced or reservation.reservation_id is None:
            return
        status = "completed" if succeeded else "failed"
        completed_id = session.scalar(
            update(QuotaReservationRecord)
            .where(
                QuotaReservationRecord.id == reservation.reservation_id,
                QuotaReservationRecord.status == "active",
            )
            .values(
                status=status,
                completed_at=at,
            )
            .returning(QuotaReservationRecord.id)
            .execution_options(synchronize_session=False)
        )
        if completed_id is None:
            return
        counter = QuotaWindow.completed_count if succeeded else QuotaWindow.failed_count
        session.execute(
            update(QuotaWindow)
            .where(
                QuotaWindow.tenant_id == reservation.tenant_id,
                QuotaWindow.window_start == reservation.window_start,
                QuotaWindow.period_seconds == reservation.period_seconds,
            )
            .values(
                active_count=case(
                    (QuotaWindow.active_count > 0, QuotaWindow.active_count - 1),
                    else_=0,
                ),
                **{counter.key: counter + 1},
                updated_at=at,
            )
            .execution_options(synchronize_session=False)
        )

    def refresh(
        self,
        session: Session,
        reservation: QuotaReservation,
        *,
        at: datetime,
    ) -> QuotaReservation:
        """Extend an active lease without changing quota counters."""
        _require_aware(at)
        if not reservation.enforced or reservation.reservation_id is None:
            return reservation
        expires_at = at + self._reservation_ttl
        refreshed_id = session.scalar(
            update(QuotaReservationRecord)
            .where(
                QuotaReservationRecord.id == reservation.reservation_id,
                QuotaReservationRecord.status == "active",
            )
            .values(expires_at=expires_at)
            .returning(QuotaReservationRecord.id)
            .execution_options(synchronize_session=False)
        )
        if refreshed_id is None:
            raise QuotaConfigurationError("quota_reservation_inactive")
        return QuotaReservation(
            reservation_id=reservation.reservation_id,
            tenant_id=reservation.tenant_id,
            window_start=reservation.window_start,
            period_seconds=reservation.period_seconds,
            remaining=reservation.remaining,
            enforced=True,
            expires_at=expires_at,
        )

    def _reap_expired(
        self,
        session: Session,
        tenant_id: str,
        window_start: datetime,
        period_seconds: int,
        at: datetime,
    ) -> None:
        expired_ids = session.scalars(
            update(QuotaReservationRecord)
            .where(
                QuotaReservationRecord.tenant_id == tenant_id,
                QuotaReservationRecord.window_start == window_start,
                QuotaReservationRecord.period_seconds == period_seconds,
                QuotaReservationRecord.status == "active",
                QuotaReservationRecord.expires_at <= at,
            )
            .values(
                status="failed",
                completed_at=at,
            )
            .returning(QuotaReservationRecord.id)
            .execution_options(synchronize_session=False)
        ).all()
        expired_count = len(expired_ids)
        if expired_count == 0:
            return
        session.execute(
            update(QuotaWindow)
            .where(
                QuotaWindow.tenant_id == tenant_id,
                QuotaWindow.window_start == window_start,
                QuotaWindow.period_seconds == period_seconds,
            )
            .values(
                active_count=case(
                    (
                        QuotaWindow.active_count >= expired_count,
                        QuotaWindow.active_count - expired_count,
                    ),
                    else_=0,
                ),
                failed_count=QuotaWindow.failed_count + expired_count,
                updated_at=at,
            )
            .execution_options(synchronize_session=False)
        )


def load_quota_limit(session: Session, tenant_id: str) -> QuotaLimit | None:
    """Load one tenant's opt-in quota policy."""
    policy = session.get(QuotaPolicy, tenant_id)
    if policy is None:
        return None
    limit = QuotaLimit(
        quota_class=policy.quota_class,
        request_limit=policy.request_limit,
        period_seconds=policy.period_seconds,
        concurrency_limit=policy.concurrency_limit,
        enforcement_enabled=policy.enforcement_enabled,
    )
    validate_quota_limit(limit)
    return limit


def reserve_access_key_request(
    session: Session,
    access_key_id: str,
    request_limit: int | None,
    period_seconds: int | None,
    at: datetime,
) -> bool:
    """Consume one optional per-key request allowance."""
    _require_aware(at)
    if request_limit is None and period_seconds is None:
        return False
    if (
        request_limit is None
        or period_seconds is None
        or request_limit <= 0
        or period_seconds <= 0
    ):
        raise QuotaConfigurationError("access_key_quota_invalid")
    window_start = quota_window_start(at, period_seconds)
    key = (access_key_id, window_start, period_seconds)
    if session.get(AccessKeyUsageWindow, key) is None:
        try:
            with session.begin_nested():
                session.add(
                    AccessKeyUsageWindow(
                        access_key_id=access_key_id,
                        window_start=window_start,
                        period_seconds=period_seconds,
                    )
                )
                session.flush()
        except IntegrityError:
            session.expire_all()
    updated = session.scalar(
        update(AccessKeyUsageWindow)
        .where(
            AccessKeyUsageWindow.access_key_id == access_key_id,
            AccessKeyUsageWindow.window_start == window_start,
            AccessKeyUsageWindow.period_seconds == period_seconds,
            AccessKeyUsageWindow.request_count < request_limit,
        )
        .values(
            request_count=AccessKeyUsageWindow.request_count + 1,
            updated_at=at,
        )
        .returning(AccessKeyUsageWindow.request_count)
        .execution_options(synchronize_session=False)
    )
    if updated is None:
        raise QuotaExceeded(
            "access_key_request_limit_exceeded",
            retry_after_seconds(window_start, period_seconds, at),
        )
    return True


def validate_quota_limit(limit: QuotaLimit) -> None:
    """Reject persisted limits that cannot be enforced safely."""
    if (
        limit.request_limit <= 0
        or limit.period_seconds <= 0
        or limit.concurrency_limit <= 0
    ):
        raise QuotaConfigurationError("quota_policy_invalid")


def quota_window_start(at: datetime, period_seconds: int) -> datetime:
    """Return the UTC start of the quota period containing a timestamp."""
    _require_aware(at)
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


def retry_after_seconds(
    window_start: datetime,
    period_seconds: int,
    at: datetime,
) -> int:
    """Return a bounded Retry-After value for one exhausted window."""
    _require_aware(window_start)
    _require_aware(at)
    remaining = (window_start + timedelta(seconds=period_seconds) - at).total_seconds()
    return min(MAX_RETRY_AFTER_SECONDS, max(1, ceil(remaining)))


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("quota timestamps must be timezone-aware")


def _ensure_window(
    session: Session,
    tenant_id: str,
    window_start: datetime,
    period_seconds: int,
) -> None:
    key = (tenant_id, window_start, period_seconds)
    if session.get(QuotaWindow, key) is not None:
        return
    try:
        with session.begin_nested():
            session.add(
                QuotaWindow(
                    tenant_id=tenant_id,
                    window_start=window_start,
                    period_seconds=period_seconds,
                )
            )
            session.flush()
    except IntegrityError:
        session.expire_all()
    if session.get(QuotaWindow, key) is None:
        raise QuotaConfigurationError("quota_window_unavailable")
