"""Capability revocation, admin limiting, and audit failure tests."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from proxy_hub.models import (
    AuditEvent,
    DshCapability,
    Membership,
    Principal,
    Tenant,
    new_id,
    utc_now,
)
from proxy_hub.security import digest_token, resource_etag
from tests.conftest import ApiHarness


def seed_capability(api_harness: ApiHarness) -> tuple[str, str, str]:
    """Create one tenant capability managed by the test administrator."""
    tenant_id = new_id("tenant")
    principal_id = new_id("principal")
    capability_id = new_id("cap")
    raw_capability = "test-revocable-capability"
    with Session(api_harness.engine) as session:
        session.add(Tenant(id=tenant_id, slug=tenant_id, name="Tenant"))
        session.add(
            Principal(
                id=principal_id,
                issuer="https://identity.test",
                subject=principal_id,
            )
        )
        session.add(
            Membership(
                id=new_id("membership"),
                tenant_id=tenant_id,
                principal_id=principal_id,
            )
        )
        session.add(
            DshCapability(
                id=capability_id,
                token_digest=digest_token(raw_capability),
                principal_id=principal_id,
                tenant_id=tenant_id,
                scopes=["scholar_info"],
                expires_at=utc_now() + timedelta(hours=1),
            )
        )
        session.commit()
    return tenant_id, capability_id, raw_capability


def test_administrator_lists_and_revokes_capability(
    api_harness: ApiHarness,
) -> None:
    tenant_id, capability_id, raw_capability = seed_capability(api_harness)

    listed = api_harness.client.get(f"/v1/admin/tenants/{tenant_id}/capabilities")
    item = listed.json()["items"][0]
    revoked = api_harness.client.delete(
        f"/v1/admin/tenants/{tenant_id}/capabilities/{capability_id}",
        headers={
            **api_harness.mutation_headers,
            "If-Match": item["etag"],
        },
    )
    denied = api_harness.client.post(
        "/v1/mcp/scholar",
        headers={"Authorization": f"Bearer {raw_capability}"},
        content=b'{"jsonrpc":"2.0","id":1,"method":"ping"}',
    )

    assert listed.status_code == 200
    assert "token_digest" not in item
    assert revoked.status_code == 204
    assert denied.status_code == 401
    with Session(api_harness.engine) as session:
        capability = session.get(DshCapability, capability_id)
        assert capability is not None
        assert capability.revoked_at is not None
        assert capability.version == 2
        audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "capability:revoke",
                AuditEvent.resource_id == capability_id,
            )
        )
        assert audit is not None
        assert raw_capability not in str(audit.details)


def test_capability_revocation_rolls_back_when_audit_fails(
    api_harness: ApiHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id, capability_id, _raw_capability = seed_capability(api_harness)

    def fail_audit(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(
        "proxy_hub.admin_capabilities.append_mutation_audit",
        fail_audit,
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        api_harness.client.delete(
            f"/v1/admin/tenants/{tenant_id}/capabilities/{capability_id}",
            headers={
                **api_harness.mutation_headers,
                "If-Match": resource_etag("capability", capability_id, 1),
            },
        )
    with Session(api_harness.engine) as session:
        capability = session.get(DshCapability, capability_id)
        assert capability is not None
        assert capability.revoked_at is None
        assert capability.version == 1


def test_admin_rate_limit_is_audited_and_returns_retry_after(
    api_harness: ApiHarness,
) -> None:
    responses = [api_harness.client.get("/v1/admin/overview") for _ in range(121)]

    assert all(response.status_code == 200 for response in responses[:120])
    assert responses[0].headers["ratelimit-limit"] == "120"
    assert responses[-1].status_code == 429
    assert int(responses[-1].headers["retry-after"]) >= 1
    with Session(api_harness.engine) as session:
        rejected = session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "admin:rate_limit")
        )
        assert rejected == 1
