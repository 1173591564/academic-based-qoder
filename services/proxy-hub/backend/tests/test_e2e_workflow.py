"""Complete control-plane to Scholar MCP workflow regression."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from proxy_hub.models import AuditEvent, Principal, new_id, utc_now
from tests.conftest import ApiHarness


def test_tenant_onboarding_gateway_audit_and_usage_workflow(
    api_harness: ApiHarness,
) -> None:
    """Exercise the production golden path without crossing data-plane boundaries."""
    tenant = api_harness.client.post(
        "/v1/admin/tenants",
        json={"slug": "e2e-tenant", "name": "E2E Tenant"},
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "e2e-tenant",
        },
    )
    assert tenant.status_code == 201
    tenant_id = tenant.json()["id"]

    principal_id = new_id("principal")
    with Session(api_harness.engine) as session:
        session.add(
            Principal(
                id=principal_id,
                issuer="https://identity.test",
                subject="e2e-researcher",
            )
        )
        session.commit()

    membership = api_harness.client.post(
        f"/v1/admin/tenants/{tenant_id}/memberships",
        json={"principal_id": principal_id, "team_id": None},
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "e2e-membership",
        },
    )
    assert membership.status_code == 201
    tool_policy = api_harness.client.put(
        f"/v1/admin/tenants/{tenant_id}/tool-policy",
        json={"allowed_tools": ["scholar_info"]},
        headers={**api_harness.mutation_headers, "If-Match": "*"},
    )
    assert tool_policy.status_code == 201
    quota_policy = api_harness.client.put(
        f"/v1/admin/tenants/{tenant_id}/quota-policy",
        json={
            "quota_class": "e2e",
            "request_limit": 10,
            "period_seconds": 3600,
            "concurrency_limit": 2,
            "enforcement_enabled": True,
        },
        headers={**api_harness.mutation_headers, "If-Match": "*"},
    )
    assert quota_policy.status_code == 201

    backend = api_harness.client.post(
        "/v1/admin/backends",
        json={
            "name": "E2E Scholar",
            "base_url": "http://scholar.test/mcp",
            "corpus_version": "corpus-v1",
            "credential_ref": "env:SCHOLAR_TEST_TOKEN",
            "credential_version": "e2e-v1",
        },
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "e2e-backend",
        },
    )
    assert backend.status_code == 201
    backend_id = backend.json()["id"]
    probe = api_harness.client.post(
        f"/v1/admin/backends/{backend_id}:probe",
        headers=api_harness.mutation_headers,
    )
    assert probe.status_code == 200
    activated = api_harness.client.patch(
        f"/v1/admin/backends/{backend_id}",
        json={"status": "active"},
        headers={
            **api_harness.mutation_headers,
            "If-Match": probe.headers["etag"],
        },
    )
    assert activated.status_code == 200
    route = api_harness.client.put(
        f"/v1/admin/tenants/{tenant_id}/backend-route",
        json={
            "backend_id": backend_id,
            "corpus_version": "corpus-v1",
            "status": "active",
        },
        headers={**api_harness.mutation_headers, "If-Match": "*"},
    )
    assert route.status_code == 201

    enrolment = api_harness.client.post(
        f"/v1/admin/tenants/{tenant_id}/enrolments",
        json={
            "principal_id": principal_id,
            "requested_scopes": ["scholar_info"],
            "expires_in_seconds": 3600,
        },
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "e2e-enrolment",
        },
    )
    assert enrolment.status_code == 201
    issued = api_harness.client.post(
        "/v1/session",
        json={"enrolment_token": enrolment.json()["enrolment_token"]},
    )
    assert issued.status_code == 201
    raw_capability = issued.json()["session_token"]

    forwarded = api_harness.client.post(
        "/v1/mcp/scholar",
        headers={
            "Authorization": f"Bearer {raw_capability}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "scholar_info", "arguments": {}},
        },
    )
    assert forwarded.status_code == 200

    now = utc_now()
    query = {
        "from": (now - timedelta(minutes=5)).isoformat(),
        "to": (now + timedelta(minutes=1)).isoformat(),
    }
    audit = api_harness.client.get(
        f"/v1/admin/tenants/{tenant_id}/audit-events",
        params=query,
    )
    usage = api_harness.client.get(
        f"/v1/admin/tenants/{tenant_id}/usage",
        params=query,
    )
    assert audit.status_code == 200
    assert usage.status_code == 200
    assert any(
        item["action"] == "mcp:tool" and item["outcome"] == "forwarded"
        for item in audit.json()["items"]
    )
    assert usage.json()["items"][0]["requests"]["total"] == 1
    with Session(api_harness.engine) as session:
        gateway_audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.action == "mcp:tool",
            )
        )
        assert gateway_audit is not None
        assert raw_capability not in str(gateway_audit.details)
