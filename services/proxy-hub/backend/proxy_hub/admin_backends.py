"""Scholar backend registry administration."""

from collections.abc import Generator
from datetime import timedelta

import httpx
from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from proxy_hub.audit import AuditEntry, append_audit_event
from proxy_hub.auth import AuthComponents
from proxy_hub.backend_probe import probe_scholar_backend
from proxy_hub.config import Settings
from proxy_hub.database import Database, session_scope
from proxy_hub.errors import HubError, request_id
from proxy_hub.mcp_transport import validated_backend_url
from proxy_hub.models import ScholarBackend, TenantRoute, new_id, utc_now
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
from proxy_hub.rbac import OPERATOR, AdminContext, require_platform_admin
from proxy_hub.secrets import (
    SecretResolutionError,
    SecretResolver,
    validate_secret_reference,
)
from proxy_hub.security import resource_etag


class BackendCreate(BaseModel):
    """Scholar backend registration input."""

    name: str = Field(min_length=1, max_length=200)
    base_url: str = Field(min_length=1, max_length=2_048)
    corpus_version: str = Field(min_length=1, max_length=128)
    credential_ref: str = Field(min_length=1, max_length=512)
    credential_version: str | None = Field(default=None, max_length=128)


class BackendPatch(BaseModel):
    """Mutable backend registration fields."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    base_url: str | None = Field(default=None, min_length=1, max_length=2_048)
    corpus_version: str | None = Field(default=None, min_length=1, max_length=128)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")

    @model_validator(mode="after")
    def require_change(self) -> "BackendPatch":
        if (
            self.name is None
            and self.base_url is None
            and self.corpus_version is None
            and self.status is None
        ):
            raise ValueError("at least one mutable field is required")
        return self


class CredentialRotation(BaseModel):
    """New deployer-owned credential reference metadata."""

    credential_ref: str = Field(min_length=1, max_length=512)
    credential_version: str | None = Field(default=None, max_length=128)


def _safe_capacity(capacity: dict[str, object]) -> dict[str, object]:
    keys = (
        "parsed_papers",
        "vector_chunks",
        "graph_built_at",
        "synchronized_at",
        "workspace_isolation",
    )
    return {key: capacity[key] for key in keys if key in capacity}


def backend_body(backend: ScholarBackend) -> dict[str, object]:
    """Serialize a backend without exposing a credential reference or value."""
    return {
        "id": backend.id,
        "name": backend.name,
        "base_url": backend.base_url,
        "corpus_version": backend.corpus_version,
        "status": backend.status,
        "capacity": _safe_capacity(backend.capacity),
        "credential": {
            "configured": True,
            "version": backend.credential_version,
            "rotated_at": (
                backend.credential_rotated_at.isoformat()
                if backend.credential_rotated_at is not None
                else None
            ),
        },
        "probe": {
            "observed_at": (
                backend.last_probe_at.isoformat()
                if backend.last_probe_at is not None
                else None
            ),
            "ready": backend.last_probe_ready,
            "reason": backend.last_probe_reason,
        },
        "version": backend.version,
        "created_at": backend.created_at.isoformat(),
        "updated_at": backend.updated_at.isoformat(),
    }


def _visible_backend_ids(
    session: Session,
    context: AdminContext,
) -> set[str] | None:
    if context.is_platform_admin:
        return None
    if not context.tenant_ids:
        return set()
    return set(
        session.scalars(
            select(TenantRoute.backend_id).where(
                TenantRoute.tenant_id.in_(context.tenant_ids)
            )
        ).all()
    )


def _require_backend_read(
    session: Session,
    context: AdminContext,
    backend_id: str,
) -> ScholarBackend:
    visible_ids = _visible_backend_ids(session, context)
    backend = session.get(ScholarBackend, backend_id)
    if backend is None or (visible_ids is not None and backend.id not in visible_ids):
        raise HubError(404, "backend_not_found", "The backend does not exist.")
    return backend


def _require_backend_probe(
    session: Session,
    context: AdminContext,
    backend_id: str,
) -> ScholarBackend:
    backend = _require_backend_read(session, context, backend_id)
    if context.is_platform_admin:
        return backend
    operator_tenants = {
        grant.tenant_id
        for grant in context.grants
        if grant.role == OPERATOR and grant.tenant_id is not None
    }
    allowed = session.scalar(
        select(TenantRoute.tenant_id).where(
            TenantRoute.backend_id == backend.id,
            TenantRoute.status == "active",
            TenantRoute.tenant_id.in_(operator_tenants),
        )
    )
    if allowed is None:
        raise HubError(
            403,
            "backend_probe_denied",
            "This operation requires the operator role.",
        )
    return backend


def _validate_registration(
    base_url: str,
    credential_ref: str,
    settings: Settings,
) -> None:
    try:
        validated_backend_url(
            base_url,
            production=settings.environment == "production",
        )
    except HubError as error:
        raise HubError(
            400,
            "backend_url_invalid",
            "The backend URL is invalid.",
        ) from error
    try:
        validate_secret_reference(credential_ref)
    except SecretResolutionError as error:
        raise HubError(
            400,
            "credential_reference_invalid",
            "The credential reference is invalid.",
        ) from error


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


def build_backend_router(
    database: Database,
    auth: AuthComponents,
    settings: Settings,
    http_client: httpx.AsyncClient,
    secret_resolver: SecretResolver,
) -> APIRouter:
    """Build backend registry routes bound to application resources."""
    router = APIRouter()

    def get_session() -> Generator[Session, None, None]:
        yield from session_scope(database)

    @router.get("/backends")
    def list_backends(
        cursor: str | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        visible_ids = _visible_backend_ids(session, context)
        if visible_ids == set():
            return {"items": [], "next_cursor": None}
        query = select(ScholarBackend).order_by(ScholarBackend.id).limit(limit + 1)
        if cursor is not None:
            query = query.where(ScholarBackend.id > cursor)
        if visible_ids is not None:
            query = query.where(ScholarBackend.id.in_(visible_ids))
        backends = list(session.scalars(query).all())
        return {
            "items": [backend_body(backend) for backend in backends[:limit]],
            "next_cursor": (backends[limit - 1].id if len(backends) > limit else None),
        }

    @router.post("/backends")
    def create_backend(
        payload: BackendCreate,
        request: Request,
        idempotency_key: str | None = Header(
            default=None,
            alias="Idempotency-Key",
        ),
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        require_platform_admin(context)
        _validate_registration(payload.base_url, payload.credential_ref, settings)
        key = require_idempotency_key(idempotency_key)
        digest = request_digest(payload)
        operation = "backend:create"
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
                etag_resource_type="backend",
            )
        if session.scalar(
            select(ScholarBackend.id).where(ScholarBackend.name == payload.name)
        ):
            raise HubError(
                409,
                "backend_name_conflict",
                "A backend with this name already exists.",
            )
        backend = ScholarBackend(
            id=new_id("backend"),
            name=payload.name,
            base_url=payload.base_url,
            corpus_version=payload.corpus_version,
            credential_ref=payload.credential_ref,
            credential_version=payload.credential_version,
            credential_rotated_at=utc_now(),
            status="disabled",
            last_probe_reason="not_probed",
        )
        session.add(backend)
        session.flush()
        body = backend_body(backend)
        append_mutation_audit(
            session,
            request,
            context,
            action=operation,
            resource_type="scholar_backend",
            resource_id=backend.id,
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
        return JSONResponse(
            status_code=201,
            content=body,
            headers={"ETag": resource_etag("backend", backend.id, backend.version)},
        )

    @router.get("/backends/{backend_id}")
    def get_backend(
        backend_id: str,
        context: AdminContext = Depends(auth.admin_context),
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        backend = _require_backend_read(session, context, backend_id)
        return JSONResponse(
            content=backend_body(backend),
            headers={"ETag": resource_etag("backend", backend.id, backend.version)},
        )

    @router.patch("/backends/{backend_id}")
    def update_backend(
        backend_id: str,
        payload: BackendPatch,
        request: Request,
        if_match: str | None = Header(default=None, alias="If-Match"),
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        require_platform_admin(context)
        backend = _require_backend_read(session, context, backend_id)
        require_current_etag("backend", backend.id, backend.version, if_match)
        next_name = payload.name if payload.name is not None else backend.name
        next_base_url = (
            payload.base_url if payload.base_url is not None else backend.base_url
        )
        next_corpus = (
            payload.corpus_version
            if payload.corpus_version is not None
            else backend.corpus_version
        )
        next_status = payload.status if payload.status is not None else backend.status
        _validate_registration(next_base_url, backend.credential_ref, settings)
        conflicting_id = session.scalar(
            select(ScholarBackend.id).where(
                ScholarBackend.name == next_name,
                ScholarBackend.id != backend.id,
            )
        )
        if conflicting_id is not None:
            raise HubError(
                409,
                "backend_name_conflict",
                "A backend with this name already exists.",
            )
        invalidates_probe = (
            next_base_url != backend.base_url or next_corpus != backend.corpus_version
        )
        if next_status == "active" and (
            invalidates_probe or not _probe_is_fresh(backend, settings)
        ):
            raise HubError(
                409,
                "backend_probe_required",
                "A current successful readiness probe is required.",
            )
        values: dict[str, object] = {
            "name": next_name,
            "base_url": next_base_url,
            "corpus_version": next_corpus,
            "status": next_status,
            "version": backend.version + 1,
            "updated_at": utc_now(),
        }
        if invalidates_probe:
            values.update(
                {
                    "last_probe_ready": False,
                    "last_probe_reason": "configuration_changed",
                }
            )
        updated_id = session.scalar(
            update(ScholarBackend)
            .where(
                ScholarBackend.id == backend.id,
                ScholarBackend.version == backend.version,
            )
            .values(**values)
            .returning(ScholarBackend.id)
        )
        require_version_update(updated_id)
        session.expire(backend)
        session.refresh(backend)
        append_mutation_audit(
            session,
            request,
            context,
            action="backend:update",
            resource_type="scholar_backend",
            resource_id=backend.id,
            tenant_id=None,
            digest=request_digest(payload),
        )
        return JSONResponse(
            content=backend_body(backend),
            headers={"ETag": resource_etag("backend", backend.id, backend.version)},
        )

    @router.post("/backends/{backend_id}:rotate-credential")
    def rotate_backend_credential(
        backend_id: str,
        payload: CredentialRotation,
        request: Request,
        if_match: str | None = Header(default=None, alias="If-Match"),
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        require_platform_admin(context)
        backend = _require_backend_read(session, context, backend_id)
        require_current_etag("backend", backend.id, backend.version, if_match)
        _validate_registration(backend.base_url, payload.credential_ref, settings)
        updated_id = session.scalar(
            update(ScholarBackend)
            .where(
                ScholarBackend.id == backend.id,
                ScholarBackend.version == backend.version,
            )
            .values(
                credential_ref=payload.credential_ref,
                credential_version=payload.credential_version,
                credential_rotated_at=utc_now(),
                last_probe_ready=False,
                last_probe_reason="credential_rotated",
                version=backend.version + 1,
                updated_at=utc_now(),
            )
            .returning(ScholarBackend.id)
        )
        require_version_update(updated_id)
        session.expire(backend)
        session.refresh(backend)
        append_mutation_audit(
            session,
            request,
            context,
            action="backend:rotate_credential",
            resource_type="scholar_backend",
            resource_id=backend.id,
            tenant_id=None,
            digest=request_digest(payload),
            details={"credential_version": payload.credential_version},
        )
        return JSONResponse(
            content=backend_body(backend),
            headers={"ETag": resource_etag("backend", backend.id, backend.version)},
        )

    @router.post("/backends/{backend_id}:probe")
    async def probe_backend(
        backend_id: str,
        request: Request,
        context: AdminContext = Depends(auth.mutation_context),
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        backend = _require_backend_probe(session, context, backend_id)
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
        values: dict[str, object] = {
            "last_probe_at": utc_now(),
            "last_probe_ready": result.ready,
            "last_probe_reason": result.reason,
            "capacity": result.capacity if result.ready else {},
            "version": backend.version + 1,
            "updated_at": utc_now(),
        }
        updated_id = session.scalar(
            update(ScholarBackend)
            .where(
                ScholarBackend.id == backend.id,
                ScholarBackend.version == backend.version,
            )
            .values(**values)
            .returning(ScholarBackend.id)
        )
        require_version_update(updated_id)
        session.expire(backend)
        session.refresh(backend)
        append_audit_event(
            session,
            AuditEntry(
                request_id=request_id(request),
                principal_id=context.principal_id,
                action="backend:probe",
                resource_type="scholar_backend",
                resource_id=backend.id,
                outcome="accepted" if result.ready else "rejected",
                backend_id=backend.id,
                corpus_version=backend.corpus_version,
                decision=result.reason,
                result_class="success" if result.ready else "unavailable",
                details={"probe_reason": result.reason},
            ),
        )
        return JSONResponse(
            content=backend_body(backend),
            headers={"ETag": resource_etag("backend", backend.id, backend.version)},
        )

    return router
