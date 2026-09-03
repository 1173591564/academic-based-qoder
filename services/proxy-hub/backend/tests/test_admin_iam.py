"""Tenant and platform IAM administration tests."""

from datetime import timedelta

from conftest import ApiHarness
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from proxy_hub.models import (
    AuditEvent,
    BrowserSession,
    Membership,
    Principal,
    RoleBinding,
    new_id,
    utc_now,
)
from proxy_hub.rbac import AUDITOR, OPERATOR, TENANT_ADMIN
from proxy_hub.security import digest_token, resource_etag


def create_tenant(api_harness: ApiHarness, slug: str) -> dict[str, object]:
    """Create a tenant through the public administration API."""
    response = api_harness.client.post(
        "/v1/admin/tenants",
        json={"slug": slug, "name": slug.replace("-", " ").title()},
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": f"tenant-{slug}",
        },
    )
    assert response.status_code == 201
    return response.json()


def add_principal(
    api_harness: ApiHarness,
    subject: str,
    *,
    status: str = "active",
) -> str:
    """Insert an OIDC-derived principal for IAM administration."""
    principal_id = new_id("principal")
    with Session(api_harness.engine) as session:
        session.add(
            Principal(
                id=principal_id,
                issuer="https://identity.test",
                subject=subject,
                email=f"{subject}@example.test",
                status=status,
            )
        )
        session.commit()
    return principal_id


def test_platform_admin_manages_tenant_iam_with_integrity_controls(
    api_harness: ApiHarness,
) -> None:
    tenant_id = str(create_tenant(api_harness, "iam-tenant")["id"])
    principal_id = add_principal(api_harness, "researcher")

    team_headers = {
        **api_harness.mutation_headers,
        "Idempotency-Key": "team-create",
    }
    team = api_harness.client.post(
        f"/v1/admin/tenants/{tenant_id}/teams",
        json={"name": "Research"},
        headers=team_headers,
    )
    team_replay = api_harness.client.post(
        f"/v1/admin/tenants/{tenant_id}/teams",
        json={"name": "Research"},
        headers=team_headers,
    )
    assert team.status_code == 201
    assert team_replay.json() == team.json()
    assert team_replay.headers["Idempotent-Replayed"] == "true"
    team_id = team.json()["id"]
    updated_team = api_harness.client.patch(
        f"/v1/admin/tenants/{tenant_id}/teams/{team_id}",
        json={"name": "Research Operations"},
        headers={
            **api_harness.mutation_headers,
            "If-Match": team.headers["ETag"],
        },
    )
    assert updated_team.status_code == 200
    assert updated_team.json()["name"] == "Research Operations"

    membership_headers = {
        **api_harness.mutation_headers,
        "Idempotency-Key": "membership-create",
    }
    membership = api_harness.client.post(
        f"/v1/admin/tenants/{tenant_id}/memberships",
        json={"principal_id": principal_id, "team_id": team_id},
        headers=membership_headers,
    )
    membership_replay = api_harness.client.post(
        f"/v1/admin/tenants/{tenant_id}/memberships",
        json={"principal_id": principal_id, "team_id": team_id},
        headers=membership_headers,
    )
    assert membership.status_code == 201
    assert membership_replay.json() == membership.json()
    membership_id = membership.json()["id"]

    binding_headers = {
        **api_harness.mutation_headers,
        "Idempotency-Key": "binding-create",
    }
    binding = api_harness.client.post(
        f"/v1/admin/tenants/{tenant_id}/role-bindings",
        json={"principal_id": principal_id, "role": OPERATOR},
        headers=binding_headers,
    )
    binding_replay = api_harness.client.post(
        f"/v1/admin/tenants/{tenant_id}/role-bindings",
        json={"principal_id": principal_id, "role": OPERATOR},
        headers=binding_headers,
    )
    assert binding.status_code == 201
    assert binding_replay.json() == binding.json()

    stale_update = api_harness.client.patch(
        f"/v1/admin/tenants/{tenant_id}/memberships/{membership_id}",
        json={"status": "disabled"},
        headers={**api_harness.mutation_headers, "If-Match": '"stale"'},
    )
    assert stale_update.status_code == 412

    disabled = api_harness.client.delete(
        f"/v1/admin/tenants/{tenant_id}/memberships/{membership_id}",
        headers={
            **api_harness.mutation_headers,
            "If-Match": membership.headers["ETag"],
        },
    )
    revoked = api_harness.client.delete(
        f"/v1/admin/tenants/{tenant_id}/role-bindings/{binding.json()['id']}",
        headers={
            **api_harness.mutation_headers,
            "If-Match": binding.headers["ETag"],
        },
    )
    assert disabled.status_code == 204
    assert revoked.status_code == 204

    with Session(api_harness.engine) as session:
        stored_membership = session.get(Membership, membership_id)
        stored_binding = session.get(RoleBinding, binding.json()["id"])
        assert stored_membership is not None
        assert stored_membership.status == "disabled"
        assert stored_binding is not None
        assert stored_binding.revoked_at is not None

    memberships = api_harness.client.get(f"/v1/admin/tenants/{tenant_id}/memberships")
    disabled_membership = next(
        item for item in memberships.json()["items"] if item["id"] == membership_id
    )
    reenabled = api_harness.client.patch(
        f"/v1/admin/tenants/{tenant_id}/memberships/{membership_id}",
        json={"status": "active"},
        headers={
            **api_harness.mutation_headers,
            "If-Match": disabled_membership["etag"],
        },
    )
    restored_binding = api_harness.client.post(
        f"/v1/admin/tenants/{tenant_id}/role-bindings",
        json={"principal_id": principal_id, "role": OPERATOR},
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "binding-restore",
        },
    )
    assert reenabled.status_code == 200
    assert restored_binding.status_code == 201
    assert restored_binding.json()["id"] == binding.json()["id"]
    assert restored_binding.json()["version"] == 3
    with Session(api_harness.engine) as session:
        stored_binding = session.get(RoleBinding, binding.json()["id"])
        assert stored_binding is not None
        assert stored_binding.revoked_at is None
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 9


