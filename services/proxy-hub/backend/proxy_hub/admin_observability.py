"""Bounded administration queries for minimized audit and usage metadata."""

from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.orm import Session

from proxy_hub.auth import AuthComponents, ensure_utc
from proxy_hub.database import Database, session_scope
from proxy_hub.errors import HubError
from proxy_hub.models import AuditEvent, QuotaPolicy, Tenant
from proxy_hub.rbac import (
    AUDITOR,
    OPERATOR,
    TENANT_ADMIN,
    AdminContext,
)

MAX_QUERY_RANGE = timedelta(days=31)
MCP_ACTIONS = ("mcp:tool", "mcp:forward")
USAGE_ROLES = frozenset({TENANT_ADMIN, OPERATOR, AUDITOR})


@dataclass(frozen=True)
class TimeRange:
    """Validated inclusive-exclusive administration query range."""

    start: datetime
    end: datetime


def encode_cursor(*parts: str) -> str:
    """Encode stable non-sensitive cursor fields."""
    value = "\x1f".join(parts).encode("utf-8")
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def decode_cursor(cursor: str, expected_parts: int) -> tuple[str, ...]:
    """Decode one opaque cursor or reject malformed input."""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        parts = urlsafe_b64decode(padded.encode("ascii")).decode("utf-8").split("\x1f")
    except (UnicodeDecodeError, ValueError) as error:
        raise HubError(
            400,
            "cursor_invalid",
            "The pagination cursor is invalid.",
        ) from error
    if len(parts) != expected_parts or any(not part for part in parts):
        raise HubError(
            400,
            "cursor_invalid",
            "The pagination cursor is invalid.",
        )
    return tuple(parts)


def validated_time_range(start: datetime, end: datetime) -> TimeRange:
    """Require timezone-aware, ordered, bounded query timestamps."""
    if start.tzinfo is None or end.tzinfo is None:
        raise HubError(
            400,
            "time_range_invalid",
            "Audit and usage timestamps must include a timezone.",
        )
    normalized_start = ensure_utc(start)
    normalized_end = ensure_utc(end)
    if normalized_end <= normalized_start:
        raise HubError(
            400,
            "time_range_invalid",
            "The query end must be later than its start.",
        )
    if normalized_end - normalized_start > MAX_QUERY_RANGE:
        raise HubError(
            400,
            "time_range_too_large",
            "Audit and usage queries are limited to 31 days.",
        )
    return TimeRange(normalized_start, normalized_end)


def has_global_audit_access(context: AdminContext) -> bool:
    """Return whether the caller can read cross-tenant audit data."""
    return context.is_platform_admin or any(
        grant.role == AUDITOR and grant.tenant_id is None for grant in context.grants
    )


def require_global_audit_access(context: AdminContext) -> None:
    """Require platform-wide audit visibility."""
    if not has_global_audit_access(context):
        raise HubError(
            403,
            "audit_role_denied",
            "This operation requires a platform audit role.",
        )


def has_tenant_role(
    context: AdminContext,
    tenant_id: str,
    roles: frozenset[str],
) -> bool:
    """Return whether a caller has one allowed active tenant grant."""
    return context.is_platform_admin or any(
        grant.role in roles and grant.tenant_id == tenant_id for grant in context.grants
    )


def require_tenant_audit_access(context: AdminContext, tenant_id: str) -> None:
    """Hide tenants outside audit scope and reject non-auditor roles."""
    if has_global_audit_access(context):
        return
    visible = any(grant.tenant_id == tenant_id for grant in context.grants)
    if not visible:
        raise HubError(
            404,
            "tenant_not_found",
            "The requested tenant is not available.",
        )
    if not has_tenant_role(context, tenant_id, frozenset({AUDITOR})):
        raise HubError(
            403,
            "audit_role_denied",
            "This operation requires a tenant audit role.",
        )


def require_tenant_usage_access(context: AdminContext, tenant_id: str) -> None:
    """Hide tenants outside usage scope and enforce an allowed tenant role."""
    if has_global_audit_access(context):
        return
    visible = any(grant.tenant_id == tenant_id for grant in context.grants)
    if not visible:
        raise HubError(
            404,
            "tenant_not_found",
            "The requested tenant is not available.",
        )
    if not has_tenant_role(context, tenant_id, USAGE_ROLES):
        raise HubError(
            403,
            "usage_role_denied",
            "This operation requires a tenant operations or audit role.",
        )


