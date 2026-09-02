"""Initial browser-session administration API."""

from collections.abc import Generator
from hashlib import sha256
from json import dumps

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from proxy_hub.auth import AuthComponents
from proxy_hub.database import Database, session_scope
from proxy_hub.errors import HubError, request_id
from proxy_hub.models import (
    AuditEvent,
    IdempotencyRecord,
    Principal,
    Tenant,
    new_id,
    utc_now,
)
from proxy_hub.rbac import (
    AdminContext,
    can_read_tenant,
    capability_names,
    require_platform_admin,
    require_tenant_read,
)
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


def request_digest(payload: BaseModel) -> str:
    """Hash validated mutation input for audit and idempotency."""
    encoded = dumps(
        payload.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def append_audit(
    session: Session,
    request: Request,
    context: AdminContext,
    action: str,
    resource_type: str,
    resource_id: str,
    tenant_id: str | None,
    argument_digest: str,
) -> None:
    """Append an audit event in the caller's transaction."""
    session.add(
        AuditEvent(
            id=new_id("audit"),
            request_id=request_id(request),
            principal_id=context.principal_id,
            tenant_id=tenant_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome="accepted",
            details={
                "argument_digest": argument_digest,
                "result_class": "success",
            },
        )
    )


def build_admin_router(
    database: Database,
    auth: AuthComponents,
) -> APIRouter:
    """Build administration routes bound to application resources."""
    router = APIRouter(prefix="/v1/admin", tags=["administration"])

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
        if not idempotency_key or len(idempotency_key) > 255:
            raise HubError(
                400,
                "idempotency_key_required",
                "A valid Idempotency-Key header is required.",
            )
        digest = request_digest(payload)
        operation = "tenant:create"
        existing_record = session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.principal_id == context.principal_id,
                IdempotencyRecord.operation == operation,
                IdempotencyRecord.key == idempotency_key,
            )
        )
        if existing_record is not None:
            if existing_record.request_digest != digest:
                raise HubError(
                    409,
                    "idempotency_conflict",
                    "The idempotency key was used for a different request.",
                )
            replay_id = existing_record.response_body.get("id")
            replay_version = existing_record.response_body.get("version")
            if not isinstance(replay_id, str) or not isinstance(
                replay_version,
                int,
            ):
                raise HubError(
                    500,
                    "idempotency_record_invalid",
                    "The stored operation result is invalid.",
                )
            return JSONResponse(
                status_code=existing_record.response_status,
                content=existing_record.response_body,
                headers={
                    "ETag": resource_etag(
                        "tenant",
                        replay_id,
                        replay_version,
                    )
                },
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
        append_audit(
            session,
            request,
            context,
            operation,
            "tenant",
            tenant.id,
            tenant.id,
            digest,
        )
        session.add(
            IdempotencyRecord(
                id=new_id("idem"),
                principal_id=context.principal_id,
                operation=operation,
                key=idempotency_key,
                request_digest=digest,
                response_status=201,
                response_body=body,
            )
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
        expected_etag = resource_etag("tenant", tenant.id, tenant.version)
        if if_match is None:
            raise HubError(
                400,
                "if_match_required",
                "The current resource ETag is required.",
            )
        if if_match != expected_etag:
            raise HubError(
                412,
                "etag_mismatch",
                "The resource changed after it was loaded.",
            )
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
        append_audit(
            session,
            request,
            context,
            "tenant:update",
            "tenant",
            tenant.id,
            tenant.id,
            request_digest(payload),
        )
        return JSONResponse(
            content=tenant_body(tenant),
            headers={"ETag": resource_etag("tenant", tenant.id, tenant.version)},
        )

    return router
