"""Managed researcher and direct Scholar Access Key tests."""

from datetime import timedelta

import pytest
from conftest import ApiHarness
from sqlalchemy import select
from sqlalchemy.orm import Session

from proxy_hub.capabilities import authenticate_credential
from proxy_hub.errors import HubError
from proxy_hub.models import (
    AccessKey,
    AuditEvent,
    Membership,
    Principal,
    Tenant,
    ToolPolicy,
    utc_now,
)
from proxy_hub.quota import QuotaExceeded, reserve_access_key_request
from proxy_hub.security import digest_token


def create_access_tenant(api_harness: ApiHarness) -> str:
    """Create a tenant with a restrictive Scholar tool policy."""
    response = api_harness.client.post(
        "/v1/admin/tenants",
        json={"slug": "access-keys", "name": "Access Keys"},
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "access-keys-tenant",
        },
    )
    assert response.status_code == 201
    tenant_id = str(response.json()["id"])
    with Session(api_harness.engine) as session:
        session.add(
            ToolPolicy(
                tenant_id=tenant_id,
                allowed_tools=["scholar_info", "scholar_search"],
            )
        )
        session.commit()
    return tenant_id


def create_researcher(
    api_harness: ApiHarness,
    tenant_id: str,
) -> tuple[dict[str, object], str]:
    """Create one managed researcher and return its one-time Access Key."""
    response = api_harness.client.post(
        f"/v1/admin/tenants/{tenant_id}/researchers",
        json={
            "display_name": "Research User",
            "email": "research@example.test",
            "label": "Lab laptop",
            "allowed_tools": ["scholar_info"],
            "expires_in_seconds": 3600,
            "request_limit": 2,
            "period_seconds": 3600,
        },
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "researcher-create",
        },
    )
    assert response.status_code == 201
    body = response.json()
    raw_token = body["access_key"]["access_key"]
    assert isinstance(raw_token, str)
    assert raw_token.startswith("sk_scholar_v1_")
    return body, raw_token


def test_researcher_creation_stores_only_digest_and_redacts_replay(
    api_harness: ApiHarness,
) -> None:
    tenant_id = create_access_tenant(api_harness)
    body, raw_token = create_researcher(api_harness, tenant_id)
    researcher = body["researcher"]
    key = body["access_key"]

    replay = api_harness.client.post(
        f"/v1/admin/tenants/{tenant_id}/researchers",
        json={
            "display_name": "Research User",
            "email": "research@example.test",
            "label": "Lab laptop",
            "allowed_tools": ["scholar_info"],
            "expires_in_seconds": 3600,
            "request_limit": 2,
            "period_seconds": 3600,
        },
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "researcher-create",
        },
    )
    assert replay.status_code == 201
    assert replay.headers["Idempotent-Replayed"] == "true"
    assert replay.json()["access_key"] is None

    with Session(api_harness.engine) as session:
        principal = session.get(Principal, researcher["id"])
        access_key = session.get(AccessKey, key["id"])
        assert principal is not None
        assert principal.kind == "managed_researcher"
        assert access_key is not None
        assert access_key.token_digest == digest_token(raw_token)
        assert raw_token not in repr(access_key.__dict__)
        events = session.scalars(select(AuditEvent)).all()
        assert raw_token not in repr([event.details for event in events])

        context = authenticate_credential(session, f"Bearer {raw_token}")
        assert context.access_key_id == access_key.id
        assert context.capability_id is None
        assert context.scopes == ("scholar_info",)

    listed = api_harness.client.get(
        f"/v1/admin/tenants/{tenant_id}/access-keys"
    )
    assert listed.status_code == 200
    listed_key = listed.json()["items"][0]
    assert listed_key["access_key"] is None
    assert listed_key["token_last_four"] == raw_token[-4:]
    assert raw_token not in listed.text


