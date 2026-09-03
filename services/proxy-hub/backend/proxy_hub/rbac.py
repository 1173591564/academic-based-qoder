"""Role and tenant-scope authorization rules."""

from dataclasses import dataclass

from proxy_hub.errors import HubError

PLATFORM_ADMIN = "platform_admin"
TENANT_ADMIN = "tenant_admin"
OPERATOR = "operator"
AUDITOR = "auditor"
ROLE_NAMES = frozenset({PLATFORM_ADMIN, TENANT_ADMIN, OPERATOR, AUDITOR})
TENANT_SCOPED_ROLES = frozenset({TENANT_ADMIN, OPERATOR, AUDITOR})


@dataclass(frozen=True)
class RoleGrant:
    """One effective role assignment."""

    role: str
    tenant_id: str | None


@dataclass(frozen=True)
class AdminContext:
    """Authenticated principal and effective role grants."""

    principal_id: str
    session_id: str
    csrf_digest: str
    grants: tuple[RoleGrant, ...]

    @property
    def is_platform_admin(self) -> bool:
        return any(
            grant.role == PLATFORM_ADMIN and grant.tenant_id is None
            for grant in self.grants
        )

    @property
    def tenant_ids(self) -> frozenset[str]:
        return frozenset(
            grant.tenant_id
            for grant in self.grants
            if grant.role in TENANT_SCOPED_ROLES and grant.tenant_id is not None
        )


def require_platform_admin(context: AdminContext) -> None:
    """Require the global platform administrator role."""
    if not context.is_platform_admin:
        raise HubError(
            403,
            "platform_role_denied",
            "This operation requires the platform administrator role.",
        )


def can_read_tenant(context: AdminContext, tenant_id: str) -> bool:
    """Return whether a principal can see a tenant."""
    return context.is_platform_admin or tenant_id in context.tenant_ids


def require_tenant_read(context: AdminContext, tenant_id: str) -> None:
    """Hide tenants outside the caller's visible scope."""
    if not can_read_tenant(context, tenant_id):
        raise HubError(
            404,
            "tenant_not_found",
            "The requested tenant is not available.",
        )


def can_mutate_tenant(context: AdminContext, tenant_id: str) -> bool:
    """Return whether a principal can administer one tenant."""
    return context.is_platform_admin or any(
        grant.role == TENANT_ADMIN and grant.tenant_id == tenant_id
        for grant in context.grants
    )


def require_tenant_mutation(context: AdminContext, tenant_id: str) -> None:
    """Require tenant administration while hiding unassigned tenants."""
    require_tenant_read(context, tenant_id)
    if not can_mutate_tenant(context, tenant_id):
        raise HubError(
            403,
            "tenant_role_denied",
            "This operation requires tenant administration.",
        )


def capability_names(context: AdminContext) -> list[str]:
    """Return frontend hints derived from effective grants."""
    capabilities = {"overview:read", "tenant:read"}
    if context.is_platform_admin:
        capabilities.update(
            {
                "tenant:create",
                "tenant:update",
                "principal:manage",
                "backend:manage",
                "settings:manage",
                "audit:read",
            }
        )
    for grant in context.grants:
        if grant.tenant_id is None:
            continue
        if grant.role == TENANT_ADMIN:
            capabilities.update(
                {
                    "membership:manage",
                    "policy:manage",
                    "quota:manage",
                    "route:manage",
                }
            )
        elif grant.role == OPERATOR:
            capabilities.add("backend:probe")
        elif grant.role == AUDITOR:
            capabilities.add("audit:read")
    return sorted(capabilities)
