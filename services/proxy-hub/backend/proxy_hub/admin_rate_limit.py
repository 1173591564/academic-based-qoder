"""Database-backed fixed-window administration rate limiting."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil

from sqlalchemy import case, or_
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from proxy_hub.models import AdminRateLimit


@dataclass(frozen=True)
class AdminRateDecision:
    """One administration request rate-limit decision."""

    allowed: bool
    remaining: int
    retry_after_seconds: int


def rate_window_start(at: datetime, period_seconds: int) -> datetime:
    """Return the UTC-aligned fixed-window boundary."""
    epoch = int(at.timestamp())
    return datetime.fromtimestamp(
        epoch - (epoch % period_seconds),
        tz=timezone.utc,
    )


def consume_admin_request(
    session: Session,
    session_id: str,
    *,
    request_limit: int,
    period_seconds: int,
    at: datetime,
) -> AdminRateDecision:
    """Atomically reserve one browser administration request."""
    window_start = rate_window_start(at, period_seconds)
    values = {
        "session_id": session_id,
        "window_started_at": window_start,
        "request_count": 1,
        "updated_at": at,
    }
    update_values = {
        "window_started_at": window_start,
        "request_count": case(
            (
                AdminRateLimit.window_started_at < window_start,
                1,
            ),
            else_=AdminRateLimit.request_count + 1,
        ),
        "updated_at": at,
    }
    update_condition = or_(
        AdminRateLimit.window_started_at < window_start,
        AdminRateLimit.request_count < request_limit,
    )
    dialect_name = session.get_bind().dialect.name
    if dialect_name == "postgresql":
        statement = (
            postgresql_insert(AdminRateLimit)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[AdminRateLimit.session_id],
                set_=update_values,
                where=update_condition,
            )
            .returning(AdminRateLimit.request_count)
        )
        reserved = session.scalar(statement)
    elif dialect_name == "sqlite":
        statement = (
            sqlite_insert(AdminRateLimit)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[AdminRateLimit.session_id],
                set_=update_values,
                where=update_condition,
            )
            .returning(AdminRateLimit.request_count)
        )
        reserved = session.scalar(statement)
    else:
        raise RuntimeError("admin rate limiting requires PostgreSQL or SQLite")
    next_window = window_start + timedelta(seconds=period_seconds)
    retry_after = max(1, ceil((next_window - at).total_seconds()))
    return AdminRateDecision(
        allowed=reserved is not None,
        remaining=max(0, request_limit - (reserved or request_limit)),
        retry_after_seconds=retry_after,
    )
