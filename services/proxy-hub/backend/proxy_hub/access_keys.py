"""Managed researcher and direct Scholar Access Key administration."""

from collections.abc import Generator
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from proxy_hub.auth import AuthComponents
from proxy_hub.database import Database, session_scope
from proxy_hub.eligibility import active_membership_exists
from proxy_hub.errors import HubError
from proxy_hub.models import (
    AccessKey,
    Membership,
    Principal,
    Team,
    Tenant,
    ToolPolicy,
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
    require_version_update,
    store_idempotency_record,
)
from proxy_hub.policy import InvalidToolPolicy, validate_tool_policy
from proxy_hub.rbac import AdminContext, require_tenant_mutation
from proxy_hub.security import digest_token, new_token, resource_etag

ACCESS_KEY_PREFIX = "sk_scholar_v1_"
MANAGED_ISSUER = "urn:scholar-proxy-hub:managed"


class KeySettings(BaseModel):
    """Shared Access Key creation settings."""

    label: str = Field(min_length=1, max_length=200)
    allowed_tools: list[str] = Field(min_length=1, max_length=16)
    expires_in_seconds: int = Field(ge=300, le=31_536_000)
    request_limit: int | None = Field(default=None, ge=1, le=10_000_000)
    period_seconds: int | None = Field(default=None, ge=1, le=2_592_000)

    @field_validator("allowed_tools")
    @classmethod
    def validate_tools(cls, value: list[str]) -> list[str]:
        try:
            return list(validate_tool_policy(value))
        except InvalidToolPolicy as error:
            raise ValueError("allowed tools contain unknown Scholar tools") from error

    @model_validator(mode="after")
    def validate_quota_pair(self) -> "KeySettings":
        if (self.request_limit is None) != (self.period_seconds is None):
            raise ValueError(
                "request_limit and period_seconds must be provided together"
            )
        return self


class ResearcherCreate(KeySettings):
    """Managed researcher, membership, and initial key input."""

    display_name: str = Field(min_length=1, max_length=256)
    email: str | None = Field(default=None, max_length=320)
    team_id: str | None = Field(default=None, min_length=1, max_length=48)


class AccessKeyCreate(KeySettings):
    """Additional Access Key input."""


