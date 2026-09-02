"""Administration authentication, authorization, and mutation tests."""

from datetime import timedelta

from conftest import ApiHarness
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from proxy_hub.models import (
    AuditEvent,
    BrowserSession,
    Principal,
    RoleBinding,
    Tenant,
    new_id,
    utc_now,
)
from proxy_hub.rbac import OPERATOR
from proxy_hub.security import digest_token


def test_admin_routes_require_browser_session(api_harness: ApiHarness) -> None:
    api_harness.client.cookies.clear()

    response = api_harness.client.get("/v1/admin/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "browser_session_required"
    assert response.json()["error"]["request_id"].startswith("req_")


def test_oidc_login_fails_closed_when_unconfigured(
    api_harness: ApiHarness,
) -> None:
    response = api_harness.client.get("/auth/login", follow_redirects=False)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "oidc_unavailable"


def test_tenant_create_is_idempotent_and_audited(
    api_harness: ApiHarness,
) -> None:
    headers = {
        **api_harness.mutation_headers,
        "Idempotency-Key": "create-research",
    }
    payload = {"slug": "research-team", "name": "Research Team"}

    first = api_harness.client.post(
        "/v1/admin/tenants",
        json=payload,
        headers=headers,
    )
    replay = api_harness.client.post(
        "/v1/admin/tenants",
        json=payload,
        headers=headers,
    )

    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json() == first.json()
    assert replay.headers["ETag"] == first.headers["ETag"]
    with Session(api_harness.engine) as session:
        audit_count = session.scalar(select(func.count()).select_from(AuditEvent))
    assert audit_count == 1


def test_tenant_create_rejects_idempotency_key_reuse(
    api_harness: ApiHarness,
) -> None:
    headers = {
        **api_harness.mutation_headers,
        "Idempotency-Key": "create-conflict",
    }
    first = api_harness.client.post(
        "/v1/admin/tenants",
        json={"slug": "tenant-one", "name": "Tenant One"},
        headers=headers,
    )
    conflict = api_harness.client.post(
        "/v1/admin/tenants",
        json={"slug": "tenant-two", "name": "Tenant Two"},
        headers=headers,
    )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"


def test_tenant_update_requires_current_etag(api_harness: ApiHarness) -> None:
    create = api_harness.client.post(
        "/v1/admin/tenants",
        json={"slug": "etag-tenant", "name": "Before"},
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "create-etag",
        },
    )
    tenant_id = create.json()["id"]
    current_etag = create.headers["ETag"]

    updated = api_harness.client.patch(
        f"/v1/admin/tenants/{tenant_id}",
        json={"name": "After"},
        headers={**api_harness.mutation_headers, "If-Match": current_etag},
    )
    stale = api_harness.client.patch(
        f"/v1/admin/tenants/{tenant_id}",
        json={"status": "disabled"},
        headers={**api_harness.mutation_headers, "If-Match": current_etag},
    )

    assert updated.status_code == 200
    assert updated.json()["name"] == "After"
    assert updated.headers["ETag"] != current_etag
    assert stale.status_code == 412
    assert stale.json()["error"]["code"] == "etag_mismatch"


def test_mutation_requires_same_origin_and_csrf(
    api_harness: ApiHarness,
) -> None:
    response = api_harness.client.post(
        "/v1/admin/tenants",
        json={"slug": "denied-tenant", "name": "Denied"},
        headers={"Idempotency-Key": "csrf-denied"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "origin_denied"


def test_logout_revokes_session_and_is_audited(
    api_harness: ApiHarness,
) -> None:
    logout = api_harness.client.post(
        "/v1/admin/logout",
        headers=api_harness.mutation_headers,
    )
    after_logout = api_harness.client.get("/v1/admin/me")

    assert logout.status_code == 204
    assert after_logout.status_code == 401
    with Session(api_harness.engine) as session:
        action = session.scalar(select(AuditEvent.action))
    assert action == "browser_session:logout"


def test_operator_sees_only_assigned_tenant(api_harness: ApiHarness) -> None:
    with Session(api_harness.engine) as session:
        visible = Tenant(
            id=new_id("tenant"),
            slug="visible",
            name="Visible",
        )
        hidden = Tenant(
            id=new_id("tenant"),
            slug="hidden",
            name="Hidden",
        )
        operator = Principal(
            id=new_id("principal"),
            issuer="https://identity.test",
            subject="operator",
        )
        session.add_all([visible, hidden, operator])
        session.flush()
        session.add(
            RoleBinding(
                id=new_id("role"),
                principal_id=operator.id,
                tenant_id=visible.id,
                role=OPERATOR,
            )
        )
        session.add(
            BrowserSession(
                id=digest_token("operator-session"),
                principal_id=operator.id,
                csrf_digest=digest_token("operator-csrf"),
                expires_at=utc_now() + timedelta(hours=1),
            )
        )
        session.commit()
        visible_id = visible.id
        hidden_id = hidden.id

    operator_client: TestClient = api_harness.client
    operator_client.cookies.set("proxy_hub_session", "operator-session")
    operator_client.cookies.set("proxy_hub_csrf", "operator-csrf")
    listed = operator_client.get("/v1/admin/tenants")
    denied = operator_client.get(f"/v1/admin/tenants/{hidden_id}")
    create = operator_client.post(
        "/v1/admin/tenants",
        json={"slug": "operator-create", "name": "Operator Create"},
        headers={
            "Origin": "http://testserver",
            "X-CSRF-Token": "operator-csrf",
            "Idempotency-Key": "operator-create",
        },
    )

    assert [tenant["id"] for tenant in listed.json()["items"]] == [visible_id]
    assert denied.status_code == 404
    assert create.status_code == 403
    assert create.json()["error"]["code"] == "platform_role_denied"