def test_access_key_policy_rotation_revocation_and_researcher_disable(
    api_harness: ApiHarness,
) -> None:
    tenant_id = create_access_tenant(api_harness)
    body, raw_token = create_researcher(api_harness, tenant_id)
    researcher = body["researcher"]
    access_key = body["access_key"]

    denied = api_harness.client.post(
        f"/v1/admin/tenants/{tenant_id}/researchers/{researcher['id']}/access-keys",
        json={
            "label": "Over-scoped",
            "allowed_tools": ["scholar_graph_query"],
            "expires_in_seconds": 3600,
        },
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "over-scoped-key",
        },
    )
    assert denied.status_code == 409
    assert denied.json()["error"]["code"] == "access_key_scope_exceeds_tenant"

    rotated = api_harness.client.post(
        f"/v1/admin/tenants/{tenant_id}/access-keys/{access_key['id']}/rotate",
        json={"label": "Replacement"},
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "rotate-key",
        },
    )
    assert rotated.status_code == 201
    replacement = rotated.json()
    replacement_token = replacement["access_key"]
    assert replacement_token != raw_token
    with Session(api_harness.engine) as session:
        try:
            authenticate_credential(session, f"Bearer {raw_token}")
        except HubError as error:
            assert error.status_code == 401
        else:
            raise AssertionError("rotated Access Key remained valid")
        assert authenticate_credential(
            session,
            f"Bearer {replacement_token}",
        ).access_key_id == replacement["id"]

    disabled = api_harness.client.patch(
        f"/v1/admin/tenants/{tenant_id}/researchers/{researcher['id']}",
        json={"status": "disabled"},
        headers={
            **api_harness.mutation_headers,
            "If-Match": researcher["etag"],
        },
    )
    assert disabled.status_code == 200
    with Session(api_harness.engine) as session:
        try:
            authenticate_credential(session, f"Bearer {replacement_token}")
        except HubError as error:
            assert error.status_code == 403
        else:
            raise AssertionError("disabled researcher Access Key remained valid")

    revoked = api_harness.client.delete(
        f"/v1/admin/tenants/{tenant_id}/access-keys/{replacement['id']}",
        headers={
            **api_harness.mutation_headers,
            "If-Match": replacement["etag"],
        },
    )
    assert revoked.status_code == 204


def test_access_key_request_quota_is_atomic(
    api_harness: ApiHarness,
) -> None:
    tenant_id = create_access_tenant(api_harness)
    body, _raw_token = create_researcher(api_harness, tenant_id)
    access_key_id = str(body["access_key"]["id"])
    now = utc_now()
    with Session(api_harness.engine) as session:
        assert reserve_access_key_request(session, access_key_id, 2, 3600, now)
        assert reserve_access_key_request(session, access_key_id, 2, 3600, now)
        try:
            reserve_access_key_request(session, access_key_id, 2, 3600, now)
        except QuotaExceeded as error:
            assert error.reason == "access_key_request_limit_exceeded"
        else:
            raise AssertionError("Access Key quota did not reject excess request")
        session.commit()

    later = now + timedelta(hours=1)
    with Session(api_harness.engine) as session:
        assert reserve_access_key_request(
            session,
            access_key_id,
            2,
            3600,
            later,
        )


@pytest.mark.parametrize("inactive_resource", ["membership", "tenant", "expiry"])
def test_access_key_fails_closed_when_access_changes(
    api_harness: ApiHarness,
    inactive_resource: str,
) -> None:
    tenant_id = create_access_tenant(api_harness)
    body, raw_token = create_researcher(api_harness, tenant_id)
    researcher_id = str(body["researcher"]["id"])
    access_key_id = str(body["access_key"]["id"])
    with Session(api_harness.engine) as session:
        if inactive_resource == "membership":
            membership = session.scalar(
                select(Membership).where(
                    Membership.tenant_id == tenant_id,
                    Membership.principal_id == researcher_id,
                )
            )
            assert membership is not None
            membership.status = "disabled"
        elif inactive_resource == "tenant":
            tenant = session.get(Tenant, tenant_id)
            assert tenant is not None
            tenant.status = "disabled"
        else:
            access_key = session.get(AccessKey, access_key_id)
            assert access_key is not None
            access_key.expires_at = utc_now() - timedelta(seconds=1)
        session.commit()
        with pytest.raises(HubError) as error:
            authenticate_credential(session, f"Bearer {raw_token}")
        assert error.value.status_code in {401, 403}
