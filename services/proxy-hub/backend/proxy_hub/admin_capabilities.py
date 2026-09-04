"""Tenant DSH capability administration."""

from collections.abc import Generator

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import Response
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from proxy_hub.auth import AuthComponents
from proxy_hub.database import Database, session_scope
from proxy_hub.errors import HubError
from proxy_hub.models import DshCapability, McpSessionAffinity, Tenant, utc_now
from proxy_hub.mutations import (
    append_mutation_audit,
    require_current_etag,
    require_version_update,
)
from proxy_hub.rbac import AdminContext, require_tenant_mutation, require_tenant_read
from proxy_hub.security import digest_token, resource_etag


def capability_body(capability: DshCapability) -> dict[str, object]:
    """Serialize revocable capability metadata without its credential digest."""
    return {
        "id": capability.id,
        "principal_id": capability.principal_id,
        "tenant_id": capability.tenant_id,
        "scopes": capability.scopes,
        "session_label": capability.session_label,
        "expires_at": capability.expires_at.isoformat(),
        "revoked_at": (
            capability.revoked_at.isoformat()
            if capability.revoked_at is not None
            else None
        ),
        "last_used_at": (
            capability.last_used_at.isoformat()
            if capability.last_used_at is not None
            else None
        ),
        "created_at": capability.created_at.isoformat(),
        "etag": resource_etag(
            "capability",
            capability.id,
            capability.revoked_at or capability.created_at,
        ),
    }


def build_capability_router(
    database: Database,
    auth: AuthComponents,
) -> APIRouter:
    """Create tenant capability inspection and revocation routes."""
    router = APIRouter()

    def get_session() -> Generator[Session, None, None]:
        yield from session_scope(database)

    def require_tenant(
        session: Session,
        context: AdminContext,
        tenant_id: str,
    ) -> Tenant:
        require_tenant_read(context, tenant_id)
        tenant = session.get(Tenant, tenant_id)
        if tenant is None:
            raise HubError(
                404,
                "tenant_not_found",
                "The requested tenant is not available.",
            )
        return tenant

    @router.get("/tenants/{tenant_id}/capabilities")
    def list_capabilities(
        tenant_id: str,
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        require_tenant(session, context, tenant_id)
        capabilities = session.scalars(
            select(DshCapability)
            .where(DshCapability.tenant_id == tenant_id)
            .order_by(DshCapability.created_at.desc(), DshCapability.id)
        ).all()
        return {"items": [capability_body(capability) for capability in capabilities]}

    @router.delete(
        "/tenants/{tenant_id}/capabilities/{capability_id}",
        status_code=204,
    )
    def revoke_capability(
        tenant_id: str,
        capability_id: str,
        request: Request,
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
        if_match: str | None = Header(default=None, alias="If-Match"),
    ) -> Response:
        require_tenant(session, context, tenant_id)
        require_tenant_mutation(context, tenant_id)
        capability = session.scalar(
            select(DshCapability).where(
                DshCapability.id == capability_id,
                DshCapability.tenant_id == tenant_id,
            )
        )
        if capability is None:
            raise HubError(
                404,
                "capability_not_found",
                "The requested capability is not available.",
            )
        require_current_etag(
            "capability",
            capability.id,
            capability.revoked_at or capability.created_at,
            if_match,
        )
        if capability.revoked_at is not None:
            return Response(status_code=204)
        revoked_at = utc_now()
        updated_id = session.scalar(
            update(DshCapability)
            .where(
                DshCapability.id == capability.id,
                DshCapability.revoked_at.is_(None),
            )
            .values(
                revoked_at=revoked_at,
            )
            .returning(DshCapability.id)
        )
        require_version_update(updated_id)
        session.execute(
            delete(McpSessionAffinity).where(
                McpSessionAffinity.capability_id == capability.id
            )
        )
        append_mutation_audit(
            session,
            request,
            context,
            action="capability:revoke",
            resource_type="dsh_capability",
            resource_id=capability.id,
            tenant_id=tenant_id,
            digest=digest_token(capability.id),
            details={"reason": "administrator_revoked"},
        )
        session.commit()
        return Response(status_code=204)

    return router
