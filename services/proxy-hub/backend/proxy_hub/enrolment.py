"""One-time tenant enrolment token administration."""

from collections.abc import Generator
from datetime import timedelta

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from proxy_hub.auth import AuthComponents
from proxy_hub.database import Database, session_scope
from proxy_hub.errors import HubError
from proxy_hub.models import (
    EnrolmentToken,
    Membership,
    Principal,
    Team,
    Tenant,
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


class EnrolmentCreate(BaseModel):
    """One-time enrolment token creation input."""

    principal_id: str = Field(min_length=1, max_length=48)
    requested_scopes: list[str] = Field(min_length=1, max_length=16)
    expires_in_seconds: int = Field(ge=300, le=604800)

    @field_validator("requested_scopes")
    @classmethod
    def validate_scopes(cls, value: list[str]) -> list[str]:
        try:
            return list(validate_tool_policy(value))
        except InvalidToolPolicy as error:
            raise ValueError("requested scopes contain unknown tools") from error


class EnrolmentRevocation(BaseModel):
    """Auditable enrolment revocation identity."""

    id: str


def enrolment_body(
    enrolment: EnrolmentToken,
    *,
    raw_token: str | None = None,
) -> dict[str, object]:
    """Serialize enrolment metadata without its stored digest."""
    return {
        "id": enrolment.id,
        "enrolment_token": raw_token,
        "principal_id": enrolment.principal_id,
        "tenant_id": enrolment.tenant_id,
        "requested_scopes": enrolment.requested_scopes,
        "expires_at": enrolment.expires_at.isoformat(),
        "consumed_at": (
            enrolment.consumed_at.isoformat()
            if enrolment.consumed_at is not None
            else None
        ),
        "revoked_at": (
            enrolment.revoked_at.isoformat()
            if enrolment.revoked_at is not None
            else None
        ),
        "created_by_principal_id": enrolment.created_by_principal_id,
        "version": enrolment.version,
        "etag": resource_etag(
            "enrolment",
            enrolment.id,
            enrolment.version,
        ),
        "created_at": enrolment.created_at.isoformat(),
    }


def build_enrolment_router(
    database: Database,
    auth: AuthComponents,
) -> APIRouter:
    """Create tenant enrolment administration routes."""
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

    def require_eligible_principal(
        session: Session,
        tenant_id: str,
        principal_id: str,
    ) -> Principal:
        principal = session.get(Principal, principal_id)
        if principal is None:
            raise HubError(
                404,
                "principal_not_found",
                "The requested principal is not available.",
            )
        if principal.status != "active":
            raise HubError(
                409,
                "principal_inactive",
                "Enrolment requires an active principal.",
            )
        memberships = session.scalars(
            select(Membership).where(
                Membership.tenant_id == tenant_id,
                Membership.principal_id == principal_id,
                Membership.status == "active",
            )
        ).all()
        for membership in memberships:
            if membership.team_id is None:
                return principal
            team = session.scalar(
                select(Team).where(
                    Team.id == membership.team_id,
                    Team.tenant_id == tenant_id,
                    Team.status == "active",
                )
            )
            if team is not None:
                return principal
        raise HubError(
            409,
            "membership_inactive",
            "Enrolment requires an active tenant membership.",
        )

    @router.get("/tenants/{tenant_id}/enrolments")
    def list_enrolments(
        tenant_id: str,
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        managed_tenant(session, context, tenant_id)
        enrolments = session.scalars(
            select(EnrolmentToken)
            .where(EnrolmentToken.tenant_id == tenant_id)
            .order_by(EnrolmentToken.created_at.desc(), EnrolmentToken.id)
        ).all()
        return {"items": [enrolment_body(enrolment) for enrolment in enrolments]}

    @router.post("/tenants/{tenant_id}/enrolments")
    def create_enrolment(
        tenant_id: str,
        payload: EnrolmentCreate,
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
        operation = f"enrolment:create:{tenant_id}"
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
                etag_resource_type="enrolment",
                redacted_fields=("enrolment_token",),
            )
        if tenant.status != "active":
            raise HubError(
                409,
                "tenant_inactive",
                "Enrolment requires an active tenant.",
            )
        require_eligible_principal(
            session,
            tenant_id,
            payload.principal_id,
        )
        raw_token = new_token()
        enrolment = EnrolmentToken(
            id=new_id("enrol"),
            token_digest=digest_token(raw_token),
            principal_id=payload.principal_id,
            tenant_id=tenant_id,
            requested_scopes=payload.requested_scopes,
            expires_at=utc_now() + timedelta(seconds=payload.expires_in_seconds),
            created_by_principal_id=context.principal_id,
        )
        session.add(enrolment)
        session.flush()
        response_body = enrolment_body(enrolment, raw_token=raw_token)
        stored_body = enrolment_body(enrolment)
        append_mutation_audit(
            session,
            request,
            context,
            action="enrolment:create",
            resource_type="enrolment",
            resource_id=enrolment.id,
            tenant_id=tenant_id,
            digest=digest,
            details={
                "principal_id": payload.principal_id,
                "scope_count": len(payload.requested_scopes),
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
                    "enrolment",
                    enrolment.id,
                    enrolment.version,
                )
            },
        )

    @router.delete(
        "/tenants/{tenant_id}/enrolments/{enrolment_id}",
        status_code=204,
    )
    def revoke_enrolment(
        tenant_id: str,
        enrolment_id: str,
        request: Request,
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
        if_match: str | None = Header(default=None, alias="If-Match"),
    ) -> Response:
        managed_tenant(session, context, tenant_id)
        enrolment = session.scalar(
            select(EnrolmentToken).where(
                EnrolmentToken.id == enrolment_id,
                EnrolmentToken.tenant_id == tenant_id,
            )
        )
        if enrolment is None:
            raise HubError(
                404,
                "enrolment_not_found",
                "The requested enrolment is not available.",
            )
        if if_match is None:
            require_current_etag(
                "enrolment",
                enrolment.id,
                enrolment.version,
                if_match,
            )
        if enrolment.revoked_at is not None:
            return Response(status_code=204)
        require_current_etag(
            "enrolment",
            enrolment.id,
            enrolment.version,
            if_match,
        )
        digest = request_digest(EnrolmentRevocation(id=enrolment.id))
        updated_id = session.scalar(
            update(EnrolmentToken)
            .where(
                EnrolmentToken.id == enrolment.id,
                EnrolmentToken.version == enrolment.version,
                EnrolmentToken.revoked_at.is_(None),
            )
            .values(
                revoked_at=utc_now(),
                version=enrolment.version + 1,
            )
            .returning(EnrolmentToken.id)
        )
        require_version_update(updated_id)
        append_mutation_audit(
            session,
            request,
            context,
            action="enrolment:revoke",
            resource_type="enrolment",
            resource_id=enrolment.id,
            tenant_id=tenant_id,
            digest=digest,
        )
        session.commit()
        return Response(status_code=204)

    return router
