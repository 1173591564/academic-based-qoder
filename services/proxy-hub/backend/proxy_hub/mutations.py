"""Shared administration mutation integrity helpers."""

from collections.abc import Collection, Mapping
from datetime import datetime
from hashlib import sha256
from json import dumps

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from proxy_hub.audit import AuditEntry, append_audit_event
from proxy_hub.errors import HubError, request_id
from proxy_hub.models import IdempotencyRecord, new_id
from proxy_hub.rbac import AdminContext
from proxy_hub.security import resource_etag


def request_digest(payload: BaseModel) -> str:
    """Hash validated mutation input for audit and idempotency."""
    encoded = dumps(
        payload.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def require_idempotency_key(value: str | None) -> str:
    """Validate a bounded caller-provided idempotency key."""
    if not value or len(value) > 255:
        raise HubError(
            400,
            "idempotency_key_required",
            "A valid Idempotency-Key header is required.",
        )
    return value


def find_idempotency_record(
    session: Session,
    principal_id: str,
    operation: str,
    key: str,
    digest: str,
) -> IdempotencyRecord | None:
    """Return a matching prior operation or reject key reuse."""
    record = session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.principal_id == principal_id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.key == key,
        )
    )
    if record is not None and record.request_digest != digest:
        raise HubError(
            409,
            "idempotency_conflict",
            "The idempotency key was used for a different request.",
        )
    return record


def store_idempotency_record(
    session: Session,
    principal_id: str,
    operation: str,
    key: str,
    digest: str,
    status_code: int,
    response_body: Mapping[str, object],
) -> None:
    """Store a non-secret mutation result in the caller's transaction."""
    session.add(
        IdempotencyRecord(
            id=new_id("idem"),
            principal_id=principal_id,
            operation=operation,
            key=key,
            request_digest=digest,
            response_status=status_code,
            response_body=dict(response_body),
        )
    )


def idempotency_response(
    record: IdempotencyRecord,
    *,
    etag_resource_type: str | None = None,
    redacted_fields: Collection[str] = (),
) -> JSONResponse:
    """Render a validated replay without re-running side effects."""
    body = dict(record.response_body)
    for field in redacted_fields:
        body[field] = None
    headers = {"Idempotent-Replayed": "true"}
    if etag_resource_type is not None:
        resource_id = body.get("id")
        version = body.get("version")
        if not isinstance(resource_id, str) or not isinstance(version, int):
            raise HubError(
                500,
                "idempotency_record_invalid",
                "The stored idempotency response is invalid.",
            )
        headers["ETag"] = resource_etag(
            etag_resource_type,
            resource_id,
            version,
        )
    return JSONResponse(
        status_code=record.response_status,
        content=body,
        headers=headers,
    )


def require_current_etag(
    resource_type: str,
    resource_id: str,
    version: int | datetime,
    if_match: str | None,
) -> None:
    """Require the current strong ETag for a mutable resource."""
    if if_match is None:
        raise HubError(
            400,
            "if_match_required",
            "The current resource ETag is required.",
        )
    if if_match != resource_etag(resource_type, resource_id, version):
        raise HubError(
            412,
            "etag_mismatch",
            "The resource changed after it was loaded.",
        )


def require_version_update(resource_id: str | None) -> str:
    """Reject a mutation that lost an optimistic-concurrency race."""
    if resource_id is None:
        raise HubError(
            412,
            "etag_mismatch",
            "The resource changed after it was loaded.",
        )
    return resource_id


def append_mutation_audit(
    session: Session,
    request: Request,
    context: AdminContext,
    *,
    action: str,
    resource_type: str,
    resource_id: str,
    tenant_id: str | None,
    digest: str,
    backend_id: str | None = None,
    corpus_version: str | None = None,
    decision: str | None = None,
    details: Mapping[str, object] | None = None,
) -> None:
    """Append one minimized mutation audit event."""
    event_details = dict(details or {})
    event_details.update(
        {
            "argument_digest": digest,
            "result_class": "success",
        }
    )
    append_audit_event(
        session,
        AuditEntry(
            request_id=request_id(request),
            principal_id=context.principal_id,
            tenant_id=tenant_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome="accepted",
            argument_digest=digest,
            backend_id=backend_id,
            corpus_version=corpus_version,
            decision=decision,
            result_class="success",
            details=event_details,
        ),
    )
