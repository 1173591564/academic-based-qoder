"""Proxy Hub control-plane persistence models."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id(prefix: str) -> str:
    """Create an opaque resource identifier."""
    return f"{prefix}_{uuid4().hex}"


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for Hub-owned control-plane tables."""


class Timestamped:
    """Creation and modification timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class Versioned:
    """Optimistic-concurrency version."""

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class Principal(Base, Timestamped, Versioned):
    """Human identity synchronized from the configured identity provider."""

    __tablename__ = "principals"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    issuer: Mapped[str] = mapped_column(String(512), nullable=False)
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_principal_issuer_subject"),
    )


class BrowserSession(Base):
    """Opaque server-side browser session."""

    __tablename__ = "browser_sessions"

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    principal_id: Mapped[str] = mapped_column(
        ForeignKey("principals.id"),
        nullable=False,
        index=True,
    )
    csrf_digest: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class OidcLoginState(Base):
    """Short-lived server-side OIDC authorization request state."""

    __tablename__ = "oidc_login_states"

    state_digest: Mapped[str] = mapped_column(String(128), primary_key=True)
    nonce: Mapped[str] = mapped_column(String(128), nullable=False)
    code_verifier: Mapped[str] = mapped_column(String(128), nullable=False)
    return_to: Mapped[str] = mapped_column(String(1024), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class Tenant(Base, Timestamped, Versioned):
    """Organization boundary mapped to one Scholar corpus route."""

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class Team(Base, Timestamped, Versioned):
    """Named principal group within one tenant."""

    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_team_tenant_name"),
    )


class Membership(Base, Timestamped, Versioned):
    """Principal membership in a tenant and optional team."""

    __tablename__ = "memberships"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"), index=True)
    principal_id: Mapped[str] = mapped_column(
        ForeignKey("principals.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "team_id",
            "principal_id",
            name="uq_membership_scope_principal",
        ),
    )


class RoleBinding(Base, Timestamped):
    """Platform-wide or tenant-scoped role assignment."""

    __tablename__ = "role_bindings"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    principal_id: Mapped[str] = mapped_column(
        ForeignKey("principals.id"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str | None] = mapped_column(ForeignKey("tenants.id"), index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "principal_id",
            "tenant_id",
            "role",
            name="uq_role_binding",
        ),
    )


class ToolPolicy(Base, Timestamped, Versioned):
    """Exact Scholar tool allowlist for one tenant."""

    __tablename__ = "tool_policies"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id"),
        primary_key=True,
    )
    allowed_tools: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class QuotaPolicy(Base, Timestamped, Versioned):
    """Quota class and limit allocation for one tenant."""

    __tablename__ = "quota_policies"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id"),
        primary_key=True,
    )
    quota_class: Mapped[str] = mapped_column(String(64), nullable=False)
    request_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    period_seconds: Mapped[int] = mapped_column(Integer, nullable=False)


class ScholarBackend(Base, Timestamped, Versioned):
    """Registered Scholar service instance without secret material."""

    __tablename__ = "scholar_backends"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    corpus_version: Mapped[str] = mapped_column(String(128), nullable=False)
    credential_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    credential_version: Mapped[str | None] = mapped_column(String(128))
    credential_rotated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    status: Mapped[str] = mapped_column(String(32), default="disabled", nullable=False)
    capacity: Mapped[dict[str, object]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    last_probe_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_probe_ready: Mapped[bool | None] = mapped_column(Boolean)


class TenantRoute(Base, Timestamped, Versioned):
    """Active tenant-to-Scholar backend mapping."""

    __tablename__ = "tenant_routes"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id"),
        primary_key=True,
    )
    backend_id: Mapped[str] = mapped_column(
        ForeignKey("scholar_backends.id"),
        nullable=False,
        index=True,
    )
    corpus_version: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class DshCapability(Base):
    """Revocable DSH session capability metadata."""

    __tablename__ = "dsh_capabilities"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    token_digest: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    principal_id: Mapped[str] = mapped_column(
        ForeignKey("principals.id"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    issued_from_enrolment_id: Mapped[str | None] = mapped_column(
        ForeignKey("enrolment_tokens.id"),
        index=True,
    )
    session_label: Mapped[str | None] = mapped_column(String(200))
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class EnrolmentToken(Base):
    """One-time credential used to issue a DSH capability."""

    __tablename__ = "enrolment_tokens"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    token_digest: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    principal_id: Mapped[str] = mapped_column(
        ForeignKey("principals.id"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    requested_scopes: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_principal_id: Mapped[str] = mapped_column(
        ForeignKey("principals.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class QuotaWindow(Base):
    """Atomic tenant request counters for one quota period."""

    __tablename__ = "quota_windows"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id"),
        primary_key=True,
    )
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
    )
    period_seconds: Mapped[int] = mapped_column(Integer, primary_key=True)
    reserved_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class McpSessionAffinity(Base):
    """Stable backend selection for one MCP session."""

    __tablename__ = "mcp_session_affinities"

    session_digest: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    backend_id: Mapped[str] = mapped_column(
        ForeignKey("scholar_backends.id"),
        nullable=False,
        index=True,
    )
    corpus_version: Mapped[str] = mapped_column(String(128), nullable=False)
    capability_id: Mapped[str] = mapped_column(
        ForeignKey("dsh_capabilities.id"),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class IdempotencyRecord(Base):
    """Stored response for one principal-scoped idempotency key."""

    __tablename__ = "idempotency_records"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    principal_id: Mapped[str] = mapped_column(
        ForeignKey("principals.id"),
        nullable=False,
    )
    operation: Mapped[str] = mapped_column(String(128), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(128), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "principal_id",
            "operation",
            "key",
            name="uq_idempotency_principal_operation_key",
        ),
    )


class AuditEvent(Base):
    """Append-only authorization or control-plane mutation record."""

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    request_id: Mapped[str] = mapped_column(String(96), nullable=False)
    principal_id: Mapped[str | None] = mapped_column(String(48), index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(48), index=True)
    capability_id: Mapped[str | None] = mapped_column(String(48), index=True)
    mcp_session_digest: Mapped[str | None] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(96))
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(128), index=True)
    argument_digest: Mapped[str | None] = mapped_column(String(128))
    backend_id: Mapped[str | None] = mapped_column(String(48), index=True)
    corpus_version: Mapped[str | None] = mapped_column(String(128))
    decision: Mapped[str | None] = mapped_column(String(32), index=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    result_class: Mapped[str | None] = mapped_column(String(64))
    returned_bytes: Mapped[int | None] = mapped_column(Integer)
    quota_delta: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict[str, object]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    __table_args__ = (Index("ix_audit_events_occurred_at_id", "occurred_at", "id"),)


def reject_audit_mutation(
    _mapper: object,
    _connection: object,
    _target: AuditEvent,
) -> None:
    """Prevent application-level audit updates and deletes."""
    raise RuntimeError("audit events are append-only")


event.listen(AuditEvent, "before_update", reject_audit_mutation)
event.listen(AuditEvent, "before_delete", reject_audit_mutation)
