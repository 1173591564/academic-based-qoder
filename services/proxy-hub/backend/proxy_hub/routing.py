"""Fail-closed tenant route and MCP affinity resolution."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from proxy_hub.models import (
    McpSessionAffinity,
    ScholarBackend,
    Tenant,
    TenantRoute,
)
from proxy_hub.policy import backend_allows_workspace_writes


class RouteResolutionError(RuntimeError):
    """A tenant has no eligible Scholar backend."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class RouteSelection:
    """One eligible backend selected for a tenant request."""

    tenant_id: str
    backend_id: str
    base_url: str
    corpus_version: str
    credential_ref: str
    workspace_writes_allowed: bool
    from_affinity: bool


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _select_backend(
    session: Session,
    tenant_id: str,
    backend_id: str,
    corpus_version: str,
    at: datetime,
    max_probe_age: timedelta,
    *,
    from_affinity: bool,
) -> RouteSelection:
    backend = session.get(ScholarBackend, backend_id)
    if backend is None or backend.status != "active":
        raise RouteResolutionError("backend_inactive")
    if backend.last_probe_ready is not True:
        raise RouteResolutionError("backend_unready")
    if (
        backend.last_probe_at is None
        or _as_utc(backend.last_probe_at) <= _as_utc(at) - max_probe_age
    ):
        raise RouteResolutionError("backend_probe_stale")
    if backend.corpus_version != corpus_version:
        raise RouteResolutionError("corpus_version_mismatch")
    return RouteSelection(
        tenant_id=tenant_id,
        backend_id=backend.id,
        base_url=backend.base_url,
        corpus_version=backend.corpus_version,
        credential_ref=backend.credential_ref,
        workspace_writes_allowed=backend_allows_workspace_writes(backend.capacity),
        from_affinity=from_affinity,
    )


def resolve_route(
    session: Session,
    tenant_id: str,
    credential_id: str,
    at: datetime,
    max_probe_age: timedelta,
    *,
    credential_kind: str = "capability",
    mcp_session_digest: str | None = None,
) -> RouteSelection:
    """Resolve an explicit active route or a valid existing affinity."""
    if max_probe_age <= timedelta(0):
        raise ValueError("maximum probe age must be positive")
    tenant = session.get(Tenant, tenant_id)
    if tenant is None or tenant.status != "active":
        raise RouteResolutionError("tenant_inactive")
    route = session.get(TenantRoute, tenant_id)
    if route is None or route.status != "active":
        raise RouteResolutionError("route_missing")

    if mcp_session_digest is not None:
        affinity = session.get(McpSessionAffinity, mcp_session_digest)
        if affinity is None or _as_utc(affinity.expires_at) <= _as_utc(at):
            raise RouteResolutionError("session_affinity_missing")
        affinity_credential_id = (
            affinity.capability_id
            if credential_kind == "capability"
            else affinity.access_key_id
        )
        if (
            credential_kind not in {"capability", "access_key"}
            or affinity.tenant_id != tenant_id
            or affinity_credential_id != credential_id
        ):
            raise RouteResolutionError("session_affinity_mismatch")
        backend = session.get(ScholarBackend, affinity.backend_id)
        if backend is None:
            raise RouteResolutionError("backend_missing")
        return _select_backend(
            session,
            tenant_id,
            affinity.backend_id,
            affinity.corpus_version,
            at,
            max_probe_age,
            from_affinity=True,
        )

    return _select_backend(
        session,
        tenant_id,
        route.backend_id,
        route.corpus_version,
        at,
        max_probe_age,
        from_affinity=False,
    )
