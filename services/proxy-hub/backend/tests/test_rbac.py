"""Role and tenant-scope authorization tests."""

from proxy_hub.rbac import (
    PLATFORM_ADMIN,
    TENANT_ADMIN,
    AdminContext,
    RoleGrant,
    capability_names,
)


def test_unknown_and_malformed_roles_do_not_grant_tenant_scope() -> None:
    context = AdminContext(
        principal_id="principal_test",
        session_id="session_test",
        csrf_digest="csrf_test",
        grants=(
            RoleGrant(role="unknown", tenant_id="tenant_unknown"),
            RoleGrant(role=PLATFORM_ADMIN, tenant_id="tenant_scoped"),
            RoleGrant(role=TENANT_ADMIN, tenant_id=None),
        ),
    )

    assert context.tenant_ids == frozenset()
    assert "membership:manage" not in capability_names(context)