def test_tenant_admin_scope_depends_on_active_membership(
    api_harness: ApiHarness,
) -> None:
    visible_id = str(create_tenant(api_harness, "visible-iam")["id"])
    hidden_id = str(create_tenant(api_harness, "hidden-iam")["id"])
    tenant_admin_id = add_principal(api_harness, "tenant-admin")
    membership_id = new_id("membership")
    with Session(api_harness.engine) as session:
        session.add(
            Membership(
                id=membership_id,
                principal_id=tenant_admin_id,
                tenant_id=visible_id,
            )
        )
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
                id=digest_token("tenant-admin-session"),
                principal_id=tenant_admin_id,
                csrf_digest=digest_token("tenant-admin-csrf"),
                expires_at=utc_now() + timedelta(hours=1),
            )
        )
        session.commit()

    api_harness.client.cookies.set(
        "proxy_hub_session",
        "tenant-admin-session",
    )
    api_harness.client.cookies.set("proxy_hub_csrf", "tenant-admin-csrf")
    allowed = api_harness.client.get(f"/v1/admin/tenants/{visible_id}/teams")
    hidden = api_harness.client.get(f"/v1/admin/tenants/{hidden_id}/teams")
    assert allowed.status_code == 200
    assert hidden.status_code == 404

    with Session(api_harness.engine) as session:
        membership = session.get(Membership, membership_id)
        assert membership is not None
        membership.status = "disabled"
        session.commit()

    no_longer_assigned = api_harness.client.get(f"/v1/admin/tenants/{visible_id}/teams")
    assert no_longer_assigned.status_code == 404


def test_platform_principal_and_role_controls(
    api_harness: ApiHarness,
) -> None:
    principal_id = add_principal(api_harness, "platform-auditor")
    principals = api_harness.client.get("/v1/admin/principals")
    principal = next(
        item for item in principals.json()["items"] if item["id"] == principal_id
    )

    invalid_role = api_harness.client.post(
        "/v1/admin/platform-role-bindings",
        json={"principal_id": principal_id, "role": TENANT_ADMIN},
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "invalid-platform-role",
        },
    )
    role = api_harness.client.post(
        "/v1/admin/platform-role-bindings",
        json={"principal_id": principal_id, "role": AUDITOR},
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "platform-auditor-role",
        },
    )
    role_revoke = api_harness.client.delete(
        f"/v1/admin/platform-role-bindings/{role.json()['id']}",
        headers={
            **api_harness.mutation_headers,
            "If-Match": role.headers["ETag"],
        },
    )
    own_binding = next(
        binding
        for binding in api_harness.client.get(
            "/v1/admin/platform-role-bindings"
        ).json()["items"]
        if binding["principal_id"] == api_harness.principal_id
    )
    self_revoke = api_harness.client.delete(
        f"/v1/admin/platform-role-bindings/{own_binding['id']}",
        headers={
            **api_harness.mutation_headers,
            "If-Match": own_binding["etag"],
        },
    )
    disabled = api_harness.client.patch(
        f"/v1/admin/principals/{principal_id}",
        json={"status": "disabled"},
        headers={
            **api_harness.mutation_headers,
            "If-Match": principal["etag"],
        },
    )
    self_disable = api_harness.client.patch(
        f"/v1/admin/principals/{api_harness.principal_id}",
        json={"status": "disabled"},
        headers={
            **api_harness.mutation_headers,
            "If-Match": resource_etag(
                "principal",
                api_harness.principal_id,
                1,
            ),
        },
    )

    assert invalid_role.status_code == 400
    assert invalid_role.json()["error"]["code"] == "role_unknown"
    assert role.status_code == 201
    assert role_revoke.status_code == 204
    assert self_revoke.status_code == 409
    assert self_revoke.json()["error"]["code"] == "platform_role_self_revoke_denied"
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"
    assert self_disable.status_code == 409
    assert self_disable.json()["error"]["code"] == "principal_self_disable_denied"
