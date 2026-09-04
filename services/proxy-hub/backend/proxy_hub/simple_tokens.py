"""Single-lab Token administration and DSH validation APIs."""

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from unicodedata import normalize

import httpx
from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from proxy_hub.access_keys import _key_status, issue_access_key
from proxy_hub.audit import AuditEntry, append_audit_event
from proxy_hub.auth import AuthComponents, ensure_utc
from proxy_hub.backend_probe import probe_scholar_backend
from proxy_hub.capabilities import CredentialContext, authenticate_credential
from proxy_hub.config import Settings
from proxy_hub.database import Database, session_scope
from proxy_hub.errors import HubError, request_id
from proxy_hub.models import (
    AccessKey,
    AuditEvent,
    Membership,
    Principal,
    ScholarBackend,
    Tenant,
    TenantRoute,
    new_id,
    utc_now,
)
from proxy_hub.mutations import (
    append_mutation_audit,
    find_idempotency_record,
    idempotency_response,
    request_digest,
    require_current_etag,
    require_idempotency_key,
    store_idempotency_record,
)
from proxy_hub.policy import SCHOLAR_TOOL_CATALOG
from proxy_hub.rbac import AdminContext, require_tenant_mutation
from proxy_hub.routing import RouteResolutionError, resolve_route
from proxy_hub.secrets import SecretResolver
from proxy_hub.security import resource_etag
from proxy_hub.single_lab import resolve_single_lab_tenant

MANAGED_ISSUER = "urn:scholar-proxy-hub:managed"
MAX_AUDIT_RANGE = timedelta(days=31)


def normalize_token_name(value: str) -> tuple[str, str]:
    """Return a trimmed display name and its Unicode uniqueness key."""
    display_name = normalize("NFKC", value.strip())
    if not display_name:
        raise ValueError("Token name must not be empty.")
    return display_name, display_name.casefold()


class TokenCreate(BaseModel):
    """Permanent single-lab Token creation input."""

    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return normalize_token_name(value)[0]


class TokenPatch(BaseModel):
    """Token display-name mutation input."""

    name: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return normalize_token_name(value)[0] if value is not None else None

    @model_validator(mode="after")
    def require_change(self) -> "TokenPatch":
        if self.name is None:
            raise ValueError("A Token name is required.")
        return self


class TokenRotate(BaseModel):
    """Explicit Token rotation confirmation."""

    confirm: bool

    @model_validator(mode="after")
    def require_confirmation(self) -> "TokenRotate":
        if not self.confirm:
            raise ValueError("Token rotation must be confirmed.")
        return self


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _token_body(
    access_key: AccessKey,
    principal: Principal,
    *,
    raw_token: str | None = None,
) -> dict[str, object]:
    return {
        "id": access_key.id,
        "name": principal.display_name or access_key.label,
        "token": raw_token,
        "token_prefix": access_key.token_prefix,
        "token_last_four": access_key.token_last_four,
        "status": _key_status(access_key, utc_now()),
        "created_at": access_key.created_at.isoformat(),
        "last_used_at": (
            access_key.last_used_at.isoformat()
            if access_key.last_used_at is not None
            else None
        ),
        "revoked_at": (
            access_key.revoked_at.isoformat()
            if access_key.revoked_at is not None
            else None
        ),
        "expires_at": (
            access_key.expires_at.isoformat()
            if access_key.expires_at is not None
            else None
        ),
        "version": access_key.version,
        "etag": resource_etag("token", access_key.id, access_key.version),
    }


def _facade_token(
    session: Session,
    tenant_id: str,
    token_id: str,
) -> tuple[AccessKey, Principal, Membership]:
    row = session.execute(
        select(AccessKey, Principal, Membership)
        .join(Principal, Principal.id == AccessKey.principal_id)
        .join(
            Membership,
            and_(
                Membership.principal_id == Principal.id,
                Membership.tenant_id == AccessKey.tenant_id,
            ),
        )
        .where(
            AccessKey.id == token_id,
            AccessKey.tenant_id == tenant_id,
            AccessKey.token_name_key.is_not(None),
        )
    ).one_or_none()
    if row is None:
        raise HubError(404, "token_not_found", "The Token does not exist.")
    return row[0], row[1], row[2]


