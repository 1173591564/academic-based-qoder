"""Tenant policy, quota, and Scholar route administration."""

from collections.abc import Generator
from datetime import timedelta

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.orm import Session

from proxy_hub.auth import AuthComponents
from proxy_hub.config import Settings
from proxy_hub.database import Database, session_scope
from proxy_hub.errors import HubError
from proxy_hub.models import (
    QuotaPolicy,
    ScholarBackend,
    Tenant,
    TenantRoute,
    ToolPolicy,
    utc_now,
)
from proxy_hub.mutations import (
    append_mutation_audit,
    request_digest,
    require_version_update,
)
from proxy_hub.policy import InvalidToolPolicy, validate_tool_policy
from proxy_hub.rbac import (
    AdminContext,
    require_platform_admin,
    require_tenant_mutation,
    require_tenant_read,
)
from proxy_hub.security import resource_etag


class ToolPolicyPut(BaseModel):
    """Exact tenant Scholar tool allowlist."""

    allowed_tools: list[str] = Field(max_length=16)


class QuotaPolicyPut(BaseModel):
    """Tenant request and concurrency quota."""

    quota_class: str = Field(min_length=1, max_length=64)
    request_limit: int = Field(gt=0, le=1_000_000_000)
    period_seconds: int = Field(gt=0, le=31_536_000)
    concurrency_limit: int = Field(gt=0, le=100_000)
    enforcement_enabled: bool


class TenantRoutePut(BaseModel):
    """Explicit tenant-to-backend route."""

    backend_id: str = Field(min_length=1, max_length=48)
    corpus_version: str = Field(min_length=1, max_length=128)
    status: str = Field(default="active", pattern=r"^(active|disabled)$")


def tool_policy_body(policy: ToolPolicy) -> dict[str, object]:
    """Serialize an exact tenant tool policy."""
    return {
        "tenant_id": policy.tenant_id,
        "allowed_tools": sorted(policy.allowed_tools),
        "version": policy.version,
        "created_at": policy.created_at.isoformat(),
        "updated_at": policy.updated_at.isoformat(),
    }


def quota_policy_body(policy: QuotaPolicy) -> dict[str, object]:
    """Serialize a tenant quota policy."""
    return {
        "tenant_id": policy.tenant_id,
        "quota_class": policy.quota_class,
        "request_limit": policy.request_limit,
        "period_seconds": policy.period_seconds,
        "concurrency_limit": policy.concurrency_limit,
        "enforcement_enabled": policy.enforcement_enabled,
        "version": policy.version,
        "created_at": policy.created_at.isoformat(),
        "updated_at": policy.updated_at.isoformat(),
    }


def route_body(route: TenantRoute) -> dict[str, object]:
    """Serialize an explicit tenant backend route."""
    return {
        "tenant_id": route.tenant_id,
        "backend_id": route.backend_id,
        "corpus_version": route.corpus_version,
        "status": route.status,
        "version": route.version,
        "created_at": route.created_at.isoformat(),
        "updated_at": route.updated_at.isoformat(),
    }


def _require_tenant(session: Session, context: AdminContext, tenant_id: str) -> Tenant:
    require_tenant_read(context, tenant_id)
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HubError(404, "tenant_not_found", "The tenant does not exist.")
    return tenant


def _require_upsert_etag(
    resource_type: str,
    resource_id: str,
    version: int | None,
    if_match: str | None,
) -> None:
    if if_match is None:
        raise HubError(
            400,
            "if_match_required",
            "The current resource ETag is required.",
        )
    if version is None:
        if if_match != "*":
            raise HubError(
                412,
                "etag_mismatch",
                "Use If-Match: * to create this resource.",
            )
        return
    if if_match != resource_etag(resource_type, resource_id, version):
        raise HubError(
            412,
            "etag_mismatch",
            "The resource changed after it was loaded.",
        )


def _probe_is_fresh(backend: ScholarBackend, settings: Settings) -> bool:
    if (
        backend.last_probe_at is None
        or backend.last_probe_ready is not True
        or backend.last_probe_reason != "ready"
    ):
        return False
    observed_at = backend.last_probe_at
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=utc_now().tzinfo)
    return utc_now() - observed_at <= timedelta(
        seconds=settings.backend_probe_max_age_seconds
    )