def audit_event_body(event: AuditEvent) -> dict[str, object]:
    """Serialize only bounded authorization and operational metadata."""
    return {
        "id": event.id,
        "occurred_at": ensure_utc(event.occurred_at).isoformat(),
        "request_id": event.request_id,
        "principal_id": event.principal_id,
        "tenant_id": event.tenant_id,
        "action": event.action,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "outcome": event.outcome,
        "tool_name": event.tool_name,
        "backend_id": event.backend_id,
        "corpus_version": event.corpus_version,
        "decision": event.decision,
        "result_class": event.result_class,
        "latency_ms": event.latency_ms,
        "returned_bytes": event.returned_bytes,
        "quota_delta": event.quota_delta,
    }


def audit_page(
    session: Session,
    time_range: TimeRange,
    *,
    tenant_id: str | None,
    cursor: str | None,
    limit: int,
) -> dict[str, object]:
    """Return a stable descending page of immutable audit events."""
    statement = select(AuditEvent).where(
        AuditEvent.occurred_at >= time_range.start,
        AuditEvent.occurred_at < time_range.end,
    )
    if tenant_id is not None:
        statement = statement.where(AuditEvent.tenant_id == tenant_id)
    if cursor is not None:
        occurred_text, event_id = decode_cursor(cursor, 2)
        try:
            occurred_at = datetime.fromisoformat(occurred_text)
        except ValueError as error:
            raise HubError(
                400,
                "cursor_invalid",
                "The pagination cursor is invalid.",
            ) from error
        if occurred_at.tzinfo is None:
            raise HubError(
                400,
                "cursor_invalid",
                "The pagination cursor is invalid.",
            )
        occurred_at = ensure_utc(occurred_at)
        statement = statement.where(
            or_(
                AuditEvent.occurred_at < occurred_at,
                and_(
                    AuditEvent.occurred_at == occurred_at,
                    AuditEvent.id < event_id,
                ),
            )
        )
    events = session.scalars(
        statement.order_by(
            AuditEvent.occurred_at.desc(),
            AuditEvent.id.desc(),
        ).limit(limit + 1)
    ).all()
    page = events[:limit]
    next_cursor = None
    if len(events) > limit and page:
        last = page[-1]
        next_cursor = encode_cursor(ensure_utc(last.occurred_at).isoformat(), last.id)
    return {
        "items": [audit_event_body(event) for event in page],
        "next_cursor": next_cursor,
        "range": {
            "from": time_range.start.isoformat(),
            "to": time_range.end.isoformat(),
        },
    }


def usage_statement(
    time_range: TimeRange,
    tenant_ids: list[str],
) -> Select[tuple[object, ...]]:
    """Build one aggregate statement over minimized gateway audit columns."""
    return (
        select(
            AuditEvent.tenant_id,
            func.count(AuditEvent.id),
            func.sum(case((AuditEvent.outcome == "forwarded", 1), else_=0)),
            func.sum(case((AuditEvent.outcome == "failed", 1), else_=0)),
            func.sum(case((AuditEvent.outcome == "rejected", 1), else_=0)),
            func.count(AuditEvent.latency_ms),
            func.avg(AuditEvent.latency_ms),
            func.max(AuditEvent.latency_ms),
            func.coalesce(func.sum(AuditEvent.returned_bytes), 0),
            func.coalesce(func.sum(AuditEvent.quota_delta), 0),
        )
        .where(
            AuditEvent.tenant_id.in_(tenant_ids),
            AuditEvent.action.in_(MCP_ACTIONS),
            AuditEvent.occurred_at >= time_range.start,
            AuditEvent.occurred_at < time_range.end,
        )
        .group_by(AuditEvent.tenant_id)
    )


def usage_item(
    tenant: Tenant,
    policy: QuotaPolicy | None,
    metrics: tuple[object, ...] | None,
) -> dict[str, object]:
    """Serialize aggregate usage without request or research content."""
    values = metrics or (tenant.id, 0, 0, 0, 0, 0, None, None, 0, 0)
    latency_samples = integer_metric(values[5])
    return {
        "tenant_id": tenant.id,
        "requests": {
            "total": integer_metric(values[1]),
            "successful": integer_metric(values[2]),
            "failed": integer_metric(values[3]),
            "rejected": integer_metric(values[4]),
        },
        "latency": {
            "samples": latency_samples,
            "average_ms": (
                round(numeric_metric(values[6]), 2) if values[6] is not None else None
            ),
            "maximum_ms": (
                integer_metric(values[7]) if values[7] is not None else None
            ),
        },
        "returned_bytes": integer_metric(values[8]),
        "quota": {
            "consumed": integer_metric(values[9]),
            "configured": policy is not None,
            "quota_class": policy.quota_class if policy is not None else None,
            "request_limit": policy.request_limit if policy is not None else None,
            "period_seconds": policy.period_seconds if policy is not None else None,
            "concurrency_limit": (
                policy.concurrency_limit if policy is not None else None
            ),
            "enforcement_enabled": (
                policy.enforcement_enabled if policy is not None else False
            ),
        },
    }