def _latest_facade_tokens(
    session: Session,
    tenant_id: str,
) -> list[tuple[AccessKey, Principal]]:
    rows = session.execute(
        select(AccessKey, Principal)
        .join(Principal, Principal.id == AccessKey.principal_id)
        .where(
            AccessKey.tenant_id == tenant_id,
            AccessKey.token_name_key.is_not(None),
            Principal.status == "active",
        )
        .order_by(AccessKey.created_at.desc(), AccessKey.id.desc())
    ).all()
    latest: dict[str, tuple[AccessKey, Principal]] = {}
    for access_key, principal in rows:
        latest.setdefault(principal.id, (access_key, principal))
    return sorted(
        latest.values(),
        key=lambda item: (item[0].created_at, item[0].id),
        reverse=True,
    )


def _require_token_admin(
    session: Session,
    settings: Settings,
    context: AdminContext,
) -> Tenant:
    tenant = resolve_single_lab_tenant(session, settings)
    require_tenant_mutation(context, tenant.id)
    return tenant


def _route_backend(
    session: Session,
    tenant: Tenant,
) -> tuple[TenantRoute | None, ScholarBackend | None]:
    route = session.get(TenantRoute, tenant.id)
    backend = (
        session.get(ScholarBackend, route.backend_id) if route is not None else None
    )
    return route, backend


def _service_status(
    settings: Settings,
    route: TenantRoute | None,
    backend: ScholarBackend | None,
) -> dict[str, object]:
    observed_at = utc_now()
    probe_at = (
        _aware(backend.last_probe_at)
        if backend is not None and backend.last_probe_at is not None
        else None
    )
    fresh = probe_at is not None and observed_at - probe_at <= timedelta(
        seconds=settings.backend_probe_max_age_seconds
    )
    available = bool(
        route is not None
        and route.status == "active"
        and backend is not None
        and backend.status == "active"
        and backend.last_probe_ready is True
        and backend.last_probe_reason == "ready"
        and fresh
    )
    return {
        "available": available,
        "corpus_version": (
            route.corpus_version
            if route is not None
            else backend.corpus_version
            if backend is not None
            else None
        ),
        "checked_at": probe_at.isoformat() if probe_at is not None else None,
        "reason": None
        if available
        else (backend.last_probe_reason if backend is not None else "not_configured"),
        "transport": {
            "secure": settings.public_origin.scheme == "https",
            "development_http": (
                settings.public_origin.scheme == "http"
                and settings.allow_insecure_public_http
            ),
        },
    }


def _credential_name(session: Session, context: CredentialContext) -> str:
    principal = session.get(Principal, context.principal_id)
    if principal is None or principal.kind != "managed_researcher":
        raise HubError(
            403,
            "credential_denied",
            "The Scholar credential is not a managed Token.",
        )
    return principal.display_name or "Scholar Token"


