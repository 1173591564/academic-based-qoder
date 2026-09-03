"""Audit and usage administration query tests."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from conftest import ApiHarness
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from proxy_hub.admin_observability import integer_metric, numeric_metric
from proxy_hub.models import (
    AuditEvent,
    BrowserSession,
    Membership,
    Principal,
    QuotaPolicy,
    QuotaWindow,
    RoleBinding,
    Tenant,
    new_id,
    utc_now,
)
from proxy_hub.rbac import AUDITOR, OPERATOR
from proxy_hub.security import digest_token


def range_params(
    start: datetime,
    end: datetime,
    **extra: str | int,
) -> dict[str, str | int]:
    """Build explicit bounded administration query parameters."""
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        **extra,
    }


def test_usage_metrics_accept_postgres_numeric_aggregates() -> None:
    """PostgreSQL returns Decimal for avg/sum over integers; they must convert."""
    assert integer_metric(Decimal("42")) == 42
    assert integer_metric(7) == 7
    assert integer_metric(3.2) == 3
    assert numeric_metric(Decimal("12.5")) == 12.5
    assert numeric_metric(9) == 9.0
    with pytest.raises(RuntimeError):
        integer_metric("12")
    with pytest.raises(RuntimeError):
        numeric_metric(None)
    with pytest.raises(RuntimeError):
        integer_metric(True)


def add_tenant(session: Session, slug: str) -> Tenant:
    """Persist one active tenant."""
    tenant = Tenant(id=new_id("tenant"), slug=slug, name=slug.title())
    session.add(tenant)
    session.flush()
    return tenant


def add_browser_role(
    session: Session,
    tenant: Tenant,
    *,
    role: str,
    raw_session: str,
) -> Principal:
    """Persist one tenant-scoped browser principal."""
    principal = Principal(
        id=new_id("principal"),
        issuer="https://identity.test",
        subject=raw_session,
    )
    session.add(principal)
    session.flush()
    session.add(
        Membership(
            id=new_id("membership"),
            principal_id=principal.id,
            tenant_id=tenant.id,
        )
    )
    session.add(
        RoleBinding(
            id=new_id("role"),
            principal_id=principal.id,
            tenant_id=tenant.id,
            role=role,
        )
    )
    session.add(
        BrowserSession(
            id=digest_token(raw_session),
            principal_id=principal.id,
            csrf_digest=digest_token(f"{raw_session}-csrf"),
            expires_at=utc_now() + timedelta(hours=1),
        )
    )
    return principal


def add_audit(
    session: Session,
    *,
    event_id: str,
    tenant_id: str,
    occurred_at: datetime,
    outcome: str,
    latency_ms: int | None,
    returned_bytes: int | None,
    quota_delta: int | None,
) -> None:
    """Persist one minimized gateway event."""
    session.add(
        AuditEvent(
            id=event_id,
            occurred_at=occurred_at,
            request_id=f"request-{event_id}",
            principal_id="principal-sensitive",
            tenant_id=tenant_id,
            capability_id="capability-sensitive",
            mcp_session_digest="session-sensitive",
            action="mcp:tool",
            resource_type="scholar_backend",
            resource_id="backend-one",
            outcome=outcome,
            tool_name="scholar_search",
            argument_digest="argument-sensitive",
            backend_id="backend-one",
            corpus_version="corpus-v1",
            decision="permit" if outcome != "rejected" else "deny",
            latency_ms=latency_ms,
            result_class="2xx" if outcome == "forwarded" else "error",
            returned_bytes=returned_bytes,
            quota_delta=quota_delta,
            details={
                "reason": "bounded",
                "request_body": "must-not-be-returned",
            },
        )
    )


def test_audit_query_is_stable_paginated_and_minimized(
    api_harness: ApiHarness,
) -> None:
    now = datetime(2026, 9, 3, 12, tzinfo=timezone.utc)
    with Session(api_harness.engine) as session:
        tenant = add_tenant(session, "audit-page")
        add_audit(
            session,
            event_id="audit_c",
            tenant_id=tenant.id,
            occurred_at=now,
            outcome="forwarded",
            latency_ms=10,
            returned_bytes=100,
            quota_delta=1,
        )
        add_audit(
            session,
            event_id="audit_b",
            tenant_id=tenant.id,
            occurred_at=now,
            outcome="failed",
            latency_ms=20,
            returned_bytes=None,
            quota_delta=1,
        )
        add_audit(
            session,
            event_id="audit_a",
            tenant_id=tenant.id,
            occurred_at=now,
            outcome="rejected",
            latency_ms=None,
            returned_bytes=None,
            quota_delta=0,
        )
        session.commit()

    first = api_harness.client.get(
        "/v1/admin/audit-events",
        params=range_params(
            now - timedelta(minutes=1),
            now + timedelta(minutes=1),
            limit=2,
        ),
    )
    second = api_harness.client.get(
        "/v1/admin/audit-events",
        params=range_params(
            now - timedelta(minutes=1),
            now + timedelta(minutes=1),
            cursor=first.json()["next_cursor"],
            limit=2,
        ),
    )

    assert first.status_code == 200
    assert [item["id"] for item in first.json()["items"]] == [
        "audit_c",
        "audit_b",
    ]
    assert [item["id"] for item in second.json()["items"]] == ["audit_a"]
    assert second.json()["next_cursor"] is None
    item = first.json()["items"][0]
    assert "details" not in item
    assert "argument_digest" not in item
    assert "capability_id" not in item
    assert "mcp_session_digest" not in item


def test_audit_query_rejects_unbounded_range_and_invalid_cursor(
    api_harness: ApiHarness,
) -> None:
    now = utc_now()

    unbounded = api_harness.client.get(
        "/v1/admin/audit-events",
        params=range_params(now - timedelta(days=32), now),
    )
    invalid_cursor = api_harness.client.get(
        "/v1/admin/audit-events",
        params=range_params(
            now - timedelta(hours=1),
            now,
            cursor="not-a-valid-cursor",
        ),
    )

    assert unbounded.status_code == 400
    assert unbounded.json()["error"]["code"] == "time_range_too_large"
    assert invalid_cursor.status_code == 400
    assert invalid_cursor.json()["error"]["code"] == "cursor_invalid"


def test_tenant_audit_requires_auditor_scope(api_harness: ApiHarness) -> None:
    now = utc_now()
    with Session(api_harness.engine) as session:
        visible = add_tenant(session, "auditor-visible")
        hidden = add_tenant(session, "auditor-hidden")
        add_browser_role(
            session,
            visible,
            role=AUDITOR,
            raw_session="auditor-session",
        )
        session.commit()
        visible_id = visible.id
        hidden_id = hidden.id

    client: TestClient = api_harness.client
    client.cookies.set("proxy_hub_session", "auditor-session")
    visible_response = client.get(
        f"/v1/admin/tenants/{visible_id}/audit-events",
        params=range_params(now - timedelta(hours=1), now + timedelta(minutes=1)),
    )
    hidden_response = client.get(
        f"/v1/admin/tenants/{hidden_id}/audit-events",
        params=range_params(now - timedelta(hours=1), now + timedelta(minutes=1)),
    )
    global_response = client.get(
        "/v1/admin/audit-events",
        params=range_params(now - timedelta(hours=1), now + timedelta(minutes=1)),
    )

    assert visible_response.status_code == 200
    assert hidden_response.status_code == 404
    assert global_response.status_code == 403
    assert global_response.json()["error"]["code"] == "audit_role_denied"


def test_usage_aggregates_gateway_metadata_without_mutating_quota(
    api_harness: ApiHarness,
) -> None:
    now = datetime(2026, 9, 3, 12, tzinfo=timezone.utc)
    window_start = now - timedelta(hours=1)
    with Session(api_harness.engine) as session:
        tenant = add_tenant(session, "usage-summary")
        session.add(
            QuotaPolicy(
                tenant_id=tenant.id,
                quota_class="research",
                request_limit=100,
                period_seconds=3600,
                concurrency_limit=5,
                enforcement_enabled=True,
            )
        )
        session.add(
            QuotaWindow(
                tenant_id=tenant.id,
                window_start=window_start,
                period_seconds=3600,
                reserved_count=10,
                active_count=2,
                completed_count=6,
                failed_count=2,
            )
        )
        for event_id, outcome, latency, size, delta in (
            ("audit_1", "forwarded", 20, 100, 1),
            ("audit_2", "forwarded", 40, 200, 1),
            ("audit_3", "failed", 10, None, 1),
            ("audit_4", "rejected", None, None, 0),
        ):
            add_audit(
                session,
                event_id=event_id,
                tenant_id=tenant.id,
                occurred_at=now,
                outcome=outcome,
                latency_ms=latency,
                returned_bytes=size,
                quota_delta=delta,
            )
        session.commit()
        tenant_id = tenant.id

    response = api_harness.client.get(
        f"/v1/admin/tenants/{tenant_id}/usage",
        params=range_params(
            now - timedelta(minutes=1),
            now + timedelta(minutes=1),
        ),
    )

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "tenant_id": tenant_id,
            "requests": {
                "total": 4,
                "successful": 2,
                "failed": 1,
                "rejected": 1,
            },
            "latency": {
                "samples": 3,
                "average_ms": 23.33,
                "maximum_ms": 40,
            },
            "returned_bytes": 300,
            "quota": {
                "consumed": 3,
                "configured": True,
                "quota_class": "research",
                "request_limit": 100,
                "period_seconds": 3600,
                "concurrency_limit": 5,
                "enforcement_enabled": True,
            },
        }
    ]
    with Session(api_harness.engine) as session:
        window = session.get(QuotaWindow, (tenant_id, window_start, 3600))
        assert window is not None
        assert (
            window.reserved_count,
            window.active_count,
            window.completed_count,
            window.failed_count,
        ) == (10, 2, 6, 2)


def test_operator_can_read_assigned_usage_but_not_audit(
    api_harness: ApiHarness,
) -> None:
    now = utc_now()
    with Session(api_harness.engine) as session:
        tenant = add_tenant(session, "operator-usage")
        add_browser_role(
            session,
            tenant,
            role=OPERATOR,
            raw_session="usage-operator-session",
        )
        session.commit()
        tenant_id = tenant.id

    client: TestClient = api_harness.client
    client.cookies.set("proxy_hub_session", "usage-operator-session")
    params = range_params(now - timedelta(hours=1), now + timedelta(minutes=1))
    usage = client.get(f"/v1/admin/tenants/{tenant_id}/usage", params=params)
    audit = client.get(
        f"/v1/admin/tenants/{tenant_id}/audit-events",
        params=params,
    )

    assert usage.status_code == 200
    assert audit.status_code == 403
    assert audit.json()["error"]["code"] == "audit_role_denied"


def test_global_usage_uses_stable_tenant_cursor(
    api_harness: ApiHarness,
) -> None:
    now = utc_now()
    with Session(api_harness.engine) as session:
        first_tenant = add_tenant(session, "usage-first")
        second_tenant = add_tenant(session, "usage-second")
        session.commit()
        expected_ids = sorted([first_tenant.id, second_tenant.id])

    first = api_harness.client.get(
        "/v1/admin/usage",
        params=range_params(
            now - timedelta(hours=1),
            now + timedelta(minutes=1),
            limit=1,
        ),
    )
    second = api_harness.client.get(
        "/v1/admin/usage",
        params=range_params(
            now - timedelta(hours=1),
            now + timedelta(minutes=1),
            cursor=first.json()["next_cursor"],
            limit=1,
        ),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert [
        first.json()["items"][0]["tenant_id"],
        second.json()["items"][0]["tenant_id"],
    ] == expected_ids
    assert second.json()["next_cursor"] is None
