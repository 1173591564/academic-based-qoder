"""Initial browser-session administration API."""

from collections.abc import Generator

import httpx
from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from proxy_hub.admin_backends import build_backend_router
from proxy_hub.admin_capabilities import build_capability_router
from proxy_hub.admin_iam import build_iam_router
from proxy_hub.admin_observability import build_observability_router
from proxy_hub.admin_policies import build_policy_router
from proxy_hub.auth import AuthComponents
from proxy_hub.config import Settings
from proxy_hub.database import Database, session_scope
from proxy_hub.enrolment import build_enrolment_router
from proxy_hub.errors import HubError
from proxy_hub.models import Principal, Tenant, new_id, utc_now
from proxy_hub.mutations import (
    append_mutation_audit,
    find_idempotency_record,
    idempotency_response,
    request_digest,
    require_current_etag,
    require_idempotency_key,
    store_idempotency_record,
)
from proxy_hub.rbac import (
    AdminContext,
    can_read_tenant,
    capability_names,
    require_platform_admin,
    require_tenant_read,
)
from proxy_hub.secrets import SecretResolver
from proxy_hub.security import resource_etag


class TenantCreate(BaseModel):
    """Tenant creation input."""

    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")
    name: str = Field(min_length=1, max_length=200)


class TenantPatch(BaseModel):
    """Mutable tenant fields."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")

    @model_validator(mode="after")
    def require_change(self) -> "TenantPatch":
        if self.name is None and self.status is None:
            raise ValueError("at least one mutable field is required")
        return self


def tenant_body(tenant: Tenant) -> dict[str, object]:
    """Serialize a tenant without exposing persistence internals."""
    return {
        "id": tenant.id,
        "slug": tenant.slug,
        "name": tenant.name,
        "status": tenant.status,
        "version": tenant.version,
        "created_at": tenant.created_at.isoformat(),
        "updated_at": tenant.updated_at.isoformat(),
    }


def build_admin_router(
    database: Database,
    auth: AuthComponents,
    settings: Settings,
    http_client: httpx.AsyncClient,
    secret_resolver: SecretResolver,
) -> APIRouter:
    """Build administration routes bound to application resources."""
    router = APIRouter(prefix="/v1/admin", tags=["administration"])
    router.include_router(build_iam_router(database, auth))
    router.include_router(build_enrolment_router(database, auth))
    router.include_router(build_capability_router(database, auth))
    router.include_router(
        build_backend_router(
            database,
            auth,
            settings,
            http_client,
            secret_resolver,
        )
    )
    router.include_router(build_policy_router(database, auth, settings))
    router.include_router(build_observability_router(database, auth))

    def get_session() -> Generator[Session, None, None]:
        yield from session_scope(database)

    @router.get("/me")
    def me(
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        principal = session.get(Principal, context.principal_id)
        if principal is None:
            raise HubError(401, "browser_session_expired", "The session is invalid.")
        return {
            "principal": {
                "id": principal.id,
                "email": principal.email,
                "display_name": principal.display_name,
            },
            "roles": [
                {"role": grant.role, "tenant_id": grant.tenant_id}
                for grant in context.grants
            ],
            "tenant_ids": sorted(context.tenant_ids),
            "capabilities": capability_names(context),
        }

    @router.get("/overview")
    def overview(
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        query = select(func.count()).select_from(Tenant)
        tenant_count = 0
        if not context.is_platform_admin:
            if context.tenant_ids:
                tenant_count = (
                    session.scalar(query.where(Tenant.id.in_(context.tenant_ids))) or 0
                )
        else:
            tenant_count = session.scalar(query) or 0
        return {
            "observed_at": utc_now().isoformat(),
            "control_plane": {"status": "ready"},
            "tenants": {"visible": tenant_count or 0},
            "recent_failures": [],
        }

    @router.get("/tenants")
    def list_tenants(
        cursor: str | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        query = select(Tenant).order_by(Tenant.id).limit(limit + 1)
        if cursor:
            query = query.where(Tenant.id > cursor)
        if not context.is_platform_admin:
            if not context.tenant_ids:
                return {"items": [], "next_cursor": None}
            query = query.where(Tenant.id.in_(context.tenant_ids))
        tenants = list(session.scalars(query).all())
        next_cursor = tenants[limit - 1].id if len(tenants) > limit else None
        return {
            "items": [tenant_body(tenant) for tenant in tenants[:limit]],
            "next_cursor": next_cursor,
        }

    @router.post("/tenants")
    def create_tenant(
        payload: TenantCreate,
        request: Request,
        idempotency_key: str | None = Header(
            default=None,
            alias="Idempotency-Key",
        ),
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        require_platform_admin(context)
        key = require_idempotency_key(idempotency_key)
        digest = request_digest(payload)
        operation = "tenant:create"
        existing_record = find_idempotency_record(
            session,
            context.principal_id,
            operation,
            key,
            digest,
        )
        if existing_record is not None:
            return idempotency_response(
                existing_record,
                etag_resource_type="tenant",
            )
        if session.scalar(select(Tenant.id).where(Tenant.slug == payload.slug)):
            raise HubError(
                409,
                "tenant_slug_conflict",
                "A tenant with this slug already exists.",
            )
        tenant = Tenant(
            id=new_id("tenant"),
            slug=payload.slug,
            name=payload.name,
        )
        session.add(tenant)
        session.flush()
        body = tenant_body(tenant)
        append_mutation_audit(
            session,
            request,
            context,
            action=operation,
            resource_type="tenant",
            resource_id=tenant.id,
            tenant_id=tenant.id,
            digest=digest,
        )
        store_idempotency_record(
            session,
            context.principal_id,
            operation,
            key,
            digest,
            201,
            body,
        )
        return JSONResponse(
            status_code=201,
            content=body,
            headers={"ETag": resource_etag("tenant", tenant.id, tenant.version)},
        )

    @router.get("/tenants/{tenant_id}")
    def get_tenant(
        tenant_id: str,
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        require_tenant_read(context, tenant_id)
        tenant = session.get(Tenant, tenant_id)
        if tenant is None:
            raise HubError(404, "tenant_not_found", "The tenant does not exist.")
        return JSONResponse(
            content=tenant_body(tenant),
            headers={"ETag": resource_etag("tenant", tenant.id, tenant.version)},
        )

    @router.patch("/tenants/{tenant_id}")
    def update_tenant(
        tenant_id: str,
        payload: TenantPatch,
        request: Request,
        if_match: str | None = Header(default=None, alias="If-Match"),
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        require_platform_admin(context)
        tenant = session.get(Tenant, tenant_id)
        if tenant is None or not can_read_tenant(context, tenant_id):
            raise HubError(404, "tenant_not_found", "The tenant does not exist.")
        require_current_etag("tenant", tenant.id, tenant.version, if_match)
        next_name = payload.name if payload.name is not None else tenant.name
        next_status = payload.status if payload.status is not None else tenant.status
        updated_id = session.scalar(
            update(Tenant)
            .where(Tenant.id == tenant.id, Tenant.version == tenant.version)
            .values(
                name=next_name,
                status=next_status,
                version=tenant.version + 1,
                updated_at=utc_now(),
            )
            .returning(Tenant.id)
        )
        if updated_id is None:
            raise HubError(
                412,
                "etag_mismatch",
                "The resource changed after it was loaded.",
            )
        session.expire(tenant)
        session.refresh(tenant)
        digest = request_digest(payload)
        append_mutation_audit(
            session,
            request,
            context,
            action="tenant:update",
            resource_type="tenant",
            resource_id=tenant.id,
            tenant_id=tenant.id,
            digest=digest,
        )
        return JSONResponse(
            content=tenant_body(tenant),
            headers={"ETag": resource_etag("tenant", tenant.id, tenant.version)},
        )

    return router