def integer_metric(value: object) -> int:
    """Convert a database integer aggregate without weakening its type."""
    if isinstance(value, bool):
        raise RuntimeError("usage integer aggregate has an invalid type")
    if isinstance(value, (int, float, Decimal)):
        return int(value)
    raise RuntimeError("usage integer aggregate has an invalid type")


def numeric_metric(value: object) -> float:
    """Convert a database numeric aggregate without weakening its type."""
    if isinstance(value, bool):
        raise RuntimeError("usage numeric aggregate has an invalid type")
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    raise RuntimeError("usage numeric aggregate has an invalid type")


def usage_page(
    session: Session,
    time_range: TimeRange,
    *,
    tenant_id: str | None,
    cursor: str | None,
    limit: int,
) -> dict[str, object]:
    """Return stable tenant-ordered aggregate usage rows."""
    tenant_query = select(Tenant)
    if tenant_id is not None:
        tenant_query = tenant_query.where(Tenant.id == tenant_id)
    if cursor is not None:
        (cursor_tenant_id,) = decode_cursor(cursor, 1)
        tenant_query = tenant_query.where(Tenant.id > cursor_tenant_id)
    tenants = session.scalars(tenant_query.order_by(Tenant.id).limit(limit + 1)).all()
    page = tenants[:limit]
    tenant_ids = [tenant.id for tenant in page]
    metrics = {
        str(row[0]): tuple(row)
        for row in (
            session.execute(usage_statement(time_range, tenant_ids)).all()
            if tenant_ids
            else []
        )
    }
    policies = {
        policy.tenant_id: policy
        for policy in (
            session.scalars(
                select(QuotaPolicy).where(QuotaPolicy.tenant_id.in_(tenant_ids))
            ).all()
            if tenant_ids
            else []
        )
    }
    next_cursor = None
    if len(tenants) > limit and page:
        next_cursor = encode_cursor(page[-1].id)
    return {
        "items": [
            usage_item(
                tenant,
                policies.get(tenant.id),
                metrics.get(tenant.id),
            )
            for tenant in page
        ],
        "next_cursor": next_cursor,
        "range": {
            "from": time_range.start.isoformat(),
            "to": time_range.end.isoformat(),
        },
    }


def build_observability_router(
    database: Database,
    auth: AuthComponents,
) -> APIRouter:
    """Create read-only audit and usage administration routes."""
    router = APIRouter()

    def get_session() -> Generator[Session, None, None]:
        yield from session_scope(database)

    def query_range(
        start: datetime = Query(alias="from"),
        end: datetime = Query(alias="to"),
    ) -> TimeRange:
        return validated_time_range(start, end)

    @router.get("/audit-events")
    def list_audit_events(
        time_range: TimeRange = Depends(query_range),
        cursor: str | None = Query(default=None, max_length=512),
        limit: int = Query(default=50, ge=1, le=100),
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        require_global_audit_access(context)
        return audit_page(
            session,
            time_range,
            tenant_id=None,
            cursor=cursor,
            limit=limit,
        )

    @router.get("/tenants/{tenant_id}/audit-events")
    def list_tenant_audit_events(
        tenant_id: str,
        time_range: TimeRange = Depends(query_range),
        cursor: str | None = Query(default=None, max_length=512),
        limit: int = Query(default=50, ge=1, le=100),
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        require_tenant_audit_access(context, tenant_id)
        if session.get(Tenant, tenant_id) is None:
            raise HubError(
                404,
                "tenant_not_found",
                "The requested tenant is not available.",
            )
        return audit_page(
            session,
            time_range,
            tenant_id=tenant_id,
            cursor=cursor,
            limit=limit,
        )

    @router.get("/usage")
    def list_usage(
        time_range: TimeRange = Depends(query_range),
        cursor: str | None = Query(default=None, max_length=512),
        limit: int = Query(default=50, ge=1, le=100),
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        require_global_audit_access(context)
        return usage_page(
            session,
            time_range,
            tenant_id=None,
            cursor=cursor,
            limit=limit,
        )

    @router.get("/tenants/{tenant_id}/usage")
    def get_tenant_usage(
        tenant_id: str,
        time_range: TimeRange = Depends(query_range),
        cursor: str | None = Query(default=None, max_length=512),
        limit: int = Query(default=50, ge=1, le=100),
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        require_tenant_usage_access(context, tenant_id)
        if session.get(Tenant, tenant_id) is None:
            raise HubError(
                404,
                "tenant_not_found",
                "The requested tenant is not available.",
            )
        return usage_page(
            session,
            time_range,
            tenant_id=tenant_id,
            cursor=cursor,
            limit=limit,
        )

    return router
