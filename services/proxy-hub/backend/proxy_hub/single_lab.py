"""Single-lab control-plane bootstrap and lookup."""

from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

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