class AccessKeyPatch(BaseModel):
    """Mutable Access Key restrictions."""

    label: str | None = Field(default=None, min_length=1, max_length=200)
    allowed_tools: list[str] | None = Field(default=None, min_length=1, max_length=16)
    expires_at: datetime | None = None
    request_limit: int | None = Field(default=None, ge=1, le=10_000_000)
    period_seconds: int | None = Field(default=None, ge=1, le=2_592_000)

    @field_validator("allowed_tools")
    @classmethod
    def validate_tools(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        try:
            return list(validate_tool_policy(value))
        except InvalidToolPolicy as error:
            raise ValueError("allowed tools contain unknown Scholar tools") from error

    @model_validator(mode="after")
    def require_change(self) -> "AccessKeyPatch":
        if not self.model_fields_set:
            raise ValueError("At least one mutable field is required.")
        if ("request_limit" in self.model_fields_set) != (
            "period_seconds" in self.model_fields_set
        ):
            raise ValueError(
                "request_limit and period_seconds must be changed together"
            )
        return self


class AccessKeyRotate(BaseModel):
    """Replacement Access Key settings."""

    label: str | None = Field(default=None, min_length=1, max_length=200)
    expires_in_seconds: int | None = Field(
        default=None,
        ge=300,
        le=31_536_000,
    )


class ResearcherPatch(BaseModel):
    """Managed researcher status input."""

    status: str = Field(pattern=r"^(active|disabled)$")


def _key_status(access_key: AccessKey, now: datetime) -> str:
    if access_key.revoked_at is not None:
        return "revoked"
    if access_key.expires_at is not None and _aware(access_key.expires_at) <= now:
        return "expired"
    return "active"


def _aware(value: datetime) -> datetime:
    """Normalize SQLite and PostgreSQL timestamps to aware UTC values."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def access_key_body(
    access_key: AccessKey,
    *,
    raw_token: str | None = None,
) -> dict[str, object]:
    """Serialize Access Key metadata and an optional one-time secret."""
    now = utc_now()
    return {
        "id": access_key.id,
        "access_key": raw_token,
        "principal_id": access_key.principal_id,
        "tenant_id": access_key.tenant_id,
        "label": access_key.label,
        "token_prefix": access_key.token_prefix,
        "token_last_four": access_key.token_last_four,
        "allowed_tools": access_key.allowed_tools,
        "request_limit": access_key.request_limit,
        "period_seconds": access_key.period_seconds,
        "status": _key_status(access_key, now),
        "expires_at": (
            access_key.expires_at.isoformat()
            if access_key.expires_at is not None
            else None
        ),
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
        "revoke_reason": access_key.revoke_reason,
        "version": access_key.version,
        "etag": resource_etag("access_key", access_key.id, access_key.version),
        "created_at": access_key.created_at.isoformat(),
        "updated_at": access_key.updated_at.isoformat(),
    }


def researcher_body(
    principal: Principal,
    membership: Membership,
) -> dict[str, object]:
    """Serialize one managed researcher within a tenant."""
    return {
        "id": principal.id,
        "display_name": principal.display_name,
        "email": principal.email,
        "kind": principal.kind,
        "status": principal.status,
        "membership_id": membership.id,
        "membership_status": membership.status,
        "team_id": membership.team_id,
        "version": principal.version,
        "etag": resource_etag("principal", principal.id, principal.version),
        "created_at": principal.created_at.isoformat(),
        "updated_at": principal.updated_at.isoformat(),
    }


def validate_allowed_tools(
    session: Session,
    tenant_id: str,
    allowed_tools: list[str],
) -> None:
    """Require an Access Key tool set within the tenant policy."""
    policy = session.get(ToolPolicy, tenant_id)
    if policy is None:
        raise HubError(
            409,
            "tool_policy_missing",
            "Configure the tenant tool policy before issuing Access Keys.",
        )
    try:
        tenant_tools = set(validate_tool_policy(policy.allowed_tools))
    except InvalidToolPolicy as error:
        raise HubError(
            409,
            "tool_policy_invalid",
            "The tenant tool policy must be repaired before issuing keys.",
        ) from error
    if not set(allowed_tools).issubset(tenant_tools):
        raise HubError(
            409,
            "access_key_scope_exceeds_tenant",
            "Access Key tools cannot exceed the tenant tool policy.",
        )


def issue_access_key(
    session: Session,
    context: AdminContext,
    *,
    tenant_id: str,
    principal_id: str,
    label: str,
    allowed_tools: list[str],
    expires_at: datetime | None,
    request_limit: int | None,
    period_seconds: int | None,
    token_name_key: str | None = None,
    active_name_key: str | None = None,
) -> tuple[AccessKey, str]:
    """Issue one digest-only Access Key and return its one-time secret."""
    validate_allowed_tools(session, tenant_id, allowed_tools)
    raw_token = f"{ACCESS_KEY_PREFIX}{new_token()}"
    access_key = AccessKey(
        id=new_id("key"),
        token_digest=digest_token(raw_token),
        token_prefix=raw_token[:24],
        token_last_four=raw_token[-4:],
        principal_id=principal_id,
        tenant_id=tenant_id,
        label=label,
        token_name_key=token_name_key,
        active_name_key=active_name_key,
        allowed_tools=allowed_tools,
        request_limit=request_limit,
        period_seconds=period_seconds,
        expires_at=expires_at,
        created_by_principal_id=context.principal_id,
    )
    session.add(access_key)
    session.flush()
    return access_key, raw_token


def build_access_key_router(
    database: Database,
    auth: AuthComponents,
) -> APIRouter:
    """Create managed researcher and Access Key administration routes."""
    router = APIRouter()

    def get_session() -> Generator[Session, None, None]:
        yield from session_scope(database)

    def managed_tenant(
        session: Session,
        context: AdminContext,
        tenant_id: str,
    ) -> Tenant:
        require_tenant_mutation(context, tenant_id)
        tenant = session.get(Tenant, tenant_id)
        if tenant is None:
            raise HubError(
                404,
                "tenant_not_found",
                "The requested tenant is not available.",
            )
        return tenant

    def managed_researcher(
        session: Session,
        tenant_id: str,
        principal_id: str,
    ) -> tuple[Principal, Membership]:
        principal = session.get(Principal, principal_id)
        membership = session.scalar(
            select(Membership).where(
                Membership.tenant_id == tenant_id,
                Membership.principal_id == principal_id,
            )
        )
        if (
            principal is None
            or principal.kind != "managed_researcher"
            or membership is None
        ):
            raise HubError(
                404,
                "researcher_not_found",
                "The requested managed researcher is not available.",
            )
        return principal, membership

    def access_key_in_tenant(
        session: Session,
        tenant_id: str,
        access_key_id: str,
    ) -> AccessKey:
        access_key = session.scalar(
            select(AccessKey).where(
                AccessKey.id == access_key_id,
                AccessKey.tenant_id == tenant_id,
            )
        )
        if access_key is None:
            raise HubError(
                404,
                "access_key_not_found",
                "The requested Access Key is not available.",
            )
        return access_key

    def validate_team(
        session: Session,
        tenant_id: str,
        team_id: str | None,
    ) -> None:
        if team_id is None:
            return
        team = session.scalar(
            select(Team).where(
                Team.id == team_id,
                Team.tenant_id == tenant_id,
                Team.status == "active",
            )
        )
        if team is None:
            raise HubError(
                409,
                "team_inactive",
                "Researcher creation requires an active tenant team.",
            )

    @router.get("/tenants/{tenant_id}/researchers")
    def list_researchers(
        tenant_id: str,
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        managed_tenant(session, context, tenant_id)
        rows = session.execute(
            select(Principal, Membership)
            .join(Membership, Membership.principal_id == Principal.id)
            .where(
                Membership.tenant_id == tenant_id,
                Principal.kind == "managed_researcher",
            )
            .order_by(Principal.created_at.desc(), Principal.id)
        ).all()
        return {
            "items": [
                researcher_body(principal, membership) for principal, membership in rows
            ]
        }

    @router.post("/tenants/{tenant_id}/researchers")
    def create_researcher(
        tenant_id: str,
        payload: ResearcherCreate,
        request: Request,
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
        idempotency_key: str | None = Header(
            default=None,
            alias="Idempotency-Key",
        ),
    ) -> JSONResponse:
        tenant = managed_tenant(session, context, tenant_id)
        key = require_idempotency_key(idempotency_key)
        digest = request_digest(payload)
        operation = f"researcher:create:{tenant_id}"
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
                redacted_fields=("access_key",),
            )
        if tenant.status != "active":
            raise HubError(
                409,
                "tenant_inactive",
                "Researcher creation requires an active tenant.",
            )
        validate_team(session, tenant_id, payload.team_id)
        validate_allowed_tools(session, tenant_id, payload.allowed_tools)
        principal_id = new_id("principal")
        principal = Principal(
            id=principal_id,
            issuer=MANAGED_ISSUER,
            subject=principal_id,
            email=payload.email or None,
            display_name=payload.display_name,
            kind="managed_researcher",
        )
        membership = Membership(
            id=new_id("membership"),
            principal_id=principal_id,
            tenant_id=tenant_id,
            team_id=payload.team_id,
        )
        session.add_all((principal, membership))
        session.flush()
        access_key, raw_token = issue_access_key(
            session,
            context,
            tenant_id=tenant_id,
            principal_id=principal_id,
            label=payload.label,
            allowed_tools=payload.allowed_tools,
            expires_at=utc_now() + timedelta(seconds=payload.expires_in_seconds),
            request_limit=payload.request_limit,
            period_seconds=payload.period_seconds,
        )
        response_body = {
            "researcher": researcher_body(principal, membership),
            "access_key": access_key_body(access_key, raw_token=raw_token),
        }
        stored_body = {
            "researcher": researcher_body(principal, membership),
            "access_key": access_key_body(access_key),
        }
        append_mutation_audit(
            session,
            request,
            context,
            action="researcher:create",
            resource_type="principal",
            resource_id=principal.id,
            tenant_id=tenant_id,
            digest=digest,
            details={
                "membership_id": membership.id,
                "access_key_id": access_key.id,
                "tool_count": len(access_key.allowed_tools),
            },
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
        return JSONResponse(status_code=201, content=response_body)

    @router.patch("/tenants/{tenant_id}/researchers/{principal_id}")
    def update_researcher(
        tenant_id: str,
        principal_id: str,
        payload: ResearcherPatch,
        request: Request,
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
        if_match: str | None = Header(default=None, alias="If-Match"),
    ) -> JSONResponse:
        managed_tenant(session, context, tenant_id)
        principal, membership = managed_researcher(
            session,
            tenant_id,
            principal_id,
        )
        require_current_etag(
            "principal",
            principal.id,
            principal.version,
            if_match,
        )
        updated_id = session.scalar(
            update(Principal)
            .where(
                Principal.id == principal.id,
                Principal.version == principal.version,
            )
            .values(
                status=payload.status,
                version=principal.version + 1,
                updated_at=utc_now(),
            )
            .returning(Principal.id)
        )
        require_version_update(updated_id)
        session.expire(principal)
        session.refresh(principal)
        digest = request_digest(payload)
        append_mutation_audit(
            session,
            request,
            context,
            action="researcher:update",
            resource_type="principal",
            resource_id=principal.id,
            tenant_id=tenant_id,
            digest=digest,
        )
        session.commit()
        return JSONResponse(
            content=researcher_body(principal, membership),
            headers={
                "ETag": resource_etag(
                    "principal",
                    principal.id,
                    principal.version,
                )
            },
        )

    @router.get("/tenants/{tenant_id}/access-keys")
    def list_access_keys(
        tenant_id: str,
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        managed_tenant(session, context, tenant_id)
        access_keys = session.scalars(
            select(AccessKey)
            .where(AccessKey.tenant_id == tenant_id)
            .order_by(AccessKey.created_at.desc(), AccessKey.id)
        ).all()
        return {"items": [access_key_body(access_key) for access_key in access_keys]}

    @router.post("/tenants/{tenant_id}/researchers/{principal_id}/access-keys")
    def create_access_key(
        tenant_id: str,
        principal_id: str,
        payload: AccessKeyCreate,
        request: Request,
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
        idempotency_key: str | None = Header(
            default=None,
            alias="Idempotency-Key",
        ),
    ) -> JSONResponse:
        tenant = managed_tenant(session, context, tenant_id)
        key = require_idempotency_key(idempotency_key)
        digest = request_digest(payload)
        operation = f"access-key:create:{tenant_id}:{principal_id}"
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
                etag_resource_type="access_key",
                redacted_fields=("access_key",),
            )
        principal, _membership = managed_researcher(
            session,
            tenant_id,
            principal_id,
        )
        if (
            tenant.status != "active"
            or principal.status != "active"
            or not active_membership_exists(session, principal_id, tenant_id)
        ):
            raise HubError(
                409,
                "researcher_inactive",
                "Access Key creation requires an active researcher membership.",
            )
        access_key, raw_token = issue_access_key(
            session,
            context,
            tenant_id=tenant_id,
            principal_id=principal_id,
            label=payload.label,
            allowed_tools=payload.allowed_tools,
            expires_at=utc_now() + timedelta(seconds=payload.expires_in_seconds),
            request_limit=payload.request_limit,
            period_seconds=payload.period_seconds,
        )
        response_body = access_key_body(access_key, raw_token=raw_token)
        stored_body = access_key_body(access_key)
        append_mutation_audit(
            session,
            request,
            context,
            action="access_key:create",
            resource_type="access_key",
            resource_id=access_key.id,
            tenant_id=tenant_id,
            digest=digest,
            details={
                "principal_id": principal_id,
                "tool_count": len(access_key.allowed_tools),
            },
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
                    "access_key",
                    access_key.id,
                    access_key.version,
                )
            },
        )

    @router.patch("/tenants/{tenant_id}/access-keys/{access_key_id}")
    def update_access_key(
        tenant_id: str,
        access_key_id: str,
        payload: AccessKeyPatch,
        request: Request,
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
        if_match: str | None = Header(default=None, alias="If-Match"),
    ) -> JSONResponse:
        managed_tenant(session, context, tenant_id)
        access_key = access_key_in_tenant(session, tenant_id, access_key_id)
        require_current_etag(
            "access_key",
            access_key.id,
            access_key.version,
            if_match,
        )
        if access_key.revoked_at is not None:
            raise HubError(
                409,
                "access_key_revoked",
                "A revoked Access Key cannot be modified.",
            )
        next_tools = (
            payload.allowed_tools
            if payload.allowed_tools is not None
            else access_key.allowed_tools
        )
        validate_allowed_tools(session, tenant_id, next_tools)
        next_expires_at = (
            payload.expires_at
            if payload.expires_at is not None
            else access_key.expires_at
        )
        if next_expires_at is not None and _aware(next_expires_at) <= utc_now():
            raise HubError(
                409,
                "access_key_expiry_invalid",
                "Access Key expiry must be in the future.",
            )
        if "request_limit" in payload.model_fields_set:
            next_request_limit = payload.request_limit
            next_period_seconds = payload.period_seconds
        else:
            next_request_limit = access_key.request_limit
            next_period_seconds = access_key.period_seconds
        updated_id = session.scalar(
            update(AccessKey)
            .where(
                AccessKey.id == access_key.id,
                AccessKey.version == access_key.version,
            )
            .values(
                label=payload.label or access_key.label,
                allowed_tools=next_tools,
                request_limit=next_request_limit,
                period_seconds=next_period_seconds,
                expires_at=next_expires_at,
                version=access_key.version + 1,
                updated_at=utc_now(),
            )
            .returning(AccessKey.id)
        )
        require_version_update(updated_id)
        session.expire(access_key)
        session.refresh(access_key)
        digest = request_digest(payload)
        append_mutation_audit(
            session,
            request,
            context,
            action="access_key:update",
            resource_type="access_key",
            resource_id=access_key.id,
            tenant_id=tenant_id,
            digest=digest,
            details={"tool_count": len(access_key.allowed_tools)},
        )
        session.commit()
        return JSONResponse(
            content=access_key_body(access_key),
            headers={
                "ETag": resource_etag(
                    "access_key",
                    access_key.id,
                    access_key.version,
                )
            },
        )

    @router.post("/tenants/{tenant_id}/access-keys/{access_key_id}/rotate")
    def rotate_access_key(
        tenant_id: str,
        access_key_id: str,
        payload: AccessKeyRotate,
        request: Request,
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
        idempotency_key: str | None = Header(
            default=None,
            alias="Idempotency-Key",
        ),
    ) -> JSONResponse:
        tenant = managed_tenant(session, context, tenant_id)
        key = require_idempotency_key(idempotency_key)
        digest = request_digest(payload)
        operation = f"access-key:rotate:{tenant_id}:{access_key_id}"
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
                etag_resource_type="access_key",
                redacted_fields=("access_key",),
            )
        access_key = access_key_in_tenant(session, tenant_id, access_key_id)
        if (
            tenant.status != "active"
            or access_key.revoked_at is not None
            or not active_membership_exists(
                session,
                access_key.principal_id,
                tenant_id,
            )
        ):
            raise HubError(
                409,
                "access_key_inactive",
                "Only an active Access Key can be rotated.",
            )
        if access_key.expires_at is None:
            remaining_seconds = 31_536_000
        else:
            remaining_seconds = max(
                300,
                int((_aware(access_key.expires_at) - utc_now()).total_seconds()),
            )
        settings = AccessKeyCreate(
            label=payload.label or access_key.label,
            allowed_tools=access_key.allowed_tools,
            expires_in_seconds=payload.expires_in_seconds or remaining_seconds,
            request_limit=access_key.request_limit,
            period_seconds=access_key.period_seconds,
        )
        replacement, raw_token = issue_access_key(
            session,
            context,
            tenant_id=tenant_id,
            principal_id=access_key.principal_id,
            label=settings.label,
            allowed_tools=settings.allowed_tools,
            expires_at=utc_now() + timedelta(seconds=settings.expires_in_seconds),
            request_limit=settings.request_limit,
            period_seconds=settings.period_seconds,
        )
        access_key.revoked_at = utc_now()
        access_key.revoked_by_principal_id = context.principal_id
        access_key.revoke_reason = "rotated"
        access_key.version += 1
        response_body = access_key_body(replacement, raw_token=raw_token)
        stored_body = access_key_body(replacement)
        append_mutation_audit(
            session,
            request,
            context,
            action="access_key:rotate",
            resource_type="access_key",
            resource_id=replacement.id,
            tenant_id=tenant_id,
            digest=digest,
            details={"replaced_access_key_id": access_key.id},
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
                    "access_key",
                    replacement.id,
                    replacement.version,
                )
            },
        )

    @router.delete(
        "/tenants/{tenant_id}/access-keys/{access_key_id}",
        status_code=204,
    )
    def revoke_access_key(
        tenant_id: str,
        access_key_id: str,
        request: Request,
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
        if_match: str | None = Header(default=None, alias="If-Match"),
    ) -> Response:
        managed_tenant(session, context, tenant_id)
        access_key = access_key_in_tenant(session, tenant_id, access_key_id)
        require_current_etag(
            "access_key",
            access_key.id,
            access_key.version,
            if_match,
        )
        if access_key.revoked_at is not None:
            return Response(status_code=204)
        digest = request_digest(AccessKeyRotate(label=access_key.label))
        access_key.revoked_at = utc_now()
        access_key.revoked_by_principal_id = context.principal_id
        access_key.revoke_reason = "revoked_by_admin"
        access_key.version += 1
        append_mutation_audit(
            session,
            request,
            context,
            action="access_key:revoke",
            resource_type="access_key",
            resource_id=access_key.id,
            tenant_id=tenant_id,
            digest=digest,
        )
        session.commit()
        return Response(status_code=204)

    return router
