"""One-time enrolment token administration tests."""

from datetime import timedelta

import pytest
from conftest import ApiHarness
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from proxy_hub.models import (
    AuditEvent,
    BrowserSession,
    EnrolmentToken,
    IdempotencyRecord,
    Membership,
    Principal,
    RoleBinding,
    Team,
    Tenant,
    new_id,
    utc_now,
)
from proxy_hub.rbac import TENANT_ADMIN
from proxy_hub.security import digest_token, token_matches


def seed_enrolment_subject(
    api_harness: ApiHarness,
    *,
    tenant_status: str = "active",
    principal_status: str = "active",
    membership_status: str = "active",
    team_status: str | None = None,
) -> tuple[str, str]:
    """Create one tenant and principal with configurable eligibility."""
    tenant_id = new_id("tenant")
    principal_id = new_id("principal")
    with Session(api_harness.engine) as session:
        tenant = Tenant(
            id=tenant_id,
            slug=f"tenant-{tenant_id[-8:]}",
            name="Enrolment Tenant",
            status=tenant_status,
        )
        principal = Principal(
            id=principal_id,
            issuer="https://identity.test",
            subject=f"subject-{principal_id}",
            status=principal_status,
        )
        session.add_all([tenant, principal])
        session.flush()
        team_id = None
        if team_status is not None:
            team = Team(
                id=new_id("team"),
                tenant_id=tenant_id,
                name="Eligibility Team",
                status=team_status,
            )
            session.add(team)
            session.flush()
            team_id = team.id
        session.add(
            Membership(
                id=new_id("membership"),
                principal_id=principal_id,
                tenant_id=tenant_id,
                team_id=team_id,
                status=membership_status,
            )
        )
        session.commit()
    return tenant_id, principal_id


def create_enrolment(
    api_harness: ApiHarness,
    tenant_id: str,
    principal_id: str,
    *,
    key: str = "enrolment-create",
) -> object:
    """Issue one enrolment request through the administration API."""
    return api_harness.client.post(
        f"/v1/admin/tenants/{tenant_id}/enrolments",
        json={
            "principal_id": principal_id,
            "requested_scopes": ["scholar_search", "scholar_info"],
            "expires_in_seconds": 86400,
        },
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": key,
        },
    )


def test_enrolment_secret_is_returned_once_and_never_persisted(
    api_harness: ApiHarness,
) -> None:
    tenant_id, principal_id = seed_enrolment_subject(api_harness)

    created = create_enrolment(api_harness, tenant_id, principal_id)
    replay = create_enrolment(api_harness, tenant_id, principal_id)

    assert created.status_code == 201
    raw_token = created.json()["enrolment_token"]
    assert isinstance(raw_token, str)
    assert replay.status_code == 201
    assert replay.json()["id"] == created.json()["id"]
    assert replay.json()["enrolment_token"] is None
    assert replay.headers["Idempotent-Replayed"] == "true"

    listed = api_harness.client.get(f"/v1/admin/tenants/{tenant_id}/enrolments")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["enrolment_token"] is None
    assert "token_digest" not in listed.text
    assert raw_token not in listed.text

    with Session(api_harness.engine) as session:
        enrolment = session.get(EnrolmentToken, created.json()["id"])
        assert enrolment is not None
        assert token_matches(raw_token, enrolment.token_digest)
        idempotency = session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.operation == f"enrolment:create:{tenant_id}"
            )
        )
        assert idempotency is not None
        assert idempotency.response_body["enrolment_token"] is None
        assert raw_token not in str(idempotency.response_body)
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "enrolment:create")
            )
            == 1
        )


