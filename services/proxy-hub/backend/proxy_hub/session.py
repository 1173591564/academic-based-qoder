"""DSH session capability issuance."""

from collections.abc import Generator
from datetime import datetime, timedelta
from typing import NoReturn

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from proxy_hub.audit import AuditEntry, append_audit_event
from proxy_hub.capabilities import authenticate_capability
from proxy_hub.config import Settings
from proxy_hub.database import Database, session_scope
from proxy_hub.eligibility import active_membership_exists
from proxy_hub.errors import HubError, request_id
from proxy_hub.models import (
    DshCapability,
    EnrolmentToken,
    McpSessionAffinity,
    Principal,
    QuotaPolicy,
    QuotaWindow,
    Tenant,
    new_id,
    utc_now,
)
from proxy_hub.policy import InvalidToolPolicy, validate_tool_policy
from proxy_hub.quota import quota_window_start, remaining_requests
from proxy_hub.security import digest_token, new_token


class SessionCreate(BaseModel):
    """One-time enrolment exchange input."""

    enrolment_token: str = Field(min_length=1, max_length=512)
    session_label: str | None = Field(default=None, min_length=1, max_length=200)


def deny_session(
    session: Session,
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    reason: str,
    principal_id: str | None = None,
    tenant_id: str | None = None,
    enrolment_id: str | None = None,
) -> NoReturn:
    """Commit a minimized denial audit before rejecting session issuance."""
    append_audit_event(
        session,
        AuditEntry(
            request_id=request_id(request),
            principal_id=principal_id,
            tenant_id=tenant_id,
            action="session:create",
            resource_type="dsh_capability",
            outcome="rejected",
            decision="deny",
            details={
                "authentication_method": "enrolment",
                "enrolment_id": enrolment_id,
                "reason": reason,
            },
        ),
    )
    session.commit()
    raise HubError(status_code, code, message)


def quota_body(
    session: Session,
    tenant_id: str,
    at: datetime,
) -> dict[str, object]:
    """Return current quota metadata without reserving a request."""
    policy = session.get(QuotaPolicy, tenant_id)
    if policy is None:
        return {"class": "unconfigured", "remaining": None}
    window_start = quota_window_start(at, policy.period_seconds)
    window = session.get(
        QuotaWindow,
        (tenant_id, window_start, policy.period_seconds),
    )
    reserved_count = window.reserved_count if window is not None else 0
    return {
        "class": policy.quota_class,
        "remaining": remaining_requests(policy.request_limit, reserved_count),
    }


