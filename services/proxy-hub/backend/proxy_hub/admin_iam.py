"""Tenant and platform identity administration routes."""

from collections.abc import Generator

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from proxy_hub.auth import AuthComponents
from proxy_hub.database import Database, session_scope
from proxy_hub.errors import HubError
from proxy_hub.models import (
    Membership,
    Principal,
    RoleBinding,
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
from proxy_hub.rbac import (
    AUDITOR,
    OPERATOR,
    PLATFORM_ADMIN,
    TENANT_ADMIN,
    AdminContext,
    require_platform_admin,
    require_tenant_mutation,
)
from proxy_hub.security import resource_etag

TENANT_ROLE_NAMES = frozenset({TENANT_ADMIN, OPERATOR, AUDITOR})
PLATFORM_ROLE_NAMES = frozenset({PLATFORM_ADMIN, AUDITOR})


class TeamCreate(BaseModel):
    """Tenant team creation input."""

    name: str = Field(min_length=1, max_length=200)


class TeamPatch(BaseModel):
    """Mutable team fields."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")

    @model_validator(mode="after")
    def require_change(self) -> "TeamPatch":
        if not self.model_fields_set:
            raise ValueError("At least one mutable field is required.")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("Team name cannot be null.")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("Team status cannot be null.")
        return self


class MembershipCreate(BaseModel):
    """Tenant membership creation input."""

    principal_id: str = Field(min_length=1, max_length=48)
    team_id: str | None = Field(default=None, min_length=1, max_length=48)


class MembershipPatch(BaseModel):
    """Mutable tenant membership fields."""

    team_id: str | None = Field(default=None, min_length=1, max_length=48)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")

    @model_validator(mode="after")
    def require_change(self) -> "MembershipPatch":
        if not self.model_fields_set:
            raise ValueError("At least one mutable field is required.")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("Membership status cannot be null.")
        return self


class RoleBindingCreate(BaseModel):
    """Role binding creation input."""

    principal_id: str = Field(min_length=1, max_length=48)
    role: str = Field(min_length=1, max_length=32)


class PrincipalPatch(BaseModel):
    """Mutable principal fields."""

    status: str = Field(pattern=r"^(active|disabled)$")


class RevocationInput(BaseModel):
    """Auditable resource revocation identity."""

    id: str
    version: int


def team_body(team: Team) -> dict[str, object]:
    """Serialize a team without ORM internals."""
    return {
        "id": team.id,
        "tenant_id": team.tenant_id,
        "name": team.name,
        "status": team.status,
        "version": team.version,
        "etag": resource_etag("team", team.id, team.version),
        "created_at": team.created_at.isoformat(),
        "updated_at": team.updated_at.isoformat(),
    }


def membership_body(membership: Membership) -> dict[str, object]:
    """Serialize a tenant membership."""
    return {
        "id": membership.id,
        "principal_id": membership.principal_id,
        "tenant_id": membership.tenant_id,
        "team_id": membership.team_id,
        "status": membership.status,
        "version": membership.version,
        "etag": resource_etag(
            "membership",
            membership.id,
            membership.version,
        ),
        "created_at": membership.created_at.isoformat(),
        "updated_at": membership.updated_at.isoformat(),
    }


def role_binding_body(binding: RoleBinding) -> dict[str, object]:
    """Serialize a role binding without exposing related identities."""
    return {
        "id": binding.id,
        "principal_id": binding.principal_id,
        "tenant_id": binding.tenant_id,
        "role": binding.role,
        "revoked_at": (
            binding.revoked_at.isoformat() if binding.revoked_at is not None else None
        ),
        "version": binding.version,
        "etag": resource_etag(
            "role_binding",
            binding.id,
            binding.version,
        ),
        "created_at": binding.created_at.isoformat(),
        "updated_at": binding.updated_at.isoformat(),
    }


def principal_body(principal: Principal) -> dict[str, object]:
    """Serialize a control-plane principal."""
    return {
        "id": principal.id,
        "issuer": principal.issuer,
        "subject": principal.subject,
        "email": principal.email,
        "display_name": principal.display_name,
        "status": principal.status,
        "version": principal.version,
        "etag": resource_etag(
            "principal",
            principal.id,
            principal.version,
        ),
        "created_at": principal.created_at.isoformat(),
        "updated_at": principal.updated_at.isoformat(),
    }


def build_iam_router(
    database: Database,
    auth: AuthComponents,
) -> APIRouter:
    """Create tenant and platform IAM administration routes."""
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

    def active_principal(session: Session, principal_id: str) -> Principal:
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
                "The requested principal is not active.",
            )
        return principal

    def team_in_tenant(
        session: Session,
        tenant_id: str,
        team_id: str,
    ) -> Team:
        team = session.scalar(
            select(Team).where(
                Team.id == team_id,
                Team.tenant_id == tenant_id,
            )
        )
        if team is None:
            raise HubError(
                404,
                "team_not_found",
                "The requested team is not available.",
            )
        return team

    def membership_in_tenant(
        session: Session,
        tenant_id: str,
        membership_id: str,
    ) -> Membership:
        membership = session.scalar(
            select(Membership).where(
                Membership.id == membership_id,
                Membership.tenant_id == tenant_id,
            )
        )
        if membership is None:
            raise HubError(
                404,
                "membership_not_found",
                "The requested membership is not available.",
            )
        return membership

    def require_active_membership(
        session: Session,
        tenant_id: str,
        principal_id: str,
    ) -> None:
        membership = session.scalar(
            select(Membership.id).where(
                Membership.tenant_id == tenant_id,
                Membership.principal_id == principal_id,
                Membership.status == "active",
            )
        )
        if membership is None:
            raise HubError(
                409,
                "membership_inactive",
                "The principal requires an active tenant membership.",
            )

    @router.get("/tenants/{tenant_id}/teams")
    def list_teams(
        tenant_id: str,
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        managed_tenant(session, context, tenant_id)
        teams = session.scalars(
            select(Team)
            .where(Team.tenant_id == tenant_id)
            .order_by(Team.created_at, Team.id)
        ).all()
        return {"items": [team_body(team) for team in teams]}

    @router.post("/tenants/{tenant_id}/teams")
    def create_team(
        tenant_id: str,
        payload: TeamCreate,
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
        operation = f"team:create:{tenant_id}"
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
                etag_resource_type="team",
            )
        if tenant.status != "active":
            raise HubError(
                409,
                "tenant_inactive",
                "New teams require an active tenant.",
            )
        team = Team(
            id=new_id("team"),
            tenant_id=tenant_id,
            name=payload.name,
        )
        session.add(team)
        session.flush()
        body = team_body(team)
        append_mutation_audit(
            session,
            request,
            context,
            action="team:create",
            resource_type="team",
            resource_id=team.id,
            tenant_id=tenant_id,
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
        session.commit()
        return JSONResponse(
            status_code=201,
            content=body,
            headers={"ETag": resource_etag("team", team.id, team.version)},
        )

    @router.patch("/tenants/{tenant_id}/teams/{team_id}")
    def update_team(
        tenant_id: str,
        team_id: str,
        payload: TeamPatch,
        request: Request,
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
        if_match: str | None = Header(default=None, alias="If-Match"),
    ) -> JSONResponse:
        managed_tenant(session, context, tenant_id)
        team = team_in_tenant(session, tenant_id, team_id)
        require_current_etag("team", team.id, team.version, if_match)
        next_name = payload.name if payload.name is not None else team.name
        next_status = payload.status if payload.status is not None else team.status
        updated_id = session.scalar(
            update(Team)
            .where(
                Team.id == team.id,
                Team.version == team.version,
            )
            .values(
                name=next_name,
                status=next_status,
                version=team.version + 1,
                updated_at=utc_now(),
            )
            .returning(Team.id)
        )
        require_version_update(updated_id)
        session.expire(team)
        session.refresh(team)
        digest = request_digest(payload)
        append_mutation_audit(
            session,
            request,
            context,
            action="team:update",
            resource_type="team",
            resource_id=team.id,
            tenant_id=tenant_id,
            digest=digest,
        )
        session.commit()
        return JSONResponse(
            content=team_body(team),
            headers={"ETag": resource_etag("team", team.id, team.version)},
        )

    @router.get("/tenants/{tenant_id}/memberships")
    def list_memberships(
        tenant_id: str,
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        managed_tenant(session, context, tenant_id)
        memberships = session.scalars(
            select(Membership)
            .where(Membership.tenant_id == tenant_id)
            .order_by(Membership.created_at, Membership.id)
        ).all()
        return {"items": [membership_body(membership) for membership in memberships]}

    @router.post("/tenants/{tenant_id}/memberships")
    def create_membership(
        tenant_id: str,
        payload: MembershipCreate,
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
        operation = f"membership:create:{tenant_id}"
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
                etag_resource_type="membership",
            )
        if tenant.status != "active":
            raise HubError(
                409,
                "tenant_inactive",
                "New memberships require an active tenant.",
            )
        active_principal(session, payload.principal_id)
        if payload.team_id is not None:
            team = team_in_tenant(session, tenant_id, payload.team_id)
            if team.status != "active":
                raise HubError(
                    409,
                    "team_inactive",
                    "New memberships require an active team.",
                )
        duplicate_filters = [
            Membership.tenant_id == tenant_id,
            Membership.principal_id == payload.principal_id,
        ]
        if payload.team_id is None:
            duplicate_filters.append(Membership.team_id.is_(None))
        else:
            duplicate_filters.append(Membership.team_id == payload.team_id)
        if session.scalar(select(Membership.id).where(*duplicate_filters)):
            raise HubError(
                409,
                "membership_exists",
                "The principal already has this tenant membership.",
            )
        membership = Membership(
            id=new_id("membership"),
            principal_id=payload.principal_id,
            tenant_id=tenant_id,
            team_id=payload.team_id,
        )
        session.add(membership)
        session.flush()
        body = membership_body(membership)
        append_mutation_audit(
            session,
            request,
            context,
            action="membership:create",
            resource_type="membership",
            resource_id=membership.id,
            tenant_id=tenant_id,
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
        session.commit()
        return JSONResponse(
            status_code=201,
            content=body,
            headers={
                "ETag": resource_etag(
                    "membership",
                    membership.id,
                    membership.version,
                )
            },
        )

    @router.patch(
        "/tenants/{tenant_id}/memberships/{membership_id}",
    )
    def update_membership(
        tenant_id: str,
        membership_id: str,
        payload: MembershipPatch,
        request: Request,
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
        if_match: str | None = Header(default=None, alias="If-Match"),
    ) -> JSONResponse:
        tenant = managed_tenant(session, context, tenant_id)
        membership = membership_in_tenant(
            session,
            tenant_id,
            membership_id,
        )
        require_current_etag(
            "membership",
            membership.id,
            membership.version,
            if_match,
        )
        if payload.status == "active":
            if tenant.status != "active":
                raise HubError(
                    409,
                    "tenant_inactive",
                    "Membership activation requires an active tenant.",
                )
            active_principal(session, membership.principal_id)
        if "team_id" in payload.model_fields_set and payload.team_id is not None:
            team = team_in_tenant(session, tenant_id, payload.team_id)
            if team.status != "active":
                raise HubError(
                    409,
                    "team_inactive",
                    "Membership assignment requires an active team.",
                )
        next_team_id = (
            payload.team_id
            if "team_id" in payload.model_fields_set
            else membership.team_id
        )
        next_status = (
            payload.status if payload.status is not None else membership.status
        )
        updated_id = session.scalar(
            update(Membership)
            .where(
                Membership.id == membership.id,
                Membership.version == membership.version,
            )
            .values(
                team_id=next_team_id,
                status=next_status,
                version=membership.version + 1,
                updated_at=utc_now(),
            )
            .returning(Membership.id)
        )
        require_version_update(updated_id)
        session.expire(membership)
        session.refresh(membership)
        digest = request_digest(payload)
        append_mutation_audit(
            session,
            request,
            context,
            action="membership:update",
            resource_type="membership",
            resource_id=membership.id,
            tenant_id=tenant_id,
            digest=digest,
        )
        session.commit()
        return JSONResponse(
            content=membership_body(membership),
            headers={
                "ETag": resource_etag(
                    "membership",
                    membership.id,
                    membership.version,
                )
            },
        )

    @router.delete(
        "/tenants/{tenant_id}/memberships/{membership_id}",
        status_code=204,
    )
    def disable_membership(
        tenant_id: str,
        membership_id: str,
        request: Request,
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
        if_match: str | None = Header(default=None, alias="If-Match"),
    ) -> Response:
        managed_tenant(session, context, tenant_id)
        membership = membership_in_tenant(
            session,
            tenant_id,
            membership_id,
        )
        require_current_etag(
            "membership",
            membership.id,
            membership.version,
            if_match,
        )
        if membership.status == "disabled":
            return Response(status_code=204)
        digest = request_digest(
            RevocationInput(id=membership.id, version=membership.version)
        )
        updated_id = session.scalar(
            update(Membership)
            .where(
                Membership.id == membership.id,
                Membership.version == membership.version,
            )
            .values(
                status="disabled",
                version=membership.version + 1,
                updated_at=utc_now(),
            )
            .returning(Membership.id)
        )
        require_version_update(updated_id)
        append_mutation_audit(
            session,
            request,
            context,
            action="membership:disable",
            resource_type="membership",
            resource_id=membership.id,
            tenant_id=tenant_id,
            digest=digest,
        )
        session.commit()
        return Response(status_code=204)

    @router.get("/tenants/{tenant_id}/role-bindings")
    def list_tenant_role_bindings(
        tenant_id: str,
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        managed_tenant(session, context, tenant_id)
        bindings = session.scalars(
            select(RoleBinding)
            .where(
                RoleBinding.tenant_id == tenant_id,
                RoleBinding.revoked_at.is_(None),
            )
            .order_by(RoleBinding.created_at, RoleBinding.id)
        ).all()
        return {"items": [role_binding_body(binding) for binding in bindings]}

    @router.post("/tenants/{tenant_id}/role-bindings")
    def create_tenant_role_binding(
        tenant_id: str,
        payload: RoleBindingCreate,
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
        operation = f"tenant-role-binding:create:{tenant_id}"
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
                etag_resource_type="role_binding",
            )
        if tenant.status != "active":
            raise HubError(
                409,
                "tenant_inactive",
                "New role bindings require an active tenant.",
            )
        if payload.role not in TENANT_ROLE_NAMES:
            raise HubError(
                400,
                "role_unknown",
                "The requested tenant role is not supported.",
            )
        active_principal(session, payload.principal_id)
        require_active_membership(session, tenant_id, payload.principal_id)
        existing_binding = session.scalar(
            select(RoleBinding).where(
                RoleBinding.principal_id == payload.principal_id,
                RoleBinding.tenant_id == tenant_id,
                RoleBinding.role == payload.role,
            )
        )
        if existing_binding is not None and existing_binding.revoked_at is None:
            raise HubError(
                409,
                "role_binding_exists",
                "The requested role binding already exists.",
            )
        if existing_binding is None:
            binding = RoleBinding(
                id=new_id("role"),
                principal_id=payload.principal_id,
                tenant_id=tenant_id,
                role=payload.role,
            )
            session.add(binding)
        else:
            binding = existing_binding
            updated_id = session.scalar(
                update(RoleBinding)
                .where(
                    RoleBinding.id == binding.id,
                    RoleBinding.version == binding.version,
                    RoleBinding.revoked_at.is_not(None),
                )
                .values(
                    revoked_at=None,
                    version=binding.version + 1,
                    updated_at=utc_now(),
                )
                .returning(RoleBinding.id)
            )
            require_version_update(updated_id)
            session.expire(binding)
            session.refresh(binding)
        session.flush()
        body = role_binding_body(binding)
        append_mutation_audit(
            session,
            request,
            context,
            action="role_binding:create",
            resource_type="role_binding",
            resource_id=binding.id,
            tenant_id=tenant_id,
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
        session.commit()
        return JSONResponse(
            status_code=201,
            content=body,
            headers={
                "ETag": resource_etag(
                    "role_binding",
                    binding.id,
                    binding.version,
                )
            },
        )

    @router.delete(
        "/tenants/{tenant_id}/role-bindings/{binding_id}",
        status_code=204,
    )
    def revoke_tenant_role_binding(
        tenant_id: str,
        binding_id: str,
        request: Request,
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
        if_match: str | None = Header(default=None, alias="If-Match"),
    ) -> Response:
        managed_tenant(session, context, tenant_id)
        binding = session.scalar(
            select(RoleBinding).where(
                RoleBinding.id == binding_id,
                RoleBinding.tenant_id == tenant_id,
                RoleBinding.revoked_at.is_(None),
            )
        )
        if binding is None:
            raise HubError(
                404,
                "role_binding_not_found",
                "The requested role binding is not available.",
            )
        require_current_etag(
            "role_binding",
            binding.id,
            binding.version,
            if_match,
        )
        digest = request_digest(RevocationInput(id=binding.id, version=binding.version))
        updated_id = session.scalar(
            update(RoleBinding)
            .where(
                RoleBinding.id == binding.id,
                RoleBinding.version == binding.version,
                RoleBinding.revoked_at.is_(None),
            )
            .values(
                revoked_at=utc_now(),
                version=binding.version + 1,
                updated_at=utc_now(),
            )
            .returning(RoleBinding.id)
        )
        require_version_update(updated_id)
        append_mutation_audit(
            session,
            request,
            context,
            action="role_binding:revoke",
            resource_type="role_binding",
            resource_id=binding.id,
            tenant_id=tenant_id,
            digest=digest,
        )
        session.commit()
        return Response(status_code=204)

    @router.get("/principals")
    def list_principals(
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        require_platform_admin(context)
        principals = session.scalars(
            select(Principal).order_by(Principal.created_at, Principal.id)
        ).all()
        return {"items": [principal_body(principal) for principal in principals]}

    @router.patch("/principals/{principal_id}")
    def update_principal(
        principal_id: str,
        payload: PrincipalPatch,
        request: Request,
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
        if_match: str | None = Header(default=None, alias="If-Match"),
    ) -> JSONResponse:
        require_platform_admin(context)
        principal = session.get(Principal, principal_id)
        if principal is None:
            raise HubError(
                404,
                "principal_not_found",
                "The requested principal is not available.",
            )
        require_current_etag(
            "principal",
            principal.id,
            principal.version,
            if_match,
        )
        if principal.id == context.principal_id and payload.status == "disabled":
            raise HubError(
                409,
                "principal_self_disable_denied",
                "The current principal cannot disable itself.",
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
            action="principal:update",
            resource_type="principal",
            resource_id=principal.id,
            tenant_id=None,
            digest=digest,
        )
        session.commit()
        return JSONResponse(
            content=principal_body(principal),
            headers={
                "ETag": resource_etag(
                    "principal",
                    principal.id,
                    principal.version,
                )
            },
        )

    @router.get("/platform-role-bindings")
    def list_platform_role_bindings(
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        require_platform_admin(context)
        bindings = session.scalars(
            select(RoleBinding)
            .where(
                RoleBinding.tenant_id.is_(None),
                RoleBinding.revoked_at.is_(None),
            )
            .order_by(RoleBinding.created_at, RoleBinding.id)
        ).all()
        return {"items": [role_binding_body(binding) for binding in bindings]}

    @router.post("/platform-role-bindings")
    def create_platform_role_binding(
        payload: RoleBindingCreate,
        request: Request,
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
        idempotency_key: str | None = Header(
            default=None,
            alias="Idempotency-Key",
        ),
    ) -> JSONResponse:
        require_platform_admin(context)
        if payload.role not in PLATFORM_ROLE_NAMES:
            raise HubError(
                400,
                "role_unknown",
                "The requested platform role is not supported.",
            )
        key = require_idempotency_key(idempotency_key)
        digest = request_digest(payload)
        operation = "platform-role-binding:create"
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
                etag_resource_type="role_binding",
            )
        active_principal(session, payload.principal_id)
        existing_binding = session.scalar(
            select(RoleBinding).where(
                RoleBinding.principal_id == payload.principal_id,
                RoleBinding.tenant_id.is_(None),
                RoleBinding.role == payload.role,
            )
        )
        if existing_binding is not None and existing_binding.revoked_at is None:
            raise HubError(
                409,
                "role_binding_exists",
                "The requested role binding already exists.",
            )
        if existing_binding is None:
            binding = RoleBinding(
                id=new_id("role"),
                principal_id=payload.principal_id,
                tenant_id=None,
                role=payload.role,
            )
            session.add(binding)
        else:
            binding = existing_binding
            updated_id = session.scalar(
                update(RoleBinding)
                .where(
                    RoleBinding.id == binding.id,
                    RoleBinding.version == binding.version,
                    RoleBinding.revoked_at.is_not(None),
                )
                .values(
                    revoked_at=None,
                    version=binding.version + 1,
                    updated_at=utc_now(),
                )
                .returning(RoleBinding.id)
            )
            require_version_update(updated_id)
            session.expire(binding)
            session.refresh(binding)
        session.flush()
        body = role_binding_body(binding)
        append_mutation_audit(
            session,
            request,
            context,
            action="role_binding:create",
            resource_type="role_binding",
            resource_id=binding.id,
            tenant_id=None,
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
        session.commit()
        return JSONResponse(
            status_code=201,
            content=body,
            headers={
                "ETag": resource_etag(
                    "role_binding",
                    binding.id,
                    binding.version,
                )
            },
        )

    @router.delete(
        "/platform-role-bindings/{binding_id}",
        status_code=204,
    )
    def revoke_platform_role_binding(
        binding_id: str,
        request: Request,
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
        if_match: str | None = Header(default=None, alias="If-Match"),
    ) -> Response:
        require_platform_admin(context)
        binding = session.scalar(
            select(RoleBinding).where(
                RoleBinding.id == binding_id,
                RoleBinding.tenant_id.is_(None),
                RoleBinding.revoked_at.is_(None),
            )
        )
        if binding is None:
            raise HubError(
                404,
                "role_binding_not_found",
                "The requested role binding is not available.",
            )
        require_current_etag(
            "role_binding",
            binding.id,
            binding.version,
            if_match,
        )
        if (
            binding.principal_id == context.principal_id
            and binding.role == PLATFORM_ADMIN
        ):
            raise HubError(
                409,
                "platform_role_self_revoke_denied",
                "The current platform administrator cannot revoke itself.",
            )
        digest = request_digest(RevocationInput(id=binding.id, version=binding.version))
        updated_id = session.scalar(
            update(RoleBinding)
            .where(
                RoleBinding.id == binding.id,
                RoleBinding.version == binding.version,
                RoleBinding.revoked_at.is_(None),
            )
            .values(
                revoked_at=utc_now(),
                version=binding.version + 1,
                updated_at=utc_now(),
            )
            .returning(RoleBinding.id)
        )
        require_version_update(updated_id)
        append_mutation_audit(
            session,
            request,
            context,
            action="role_binding:revoke",
            resource_type="role_binding",
            resource_id=binding.id,
            tenant_id=None,
            digest=digest,
        )
        session.commit()
        return Response(status_code=204)

    return router