def build_policy_router(
    database: Database,
    auth: AuthComponents,
    settings: Settings,
) -> APIRouter:
    """Build tenant policy and route administration routes."""
    router = APIRouter()

    def get_session() -> Generator[Session, None, None]:
        yield from session_scope(database)

    @router.get("/tenants/{tenant_id}/tool-policy")
    def get_tool_policy(
        tenant_id: str,
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        _require_tenant(session, context, tenant_id)
        policy = session.get(ToolPolicy, tenant_id)
        if policy is None:
            raise HubError(
                404,
                "tool_policy_not_found",
                "The tenant tool policy is not configured.",
            )
        return JSONResponse(
            content=tool_policy_body(policy),
            headers={"ETag": resource_etag("tool_policy", tenant_id, policy.version)},
        )

    @router.put("/tenants/{tenant_id}/tool-policy")
    def put_tool_policy(
        tenant_id: str,
        payload: ToolPolicyPut,
        request: Request,
        if_match: str | None = Header(default=None, alias="If-Match"),
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        _require_tenant(session, context, tenant_id)
        require_tenant_mutation(context, tenant_id)
        try:
            allowed_tools = list(validate_tool_policy(payload.allowed_tools))
        except InvalidToolPolicy as error:
            raise HubError(
                400,
                "tool_policy_invalid",
                "The tool policy contains an unknown Scholar tool.",
            ) from error
        policy = session.get(ToolPolicy, tenant_id)
        _require_upsert_etag(
            "tool_policy",
            tenant_id,
            policy.version if policy is not None else None,
            if_match,
        )
        status_code = 200
        if policy is None:
            policy = ToolPolicy(tenant_id=tenant_id, allowed_tools=allowed_tools)
            session.add(policy)
            session.flush()
            status_code = 201
        else:
            updated_id = session.scalar(
                update(ToolPolicy)
                .where(
                    ToolPolicy.tenant_id == tenant_id,
                    ToolPolicy.version == policy.version,
                )
                .values(
                    allowed_tools=allowed_tools,
                    version=policy.version + 1,
                    updated_at=utc_now(),
                )
                .returning(ToolPolicy.tenant_id)
            )
            require_version_update(updated_id)
            session.expire(policy)
            session.refresh(policy)
        append_mutation_audit(
            session,
            request,
            context,
            action="tool_policy:put",
            resource_type="tool_policy",
            resource_id=tenant_id,
            tenant_id=tenant_id,
            digest=request_digest(payload),
            details={"allowed_tool_count": len(allowed_tools)},
        )
        return JSONResponse(
            status_code=status_code,
            content=tool_policy_body(policy),
            headers={"ETag": resource_etag("tool_policy", tenant_id, policy.version)},
        )

    @router.get("/tenants/{tenant_id}/quota-policy")
    def get_quota_policy(
        tenant_id: str,
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        _require_tenant(session, context, tenant_id)
        policy = session.get(QuotaPolicy, tenant_id)
        if policy is None:
            raise HubError(
                404,
                "quota_policy_not_found",
                "The tenant quota policy is not configured.",
            )
        return JSONResponse(
            content=quota_policy_body(policy),
            headers={"ETag": resource_etag("quota_policy", tenant_id, policy.version)},
        )

    @router.put("/tenants/{tenant_id}/quota-policy")
    def put_quota_policy(
        tenant_id: str,
        payload: QuotaPolicyPut,
        request: Request,
        if_match: str | None = Header(default=None, alias="If-Match"),
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        _require_tenant(session, context, tenant_id)
        require_tenant_mutation(context, tenant_id)
        policy = session.get(QuotaPolicy, tenant_id)
        _require_upsert_etag(
            "quota_policy",
            tenant_id,
            policy.version if policy is not None else None,
            if_match,
        )
        values = payload.model_dump()
        status_code = 200
        if policy is None:
            policy = QuotaPolicy(tenant_id=tenant_id, **values)
            session.add(policy)
            session.flush()
            status_code = 201
        else:
            updated_id = session.scalar(
                update(QuotaPolicy)
                .where(
                    QuotaPolicy.tenant_id == tenant_id,
                    QuotaPolicy.version == policy.version,
                )
                .values(
                    **values,
                    version=policy.version + 1,
                    updated_at=utc_now(),
                )
                .returning(QuotaPolicy.tenant_id)
            )
            require_version_update(updated_id)
            session.expire(policy)
            session.refresh(policy)
        append_mutation_audit(
            session,
            request,
            context,
            action="quota_policy:put",
            resource_type="quota_policy",
            resource_id=tenant_id,
            tenant_id=tenant_id,
            digest=request_digest(payload),
            details={
                "quota_class": payload.quota_class,
                "enforcement_enabled": payload.enforcement_enabled,
            },
        )
        return JSONResponse(
            status_code=status_code,
            content=quota_policy_body(policy),
            headers={"ETag": resource_etag("quota_policy", tenant_id, policy.version)},
        )

    @router.get("/tenants/{tenant_id}/backend-route")
    def get_backend_route(
        tenant_id: str,
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        _require_tenant(session, context, tenant_id)
        route = session.get(TenantRoute, tenant_id)
        if route is None:
            raise HubError(
                404,
                "backend_route_not_found",
                "The tenant backend route is not configured.",
            )
        return JSONResponse(
            content=route_body(route),
            headers={"ETag": resource_etag("backend_route", tenant_id, route.version)},
        )

    @router.put("/tenants/{tenant_id}/backend-route")
    def put_backend_route(
        tenant_id: str,
        payload: TenantRoutePut,
        request: Request,
        if_match: str | None = Header(default=None, alias="If-Match"),
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        require_platform_admin(context)
        tenant = _require_tenant(session, context, tenant_id)
        if tenant.status != "active" and payload.status == "active":
            raise HubError(
                409,
                "tenant_inactive",
                "An inactive tenant cannot receive an active route.",
            )
        backend = session.get(ScholarBackend, payload.backend_id)
        if backend is None:
            raise HubError(404, "backend_not_found", "The backend does not exist.")
        if payload.corpus_version != backend.corpus_version:
            raise HubError(
                409,
                "corpus_version_mismatch",
                "The route corpus version does not match the backend.",
            )
        if payload.status == "active" and (
            backend.status != "active" or not _probe_is_fresh(backend, settings)
        ):
            raise HubError(
                409,
                "backend_not_ready",
                "The backend is not active with a current successful probe.",
            )
        route = session.get(TenantRoute, tenant_id)
        _require_upsert_etag(
            "backend_route",
            tenant_id,
            route.version if route is not None else None,
            if_match,
        )
        values = payload.model_dump()
        status_code = 200
        if route is None:
            route = TenantRoute(tenant_id=tenant_id, **values)
            session.add(route)
            session.flush()
            status_code = 201
        else:
            updated_id = session.scalar(
                update(TenantRoute)
                .where(
                    TenantRoute.tenant_id == tenant_id,
                    TenantRoute.version == route.version,
                )
                .values(
                    **values,
                    version=route.version + 1,
                    updated_at=utc_now(),
                )
                .returning(TenantRoute.tenant_id)
            )
            require_version_update(updated_id)
            session.expire(route)
            session.refresh(route)
        append_mutation_audit(
            session,
            request,
            context,
            action="backend_route:put",
            resource_type="tenant_route",
            resource_id=tenant_id,
            tenant_id=tenant_id,
            digest=request_digest(payload),
            backend_id=payload.backend_id,
            corpus_version=payload.corpus_version,
            decision=payload.status,
            details={
                "backend_id": payload.backend_id,
                "corpus_version": payload.corpus_version,
                "status": payload.status,
            },
        )
        return JSONResponse(
            status_code=status_code,
            content=route_body(route),
            headers={"ETag": resource_etag("backend_route", tenant_id, route.version)},
        )

    return router