def test_enrolment_key_reuse_conflicts_and_revocation_is_idempotent(
    api_harness: ApiHarness,
) -> None:
    tenant_id, principal_id = seed_enrolment_subject(api_harness)
    created = create_enrolment(api_harness, tenant_id, principal_id)
    conflict = api_harness.client.post(
        f"/v1/admin/tenants/{tenant_id}/enrolments",
        json={
            "principal_id": principal_id,
            "requested_scopes": ["scholar_search"],
            "expires_in_seconds": 86400,
        },
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "enrolment-create",
        },
    )
    enrolment_id = created.json()["id"]
    missing_etag = api_harness.client.delete(
        f"/v1/admin/tenants/{tenant_id}/enrolments/{enrolment_id}",
        headers=api_harness.mutation_headers,
    )
    first_revoke = api_harness.client.delete(
        f"/v1/admin/tenants/{tenant_id}/enrolments/{enrolment_id}",
        headers={
            **api_harness.mutation_headers,
            "If-Match": created.headers["ETag"],
        },
    )
    second_revoke = api_harness.client.delete(
        f"/v1/admin/tenants/{tenant_id}/enrolments/{enrolment_id}",
        headers={
            **api_harness.mutation_headers,
            "If-Match": created.headers["ETag"],
        },
    )

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    assert missing_etag.status_code == 400
    assert missing_etag.json()["error"]["code"] == "if_match_required"
    assert first_revoke.status_code == 204
    assert second_revoke.status_code == 204
    with Session(api_harness.engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "enrolment:revoke")
            )
            == 1
        )


def test_enrolment_rejects_unknown_scope(api_harness: ApiHarness) -> None:
    tenant_id, principal_id = seed_enrolment_subject(api_harness)

    response = api_harness.client.post(
        f"/v1/admin/tenants/{tenant_id}/enrolments",
        json={
            "principal_id": principal_id,
            "requested_scopes": ["scholar_search", "unknown_tool"],
            "expires_in_seconds": 86400,
        },
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "unknown-scope",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


@pytest.mark.parametrize(
    ("tenant_status", "principal_status", "membership_status", "team_status"),
    [
        ("disabled", "active", "active", None),
        ("active", "disabled", "active", None),
        ("active", "active", "disabled", None),
        ("active", "active", "active", "disabled"),
    ],
)
def test_inactive_control_plane_state_blocks_enrolment(
    api_harness: ApiHarness,
    tenant_status: str,
    principal_status: str,
    membership_status: str,
    team_status: str | None,
) -> None:
    tenant_id, principal_id = seed_enrolment_subject(
        api_harness,
        tenant_status=tenant_status,
        principal_status=principal_status,
        membership_status=membership_status,
        team_status=team_status,
    )

    response = create_enrolment(
        api_harness,
        tenant_id,
        principal_id,
        key=f"inactive-{tenant_status}-{principal_status}-"
        f"{membership_status}-{team_status}",
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] in {
        "tenant_inactive",
        "principal_inactive",
        "membership_inactive",
    }


def test_tenant_admin_cannot_enumerate_other_tenant_enrolments(
    api_harness: ApiHarness,
) -> None:
    visible_id, tenant_admin_id = seed_enrolment_subject(api_harness)
    hidden_id, _hidden_principal = seed_enrolment_subject(api_harness)
    with Session(api_harness.engine) as session:
        session.add(
            RoleBinding(
                id=new_id("role"),
                principal_id=tenant_admin_id,
                tenant_id=visible_id,
                role=TENANT_ADMIN,
            )
        )
        session.add(
            BrowserSession(
                id=digest_token("enrolment-admin-session"),
                principal_id=tenant_admin_id,
                csrf_digest=digest_token("enrolment-admin-csrf"),
                expires_at=utc_now() + timedelta(hours=1),
            )
        )
        session.commit()

    api_harness.client.cookies.set(
        "proxy_hub_session",
        "enrolment-admin-session",
    )
    api_harness.client.cookies.set(
        "proxy_hub_csrf",
        "enrolment-admin-csrf",
    )
    visible = api_harness.client.get(f"/v1/admin/tenants/{visible_id}/enrolments")
    hidden = api_harness.client.get(f"/v1/admin/tenants/{hidden_id}/enrolments")

    assert visible.status_code == 200
    assert hidden.status_code == 404
