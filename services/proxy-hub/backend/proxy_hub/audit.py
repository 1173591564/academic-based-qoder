"""Append-only audit construction for control-plane and gateway events."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256
from json import dumps

from sqlalchemy.orm import Session

from proxy_hub.models import AuditEvent, new_id


@dataclass(frozen=True)
class AuditEntry:
    """Validated fields for one immutable audit event."""

    request_id: str
    action: str
    resource_type: str
    outcome: str
    principal_id: str | None = None
    tenant_id: str | None = None
    capability_id: str | None = None
    access_key_id: str | None = None
    mcp_session_digest: str | None = None
    resource_id: str | None = None
    tool_name: str | None = None
    argument_digest: str | None = None
    backend_id: str | None = None
    corpus_version: str | None = None
    decision: str | None = None
    latency_ms: int | None = None
    result_class: str | None = None
    returned_bytes: int | None = None
    quota_delta: int | None = None
    details: Mapping[str, object] = field(default_factory=dict)


def digest_arguments(arguments: Mapping[str, object]) -> str:
    """Build a stable digest without retaining request arguments."""
    encoded = dumps(
        arguments,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def append_audit_event(session: Session, entry: AuditEntry) -> AuditEvent:
    """Add an immutable audit event to the caller's transaction."""
    event = AuditEvent(
        id=new_id("audit"),
        request_id=entry.request_id,
        principal_id=entry.principal_id,
        tenant_id=entry.tenant_id,
        capability_id=entry.capability_id,
        access_key_id=entry.access_key_id,
        mcp_session_digest=entry.mcp_session_digest,
        action=entry.action,
        resource_type=entry.resource_type,
        resource_id=entry.resource_id,
        outcome=entry.outcome,
        tool_name=entry.tool_name,
        argument_digest=entry.argument_digest,
        backend_id=entry.backend_id,
        corpus_version=entry.corpus_version,
        decision=entry.decision,
        latency_ms=entry.latency_ms,
        result_class=entry.result_class,
        returned_bytes=entry.returned_bytes,
        quota_delta=entry.quota_delta,
        details=dict(entry.details),
    )
    session.add(event)
    return event