def build_token_admin_router(
    database: Database,
    auth: AuthComponents,
    settings: Settings,
    http_client: httpx.AsyncClient,
    secret_resolver: SecretResolver,
) -> APIRouter:
    """Build the simplified single-lab administration facade."""
    router = APIRouter()

    def get_session() -> Generator[Session, None, None]:
        yield from session_scope(database)

    @router.get("/tokens")
    def list_tokens(
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        tenant = _require_token_admin(session, settings, context)
        return {
            "items": [
                _token_body(access_key, principal)
                for access_key, principal in _latest_facade_tokens(
                    session,
                    tenant.id,
                )
            ]
        }

    @router.post("/tokens")
    def create_token(
        payload: TokenCreate,
        request: Request,
        idempotency_key: str | None = Header(
            default=None,
            alias="Idempotency-Key",
        ),
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        tenant = _require_token_admin(session, settings, context)
        key = require_idempotency_key(idempotency_key)
        digest = request_digest(payload)
        operation = "token:create"
        record = find_idempotency_record(
            session,
            context.principal_id,
            operation,
            key,
            digest,
        )
        if record is not None:
            return idempotency_response(
                record,
                etag_resource_type="token",
                redacted_fields=("token",),
            )
        display_name, name_key = normalize_token_name(payload.name)
        existing = session.scalar(
            select(Principal.id).where(
                Principal.managed_name_key == name_key,
            )
        )
        if existing is not None:
            raise HubError(
                409,
                "token_name_conflict",
                "A Token with this name already exists.",
            )
        principal_id = new_id("principal")
        principal = Principal(
            id=principal_id,
            issuer=MANAGED_ISSUER,
            subject=principal_id,
            display_name=display_name,
            managed_name_key=name_key,
            kind="managed_researcher",
        )
        session.add(principal)
        try:
            session.flush()
        except IntegrityError as error:
            session.rollback()
            raise HubError(
                409,
                "token_name_conflict",
                "A Token with this name already exists.",
            ) from error
        membership = Membership(
            id=new_id("membership"),
            principal_id=principal.id,
            tenant_id=tenant.id,
        )
        session.add(membership)
        access_key, raw_token = issue_access_key(
            session,
            context,
            tenant_id=tenant.id,
            principal_id=principal.id,
            label=display_name,
            allowed_tools=sorted(SCHOLAR_TOOL_CATALOG),
            expires_at=None,
            request_limit=None,
            period_seconds=None,
            token_name_key=name_key,
            active_name_key=name_key,
        )
        response_body = _token_body(
            access_key,
            principal,
            raw_token=raw_token,
        )
        stored_body = _token_body(access_key, principal)
        append_mutation_audit(
            session,
            request,
            context,
            action=operation,
            resource_type="token",
            resource_id=access_key.id,
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
            stored_body,
        )
        session.commit()
        return JSONResponse(
            status_code=201,
            content=response_body,
            headers={"ETag": resource_etag("token", access_key.id, access_key.version)},
        )

    @router.patch("/tokens/{token_id}")
    def rename_token(
        token_id: str,
        payload: TokenPatch,
        request: Request,
        if_match: str | None = Header(default=None, alias="If-Match"),
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        tenant = _require_token_admin(session, settings, context)
        access_key, principal, _membership = _facade_token(
            session,
            tenant.id,
            token_id,
        )
        require_current_etag("token", access_key.id, access_key.version, if_match)
        display_name, name_key = normalize_token_name(payload.name or "")
        conflict = session.scalar(
            select(Principal.id).where(
                Principal.managed_name_key == name_key,
                Principal.id != principal.id,
            )
        )
        if conflict is not None:
            raise HubError(
                409,
                "token_name_conflict",
                "A Token with this name already exists.",
            )
        principal.display_name = display_name
        principal.managed_name_key = name_key
        principal.version += 1
        session.execute(
            update(AccessKey)
            .where(AccessKey.principal_id == principal.id)
            .values(
                label=display_name,
                token_name_key=name_key,
                updated_at=utc_now(),
            )
        )
        if access_key.revoked_at is None and access_key.active_name_key is not None:
            access_key.active_name_key = name_key
        access_key.version += 1
        digest = request_digest(payload)
        append_mutation_audit(
            session,
            request,
            context,
            action="token:rename",
            resource_type="token",
            resource_id=access_key.id,
            tenant_id=tenant.id,
            digest=digest,
        )
        session.commit()
        session.refresh(access_key)
        return JSONResponse(
            content=_token_body(access_key, principal),
            headers={"ETag": resource_etag("token", access_key.id, access_key.version)},
        )

    @router.post("/tokens/{token_id}/rotate")
    def rotate_token(
        token_id: str,
        payload: TokenRotate,
        request: Request,
        idempotency_key: str | None = Header(
            default=None,
            alias="Idempotency-Key",
        ),
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        tenant = _require_token_admin(session, settings, context)
        key = require_idempotency_key(idempotency_key)
        digest = request_digest(payload)
        operation = f"token:rotate:{token_id}"
        record = find_idempotency_record(
            session,
            context.principal_id,
            operation,
            key,
            digest,
        )
        if record is not None:
            return idempotency_response(
                record,
                etag_resource_type="token",
                redacted_fields=("token",),
            )
        access_key, principal, membership = _facade_token(
            session,
            tenant.id,
            token_id,
        )
        name_key = principal.managed_name_key
        if name_key is None:
            raise HubError(409, "token_invalid", "The Token name is unavailable.")
        now = utc_now()
        if access_key.revoked_at is None:
            access_key.revoked_at = now
            access_key.revoked_by_principal_id = context.principal_id
            access_key.revoke_reason = "rotated"
        access_key.active_name_key = None
        access_key.version += 1
        principal.status = "active"
        membership.status = "active"
        session.flush()
        replacement, raw_token = issue_access_key(
            session,
            context,
            tenant_id=tenant.id,
            principal_id=principal.id,
            label=principal.display_name or access_key.label,
            allowed_tools=sorted(SCHOLAR_TOOL_CATALOG),
            expires_at=None,
            request_limit=None,
            period_seconds=None,
            token_name_key=name_key,
            active_name_key=name_key,
        )
        response_body = _token_body(
            replacement,
            principal,
            raw_token=raw_token,
        )
        stored_body = _token_body(replacement, principal)
        append_mutation_audit(
            session,
            request,
            context,
            action="token:rotate",
            resource_type="token",
            resource_id=replacement.id,
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
            stored_body,
        )
        session.commit()
        return JSONResponse(
            status_code=201,
            content=response_body,
            headers={
                "ETag": resource_etag(
                    "token",
                    replacement.id,
                    replacement.version,
                )
            },
        )

    def revoke(
        token_id: str,
        request: Request,
        context: AdminContext,
        session: Session,
        if_match: str | None,
        *,
        reason: str,
        disable_identity: bool,
    ) -> Response:
        tenant = _require_token_admin(session, settings, context)
        access_key, principal, membership = _facade_token(
            session,
            tenant.id,
            token_id,
        )
        require_current_etag("token", access_key.id, access_key.version, if_match)
        if access_key.revoked_at is None:
            access_key.revoked_at = utc_now()
            access_key.revoked_by_principal_id = context.principal_id
            access_key.revoke_reason = reason
            access_key.active_name_key = None
            access_key.version += 1
        if disable_identity:
            principal.status = "disabled"
            principal.managed_name_key = None
            membership.status = "disabled"
            principal.version += 1
            membership.version += 1
        append_mutation_audit(
            session,
            request,
            context,
            action=f"token:{reason}",
            resource_type="token",
            resource_id=access_key.id,
            tenant_id=tenant.id,
            digest=request_digest(TokenRotate(confirm=True)),
        )
        session.commit()
        return Response(status_code=204)

    @router.post("/tokens/{token_id}/revoke", status_code=204)
    def revoke_token(
        token_id: str,
        request: Request,
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
        if_match: str | None = Header(default=None, alias="If-Match"),
    ) -> Response:
        return revoke(
            token_id,
            request,
            context,
            session,
            if_match,
            reason="revoked",
            disable_identity=False,
        )

    @router.delete("/tokens/{token_id}", status_code=204)
    def delete_token(
        token_id: str,
        request: Request,
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
        if_match: str | None = Header(default=None, alias="If-Match"),
    ) -> Response:
        return revoke(
            token_id,
            request,
            context,
            session,
            if_match,
            reason="deleted",
            disable_identity=True,
        )

    @router.get("/service-status")
    def service_status(
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        tenant = _require_token_admin(session, settings, context)
        return _service_status(settings, *_route_backend(session, tenant))

    @router.post("/service-status/probe")
    async def probe_service(
        request: Request,
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        tenant = _require_token_admin(session, settings, context)
        route, backend = _route_backend(session, tenant)
        if route is None or backend is None:
            raise HubError(
                503,
                "backend_unavailable",
                "The Scholar Backend is not configured.",
            )
        result = await probe_scholar_backend(
            http_client,
            secret_resolver,
            base_url=backend.base_url,
            credential_ref=backend.credential_ref,
            expected_corpus_version=backend.corpus_version,
            production=settings.environment == "production",
            request_id=request_id(request),
            maximum_bytes=settings.backend_probe_max_bytes,
        )
        backend.last_probe_at = utc_now()
        backend.last_probe_ready = result.ready
        backend.last_probe_reason = result.reason
        backend.capacity = result.capacity if result.ready else {}
        backend.status = "active" if result.ready else "disabled"
        backend.version += 1
        route.status = "active" if result.ready else "disabled"
        route.corpus_version = backend.corpus_version
        route.version += 1
        append_audit_event(
            session,
            AuditEntry(
                request_id=request_id(request),
                principal_id=context.principal_id,
                tenant_id=tenant.id,
                action="backend:probe",
                resource_type="scholar_backend",
                resource_id=backend.id,
                outcome="accepted" if result.ready else "rejected",
                backend_id=backend.id,
                corpus_version=backend.corpus_version,
                decision=result.reason,
                result_class="success" if result.ready else "unavailable",
            ),
        )
        session.commit()
        return JSONResponse(
            content=_service_status(settings, route, backend),
        )

    @router.get("/token-audit")
    def token_audit(
        start: datetime = Query(alias="from"),
        end: datetime = Query(alias="to"),
        limit: int = Query(default=100, ge=1, le=100),
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        tenant = _require_token_admin(session, settings, context)
        if start.tzinfo is None or end.tzinfo is None:
            raise HubError(
                400,
                "time_range_invalid",
                "Audit timestamps must include a timezone.",
            )
        normalized_start = ensure_utc(start)
        normalized_end = ensure_utc(end)
        if (
            normalized_end <= normalized_start
            or normalized_end - normalized_start > MAX_AUDIT_RANGE
        ):
            raise HubError(
                400,
                "time_range_invalid",
                "Audit queries require an ordered range of at most 31 days.",
            )
        rows = session.execute(
            select(AuditEvent, Principal)
            .join(AccessKey, AccessKey.id == AuditEvent.access_key_id)
            .join(Principal, Principal.id == AccessKey.principal_id)
            .where(
                AuditEvent.tenant_id == tenant.id,
                AuditEvent.action.in_(("mcp:tool", "mcp:forward")),
                AuditEvent.occurred_at >= normalized_start,
                AuditEvent.occurred_at < normalized_end,
            )
            .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
            .limit(limit)
        ).all()
        return {
            "items": [
                {
                    "token_name": principal.display_name,
                    "mcp_tool": event.tool_name,
                    "occurred_at": ensure_utc(event.occurred_at).isoformat(),
                    "result": event.outcome,
                    "duration_ms": event.latency_ms,
                    "request_id": event.request_id,
                }
                for event, principal in rows
            ]
        }

    return router


def build_token_user_router(
    database: Database,
    settings: Settings,
) -> APIRouter:
    """Build Token self-validation routes used by DSH Scholar mode."""
    router = APIRouter(tags=["scholar-token"])

    def get_session() -> Generator[Session, None, None]:
        yield from session_scope(database)

    @router.get("/v1/me")
    def token_me(
        request: Request,
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        context = authenticate_credential(
            session,
            request.headers.get("authorization"),
        )
        name = _credential_name(session, context)
        try:
            selection = resolve_route(
                session,
                context.tenant_id,
                context.credential_id,
                utc_now(),
                timedelta(seconds=settings.backend_probe_max_age_seconds),
                credential_kind=context.credential_kind,
            )
        except RouteResolutionError as error:
            raise HubError(
                503,
                "backend_unavailable",
                "No eligible Scholar Backend is available.",
            ) from error
        if context.access_key_id is not None:
            access_key = session.get(AccessKey, context.access_key_id)
            if access_key is not None:
                access_key.last_used_at = utc_now()
        return {
            "name": name,
            "scholar": {
                "available": True,
                "corpus_version": selection.corpus_version,
            },
        }

    return router
