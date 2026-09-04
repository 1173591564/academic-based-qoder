"""Single-lab control-plane bootstrap and lookup."""

import logging
from datetime import timedelta
from uuid import uuid4

import anyio
import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from proxy_hub.backend_probe import probe_scholar_backend
from proxy_hub.config import Settings
from proxy_hub.database import Database
from proxy_hub.models import (
    AuditEvent,
    ScholarBackend,
    Tenant,
    TenantRoute,
    ToolPolicy,
    new_id,
    utc_now,
)
from proxy_hub.policy import SCHOLAR_TOOL_CATALOG
from proxy_hub.secrets import SecretResolver

LOGGER = logging.getLogger(__name__)


def resolve_single_lab_tenant(session: Session, settings: Settings) -> Tenant:
    """Return the configured single tenant or initialize an empty deployment."""
    if settings.single_lab_tenant_id is not None:
        tenant = session.get(Tenant, settings.single_lab_tenant_id)
        if tenant is None:
            raise RuntimeError("configured single-lab tenant does not exist")
    else:
        tenant = session.scalar(
            select(Tenant).where(Tenant.slug == settings.single_lab_tenant_slug)
        )
        if tenant is None:
            tenants = list(
                session.scalars(select(Tenant).order_by(Tenant.id).limit(2)).all()
            )
            if len(tenants) == 1:
                tenant = tenants[0]
            elif len(tenants) > 1:
                raise RuntimeError(
                    "single-lab mode requires PROXY_HUB_SINGLE_LAB_TENANT_ID"
                )
            else:
                tenant = Tenant(
                    id=new_id("tenant"),
                    slug=settings.single_lab_tenant_slug,
                    name=settings.single_lab_tenant_name,
                )
                session.add(tenant)
                session.flush()
    tools = sorted(SCHOLAR_TOOL_CATALOG)
    policy = session.get(ToolPolicy, tenant.id)
    if policy is None:
        session.add(ToolPolicy(tenant_id=tenant.id, allowed_tools=tools))
    elif policy.allowed_tools != tools:
        policy.allowed_tools = tools
        policy.version += 1
    return tenant


def _configure_backend(
    session: Session,
    settings: Settings,
    tenant: Tenant,
) -> None:
    if settings.single_lab_backend_url is None:
        return
    if (
        settings.single_lab_corpus_version is None
        or settings.single_lab_backend_credential_ref is None
    ):
        raise RuntimeError("single-lab backend configuration is incomplete")
    backend = session.scalar(
        select(ScholarBackend).where(
            ScholarBackend.name == settings.single_lab_backend_name
        )
    )
    if backend is None:
        backend = ScholarBackend(
            id=new_id("backend"),
            name=settings.single_lab_backend_name,
            base_url=settings.single_lab_backend_url,
            corpus_version=settings.single_lab_corpus_version,
            credential_ref=settings.single_lab_backend_credential_ref,
            status="disabled",
            last_probe_ready=False,
            last_probe_reason="not_probed",
        )
        session.add(backend)
        session.flush()
    route = session.get(TenantRoute, tenant.id)
    if route is None:
        session.add(
            TenantRoute(
                tenant_id=tenant.id,
                backend_id=backend.id,
                corpus_version=backend.corpus_version,
                status="disabled",
            )
        )


def bootstrap_single_lab(database: Database, settings: Settings) -> None:
    """Initialize single-lab defaults and enforce the audit retention window."""
    with database.sessions.begin() as session:
        tenant = resolve_single_lab_tenant(session, settings)
        _configure_backend(session, settings, tenant)
        cutoff = utc_now() - timedelta(days=settings.audit_retention_days)
        session.execute(delete(AuditEvent).where(AuditEvent.occurred_at < cutoff))


async def refresh_single_lab_backend(
    database: Database,
    settings: Settings,
    http_client: httpx.AsyncClient,
    secret_resolver: SecretResolver,
) -> None:
    """Refresh the configured Scholar Backend readiness observation."""
    with database.sessions() as session:
        tenant = (
            session.get(Tenant, settings.single_lab_tenant_id)
            if settings.single_lab_tenant_id is not None
            else session.scalar(
                select(Tenant).where(Tenant.slug == settings.single_lab_tenant_slug)
            )
        )
        route = session.get(TenantRoute, tenant.id) if tenant is not None else None
        backend = (
            session.get(ScholarBackend, route.backend_id) if route is not None else None
        )
        if route is None or backend is None:
            return
        tenant_id = route.tenant_id
        backend_id = backend.id
        configuration = (
            backend.base_url,
            backend.credential_ref,
            backend.corpus_version,
        )

    result = await probe_scholar_backend(
        http_client,
        secret_resolver,
        base_url=configuration[0],
        credential_ref=configuration[1],
        expected_corpus_version=configuration[2],
        production=settings.environment == "production",
        request_id=f"probe_{uuid4().hex}",
        maximum_bytes=settings.backend_probe_max_bytes,
    )

    with database.sessions.begin() as session:
        backend = session.get(ScholarBackend, backend_id)
        route = session.get(TenantRoute, tenant_id)
        if (
            backend is None
            or route is None
            or route.backend_id != backend.id
            or (
                backend.base_url,
                backend.credential_ref,
                backend.corpus_version,
            )
            != configuration
        ):
            return
        backend.last_probe_at = utc_now()
        backend.last_probe_ready = result.ready
        backend.last_probe_reason = result.reason
        backend.capacity = result.capacity if result.ready else {}
        backend.status = "active" if result.ready else "disabled"
        backend.version += 1
        route.status = "active" if result.ready else "disabled"
        route.corpus_version = backend.corpus_version
        route.version += 1


async def maintain_single_lab_backend(
    database: Database,
    settings: Settings,
    http_client: httpx.AsyncClient,
    secret_resolver: SecretResolver,
) -> None:
    """Keep the single Scholar Backend probe fresh while Proxy Hub is running."""
    interval_seconds = max(1.0, settings.backend_probe_max_age_seconds / 2)
    while True:
        try:
            await refresh_single_lab_backend(
                database,
                settings,
                http_client,
                secret_resolver,
            )
        except Exception:
            LOGGER.exception("single-lab Scholar Backend refresh failed")
        await anyio.sleep(interval_seconds)