def build_session_router(
    database: Database,
    settings: Settings,
) -> APIRouter:
    """Create the public DSH session exchange route."""
    router = APIRouter()

    def get_session() -> Generator[Session, None, None]:
        yield from session_scope(database)

    @router.post("/v1/session")
    def create_session(
        payload: SessionCreate,
        request: Request,
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        now = utc_now()
        enrolment = session.scalar(
            select(EnrolmentToken).where(
                EnrolmentToken.token_digest == digest_token(payload.enrolment_token),
                EnrolmentToken.consumed_at.is_(None),
                EnrolmentToken.revoked_at.is_(None),
                EnrolmentToken.expires_at > now,
            )
        )
        if enrolment is None:
            deny_session(
                session,
                request,
                status_code=401,
                code="invalid_credential",
                message="The enrolment credential is invalid or unavailable.",
                reason="credential_unavailable",
            )

        principal = session.get(Principal, enrolment.principal_id)
        tenant = session.get(Tenant, enrolment.tenant_id)
        if (
            principal is None
            or principal.status != "active"
            or tenant is None
            or tenant.status != "active"
            or not active_membership_exists(
                session,
                enrolment.principal_id,
                enrolment.tenant_id,
            )
        ):
            deny_session(
                session,
                request,
                status_code=403,
                code="session_denied",
                message="The enrolment is not authorized for an active tenant.",
                reason="subject_inactive",
                principal_id=enrolment.principal_id,
                tenant_id=enrolment.tenant_id,
                enrolment_id=enrolment.id,
            )
        try:
            scopes = list(validate_tool_policy(enrolment.requested_scopes))
        except InvalidToolPolicy:
            deny_session(
                session,
                request,
                status_code=403,
                code="session_denied",
                message="The enrolment contains an invalid scope assignment.",
                reason="scope_invalid",
                principal_id=enrolment.principal_id,
                tenant_id=enrolment.tenant_id,
                enrolment_id=enrolment.id,
            )
        if not scopes:
            deny_session(
                session,
                request,
                status_code=403,
                code="session_denied",
                message="The enrolment contains no usable scopes.",
                reason="scope_empty",
                principal_id=enrolment.principal_id,
                tenant_id=enrolment.tenant_id,
                enrolment_id=enrolment.id,
            )

        consumed_id = session.scalar(
            update(EnrolmentToken)
            .where(
                EnrolmentToken.id == enrolment.id,
                EnrolmentToken.version == enrolment.version,
                EnrolmentToken.consumed_at.is_(None),
                EnrolmentToken.revoked_at.is_(None),
                EnrolmentToken.expires_at > now,
            )
            .values(
                consumed_at=now,
                version=enrolment.version + 1,
            )
            .returning(EnrolmentToken.id)
            .execution_options(synchronize_session=False)
        )
        if consumed_id is None:
            deny_session(
                session,
                request,
                status_code=401,
                code="invalid_credential",
                message="The enrolment credential is invalid or unavailable.",
                reason="credential_raced",
                principal_id=enrolment.principal_id,
                tenant_id=enrolment.tenant_id,
                enrolment_id=enrolment.id,
            )

        raw_capability = new_token()
        capability = DshCapability(
            id=new_id("cap"),
            token_digest=digest_token(raw_capability),
            principal_id=principal.id,
            tenant_id=tenant.id,
            scopes=scopes,
            issued_from_enrolment_id=enrolment.id,
            session_label=payload.session_label,
            expires_at=now + timedelta(seconds=settings.capability_ttl_seconds),
        )
        session.add(capability)
        quota = quota_body(session, tenant.id, now)
        append_audit_event(
            session,
            AuditEntry(
                request_id=request_id(request),
                principal_id=principal.id,
                tenant_id=tenant.id,
                capability_id=capability.id,
                action="session:create",
                resource_type="dsh_capability",
                resource_id=capability.id,
                outcome="accepted",
                decision="permit",
                details={
                    "authentication_method": "enrolment",
                    "enrolment_id": enrolment.id,
                    "scope_count": len(scopes),
                },
            ),
        )
        session.commit()
        return JSONResponse(
            status_code=201,
            content={
                "session_token": raw_capability,
                "session_id": capability.id,
                "expires_at": capability.expires_at.isoformat(),
                "subject": {"user_id": principal.id},
                "tenant": {"tenant_id": tenant.id},
                "scopes": scopes,
                "quota": quota,
            },
            headers={
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        )

    @router.delete("/v1/session", status_code=204)
    def revoke_session(
        request: Request,
        session: Session = Depends(get_session),
    ) -> Response:
        context = authenticate_capability(
            session,
            request.headers.get("authorization"),
        )
        capability = session.get(DshCapability, context.capability_id)
        if capability is None:
            raise HubError(
                401,
                "invalid_credential",
                "A valid DSH session capability is required.",
            )
        revoked_at = utc_now()
        revoked_id = session.scalar(
            update(DshCapability)
            .where(
                DshCapability.id == capability.id,
                DshCapability.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
            .returning(DshCapability.id)
        )
        if revoked_id is None:
            raise HubError(
                401,
                "invalid_credential",
                "A valid DSH session capability is required.",
            )
        session.execute(
            delete(McpSessionAffinity).where(
                McpSessionAffinity.capability_id == capability.id
            )
        )
        append_audit_event(
            session,
            AuditEntry(
                request_id=request_id(request),
                principal_id=context.principal_id,
                tenant_id=context.tenant_id,
                capability_id=context.capability_id,
                action="session:revoke",
                resource_type="dsh_capability",
                resource_id=context.capability_id,
                outcome="accepted",
                decision="permit",
                details={"reason": "holder_revoked"},
            ),
        )
        session.commit()
        return Response(
            status_code=204,
            headers={
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        )

    return router
