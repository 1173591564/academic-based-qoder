"""Authenticated transparent forwarding for Scholar Streamable HTTP MCP."""

from collections.abc import Generator
from datetime import timedelta
from time import monotonic
from typing import NoReturn

import anyio
import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from proxy_hub.audit import AuditEntry, append_audit_event
from proxy_hub.capabilities import CredentialContext, authenticate_credential
from proxy_hub.circuit import BackendCircuitBreaker
from proxy_hub.config import Settings
from proxy_hub.database import Database, session_scope
from proxy_hub.errors import HubError, request_id
from proxy_hub.mcp_quota import stream_with_quota
from proxy_hub.mcp_transport import (
    MCP_SESSION_HEADER,
    McpRequestMetadata,
    bounded_request_body,
    inspect_mcp_request,
    mcp_session_id,
    request_headers,
    response_headers,
    response_size,
    result_class,
    validated_backend_url,
    validated_service_credential,
)
from proxy_hub.models import (
    AccessKey,
    DshCapability,
    McpSessionAffinity,
    ToolPolicy,
    utc_now,
)
from proxy_hub.policy import (
    SCHOLAR_TOOL_CATALOG,
    InvalidToolPolicy,
    decide_effective_tool,
    validate_tool_policy,
)
from proxy_hub.quota import (
    QuotaConfigurationError,
    QuotaExceeded,
    QuotaReservation,
    QuotaService,
    load_quota_limit,
    reserve_access_key_request,
)
from proxy_hub.routing import RouteResolutionError, RouteSelection, resolve_route
from proxy_hub.secrets import SecretResolutionError, SecretResolver
from proxy_hub.security import digest_token

AUDITABLE_PROTOCOL_METHODS = frozenset(
    {
        "initialize",
        "notifications/initialized",
        "ping",
        "tools/list",
        "tools/call",
    }
)


class CircuitOpenError(Exception):
    """An upstream backend circuit rejected a request."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("backend circuit is open")
        self.retry_after_seconds = retry_after_seconds


async def send_upstream(
    client: httpx.AsyncClient,
    circuit_breaker: BackendCircuitBreaker,
    settings: Settings,
    *,
    backend_id: str,
    method: str,
    backend_url: str,
    headers: dict[str, str],
    body: bytes,
) -> httpx.Response:
    """Send one upstream request with safe-method retries and circuit isolation."""
    decision = circuit_breaker.before_request(backend_id, at=utc_now())
    if not decision.allowed:
        raise CircuitOpenError(decision.retry_after_seconds)
    retry_count = settings.backend_safe_retry_attempts if method == "GET" else 0
    for attempt in range(retry_count + 1):
        upstream_request = client.build_request(
            method,
            backend_url,
            headers=headers,
            content=body,
        )
        try:
            response = await client.send(upstream_request, stream=True)
        except httpx.HTTPError:
            if attempt < retry_count:
                await anyio.sleep(settings.backend_retry_backoff_seconds * (2**attempt))
                continue
            circuit_breaker.record_failure(backend_id, at=utc_now())
            raise
        failed = (
            300 <= response.status_code < 400
            or response.status_code >= 500
            or response.status_code in {401, 403}
        )
        if failed and attempt < retry_count:
            await response.aclose()
            await anyio.sleep(settings.backend_retry_backoff_seconds * (2**attempt))
            continue
        if failed:
            circuit_breaker.record_failure(backend_id, at=utc_now())
        else:
            circuit_breaker.record_success(backend_id)
        return response
    raise RuntimeError("unreachable upstream retry state")


def append_gateway_audit(
    session: Session,
    request: Request,
    *,
    context: CredentialContext | None,
    outcome: str,
    decision: str,
    reason: str,
    metadata: McpRequestMetadata | None = None,
    selection: RouteSelection | None = None,
    mcp_session_digest: str | None = None,
    latency_ms: int | None = None,
    result_class: str | None = None,
    returned_bytes: int | None = None,
    quota_delta: int | None = None,
) -> None:
    """Append minimized MCP authorization and forwarding metadata."""
    audited_tool_name = (
        metadata.tool_name
        if metadata is not None and metadata.tool_name in SCHOLAR_TOOL_CATALOG
        else None
    )
    audited_protocol_method = (
        metadata.protocol_method
        if metadata is not None
        and metadata.protocol_method in AUDITABLE_PROTOCOL_METHODS
        else "other"
    )
    append_audit_event(
        session,
        AuditEntry(
            request_id=request_id(request),
            principal_id=context.principal_id if context is not None else None,
            tenant_id=context.tenant_id if context is not None else None,
            capability_id=context.capability_id if context is not None else None,
            access_key_id=context.access_key_id if context is not None else None,
            mcp_session_digest=mcp_session_digest,
            action="mcp:tool" if metadata and metadata.tool_name else "mcp:forward",
            resource_type="scholar_backend",
            resource_id=selection.backend_id if selection is not None else None,
            outcome=outcome,
            tool_name=audited_tool_name,
            argument_digest=(
                metadata.argument_digest if metadata is not None else None
            ),
            backend_id=selection.backend_id if selection is not None else None,
            corpus_version=(
                selection.corpus_version if selection is not None else None
            ),
            decision=decision,
            latency_ms=latency_ms,
            result_class=result_class,
            returned_bytes=returned_bytes,
            quota_delta=quota_delta,
            details={
                "reason": reason,
                "protocol_method": audited_protocol_method,
            },
        ),
    )


def deny_gateway(
    session: Session,
    request: Request,
    error: HubError,
    *,
    context: CredentialContext | None,
    reason: str,
    metadata: McpRequestMetadata | None = None,
    selection: RouteSelection | None = None,
    mcp_session_digest: str | None = None,
    quota_service: QuotaService | None = None,
    reservation: QuotaReservation | None = None,
) -> NoReturn:
    """Commit a denial audit before returning a fail-closed gateway error."""
    if quota_service is not None and reservation is not None:
        quota_service.complete(
            session,
            reservation,
            succeeded=False,
            at=utc_now(),
        )
    append_gateway_audit(
        session,
        request,
        context=context,
        outcome="rejected",
        decision="deny",
        reason=reason,
        metadata=metadata,
        selection=selection,
        mcp_session_digest=mcp_session_digest,
        quota_delta=(1 if reservation is not None and reservation.enforced else None),
    )
    session.commit()
    raise error


def build_mcp_gateway_router(
    database: Database,
    settings: Settings,
    client: httpx.AsyncClient,
    secret_resolver: SecretResolver,
    quota_service: QuotaService,
    circuit_breaker: BackendCircuitBreaker,
) -> APIRouter:
    """Create the authenticated Scholar Streamable HTTP gateway."""
    router = APIRouter()

    def get_session() -> Generator[Session, None, None]:
        yield from session_scope(database)

    @router.api_route(
        "/v1/mcp/scholar",
        methods=["GET", "POST", "DELETE"],
    )
    async def forward_scholar_mcp(
        request: Request,
        session: Session = Depends(get_session),
    ) -> StreamingResponse:
        try:
            context = authenticate_credential(
                session,
                request.headers.get("authorization"),
            )
        except HubError as error:
            deny_gateway(
                session,
                request,
                error,
                context=None,
                reason=error.code,
            )

        try:
            raw_mcp_session = mcp_session_id(request.headers.get(MCP_SESSION_HEADER))
        except HubError as error:
            deny_gateway(
                session,
                request,
                error,
                context=context,
                reason=error.code,
            )
        if request.method in {"GET", "DELETE"} and raw_mcp_session is None:
            deny_gateway(
                session,
                request,
                HubError(
                    400,
                    "mcp_session_required",
                    "This MCP request requires an active session.",
                ),
                context=context,
                reason="mcp_session_required",
            )
        try:
            body = await bounded_request_body(
                request,
                settings.mcp_request_max_bytes,
            )
        except HubError as error:
            deny_gateway(
                session,
                request,
                error,
                context=context,
                reason=error.code,
            )
        try:
            metadata = inspect_mcp_request(request.method, body)
        except HubError as error:
            deny_gateway(
                session,
                request,
                error,
                context=context,
                reason=error.code,
            )
        tenant_tools: tuple[str, ...] = ()
        if metadata.tool_name is not None:
            tenant_policy = session.get(ToolPolicy, context.tenant_id)
            if tenant_policy is None:
                deny_gateway(
                    session,
                    request,
                    HubError(
                        403,
                        "tool_denied",
                        "The Scholar tool is not authorized for this tenant.",
                    ),
                    context=context,
                    reason="tenant_policy_missing",
                    metadata=metadata,
                )
            try:
                tenant_tools = validate_tool_policy(tenant_policy.allowed_tools)
            except InvalidToolPolicy:
                deny_gateway(
                    session,
                    request,
                    HubError(
                        403,
                        "tool_denied",
                        "The Scholar tool is not authorized for this tenant.",
                    ),
                    context=context,
                    reason="tenant_policy_invalid",
                    metadata=metadata,
                )
            decision = decide_effective_tool(
                metadata.tool_name,
                context.scopes,
                tenant_tools,
                allow_workspace_writes=True,
            )
            if not decision.allowed:
                deny_gateway(
                    session,
                    request,
                    HubError(
                        403,
                        "tool_denied",
                        "The Scholar tool is not authorized for this session.",
                    ),
                    context=context,
                    reason=decision.reason,
                    metadata=metadata,
                )

        now = utc_now()
        session_digest = (
            digest_token(raw_mcp_session) if raw_mcp_session is not None else None
        )
        try:
            selection = resolve_route(
                session,
                context.tenant_id,
                context.credential_id,
                now,
                timedelta(seconds=settings.backend_probe_max_age_seconds),
                credential_kind=context.credential_kind,
                mcp_session_digest=session_digest,
            )
        except RouteResolutionError as error:
            deny_gateway(
                session,
                request,
                HubError(
                    503,
                    "backend_unavailable",
                    "No eligible Scholar backend is available.",
                ),
                context=context,
                reason=error.code,
                metadata=metadata,
                mcp_session_digest=session_digest,
            )
        if metadata.tool_name is not None:
            decision = decide_effective_tool(
                metadata.tool_name,
                context.scopes,
                tenant_tools,
                allow_workspace_writes=selection.workspace_writes_allowed,
            )
            if not decision.allowed:
                deny_gateway(
                    session,
                    request,
                    HubError(
                        403,
                        "tool_denied",
                        "The Scholar tool is not authorized for this session.",
                    ),
                    context=context,
                    reason=decision.reason,
                    metadata=metadata,
                    selection=selection,
                    mcp_session_digest=session_digest,
                )
        try:
            service_credential = validated_service_credential(
                secret_resolver.resolve(selection.credential_ref)
            )
            backend_url = validated_backend_url(
                selection.base_url,
                production=settings.environment == "production",
            )
        except (SecretResolutionError, HubError) as error:
            reason = (
                "credential_unavailable"
                if isinstance(error, SecretResolutionError)
                else error.code
            )
            deny_gateway(
                session,
                request,
                HubError(
                    503,
                    "backend_unavailable",
                    "No eligible Scholar backend is available.",
                ),
                context=context,
                reason=reason,
                metadata=metadata,
                selection=selection,
                mcp_session_digest=session_digest,
            )

        if context.access_key_id is not None:
            try:
                reserve_access_key_request(
                    session,
                    context.access_key_id,
                    context.request_limit,
                    context.period_seconds,
                    now,
                )
            except QuotaExceeded as error:
                append_gateway_audit(
                    session,
                    request,
                    context=context,
                    outcome="rejected",
                    decision="deny",
                    reason=error.reason,
                    metadata=metadata,
                    selection=selection,
                    mcp_session_digest=session_digest,
                    quota_delta=0,
                )
                session.commit()
                raise HubError(
                    429,
                    "quota_exceeded",
                    "The Access Key request quota is currently exhausted.",
                    headers={"Retry-After": str(error.retry_after_seconds)},
                ) from error
            except QuotaConfigurationError as error:
                append_gateway_audit(
                    session,
                    request,
                    context=context,
                    outcome="failed",
                    decision="deny",
                    reason=str(error),
                    metadata=metadata,
                    selection=selection,
                    mcp_session_digest=session_digest,
                    quota_delta=0,
                )
                session.commit()
                raise HubError(
                    503,
                    "quota_unavailable",
                    "The Access Key quota cannot be enforced.",
                ) from error
        try:
            reservation = quota_service.reserve(
                session,
                context.tenant_id,
                load_quota_limit(session, context.tenant_id),
                now,
            )
        except QuotaExceeded as error:
            append_gateway_audit(
                session,
                request,
                context=context,
                outcome="rejected",
                decision="deny",
                reason=error.reason,
                metadata=metadata,
                selection=selection,
                mcp_session_digest=session_digest,
                quota_delta=0,
            )
            session.commit()
            raise HubError(
                429,
                "quota_exceeded",
                "The tenant request quota is currently exhausted.",
                headers={"Retry-After": str(error.retry_after_seconds)},
            ) from error
        except QuotaConfigurationError as error:
            append_gateway_audit(
                session,
                request,
                context=context,
                outcome="failed",
                decision="deny",
                reason=str(error),
                metadata=metadata,
                selection=selection,
                mcp_session_digest=session_digest,
                quota_delta=0,
            )
            session.commit()
            raise HubError(
                503,
                "quota_unavailable",
                "The tenant quota policy cannot be enforced.",
            ) from error
        session.commit()

        started_at = monotonic()
        try:
            upstream = await send_upstream(
                client,
                circuit_breaker,
                settings,
                backend_id=selection.backend_id,
                method=request.method,
                backend_url=backend_url,
                headers=request_headers(request, service_credential),
                body=body,
            )
        except CircuitOpenError as error:
            quota_service.complete(
                session,
                reservation,
                succeeded=False,
                at=utc_now(),
            )
            append_gateway_audit(
                session,
                request,
                context=context,
                outcome="rejected",
                decision="deny",
                reason="backend_circuit_open",
                metadata=metadata,
                selection=selection,
                mcp_session_digest=session_digest,
                latency_ms=int((monotonic() - started_at) * 1000),
                result_class="circuit_open",
                quota_delta=1 if reservation.enforced else None,
            )
            session.commit()
            raise HubError(
                503,
                "backend_unavailable",
                "No eligible Scholar backend is available.",
                headers={"Retry-After": str(error.retry_after_seconds)},
            ) from error
        except httpx.HTTPError as error:
            timed_out = isinstance(error, httpx.TimeoutException)
            quota_service.complete(
                session,
                reservation,
                succeeded=False,
                at=utc_now(),
            )
            append_gateway_audit(
                session,
                request,
                context=context,
                outcome="failed",
                decision="permit",
                reason="backend_timeout" if timed_out else "backend_request_failed",
                metadata=metadata,
                selection=selection,
                mcp_session_digest=session_digest,
                latency_ms=int((monotonic() - started_at) * 1000),
                result_class="timeout" if timed_out else "transport_error",
                quota_delta=1 if reservation.enforced else None,
            )
            session.commit()
            raise HubError(
                504 if timed_out else 502,
                "backend_timeout" if timed_out else "backend_request_failed",
                "The Scholar backend request failed.",
            ) from error
        if 300 <= upstream.status_code < 400:
            await upstream.aclose()
            quota_service.complete(
                session,
                reservation,
                succeeded=False,
                at=utc_now(),
            )
            append_gateway_audit(
                session,
                request,
                context=context,
                outcome="failed",
                decision="permit",
                reason="backend_redirect",
                metadata=metadata,
                selection=selection,
                mcp_session_digest=session_digest,
                latency_ms=int((monotonic() - started_at) * 1000),
                result_class=result_class(upstream.status_code),
                quota_delta=1 if reservation.enforced else None,
            )
            session.commit()
            raise HubError(
                502,
                "backend_protocol_error",
                "The Scholar backend returned an invalid response.",
            )
        if upstream.status_code >= 500 or upstream.status_code in {401, 403}:
            await upstream.aclose()
            quota_service.complete(
                session,
                reservation,
                succeeded=False,
                at=utc_now(),
            )
            append_gateway_audit(
                session,
                request,
                context=context,
                outcome="failed",
                decision="permit",
                reason="backend_rejected",
                metadata=metadata,
                selection=selection,
                mcp_session_digest=session_digest,
                latency_ms=int((monotonic() - started_at) * 1000),
                result_class=result_class(upstream.status_code),
                quota_delta=1 if reservation.enforced else None,
            )
            session.commit()
            raise HubError(
                502,
                "backend_request_failed",
                "The Scholar backend request failed.",
            )

        declared_size = response_size(upstream)
        if (
            declared_size is not None
            and declared_size > settings.mcp_response_max_bytes
        ):
            await upstream.aclose()
            deny_gateway(
                session,
                request,
                HubError(
                    502,
                    "backend_response_too_large",
                    "The Scholar backend response exceeds the configured limit.",
                ),
                context=context,
                reason="backend_response_too_large",
                metadata=metadata,
                selection=selection,
                mcp_session_digest=session_digest,
                quota_service=quota_service,
                reservation=reservation,
            )
        try:
            response_session = mcp_session_id(
                upstream.headers.get(MCP_SESSION_HEADER),
                upstream=True,
            )
        except HubError:
            await upstream.aclose()
            deny_gateway(
                session,
                request,
                HubError(
                    502,
                    "backend_protocol_error",
                    "The Scholar backend returned an invalid MCP session.",
                ),
                context=context,
                reason="backend_session_invalid",
                metadata=metadata,
                selection=selection,
                mcp_session_digest=session_digest,
                quota_service=quota_service,
                reservation=reservation,
            )
        if (
            raw_mcp_session is not None
            and response_session is not None
            and response_session != raw_mcp_session
        ):
            await upstream.aclose()
            deny_gateway(
                session,
                request,
                HubError(
                    502,
                    "backend_protocol_error",
                    "The Scholar backend returned an invalid MCP session.",
                ),
                context=context,
                reason="backend_session_mismatch",
                metadata=metadata,
                selection=selection,
                mcp_session_digest=session_digest,
                quota_service=quota_service,
                reservation=reservation,
            )

        if response_session is not None and 200 <= upstream.status_code < 300:
            response_digest = digest_token(response_session)
            affinity_expires_at = context.expires_at or (
                now + timedelta(seconds=settings.session_ttl_seconds)
            )
            affinity = session.get(McpSessionAffinity, response_digest)
            if affinity is None:
                affinity = McpSessionAffinity(
                    session_digest=response_digest,
                    tenant_id=context.tenant_id,
                    backend_id=selection.backend_id,
                    corpus_version=selection.corpus_version,
                    capability_id=context.capability_id,
                    access_key_id=context.access_key_id,
                    expires_at=affinity_expires_at,
                    last_seen_at=now,
                )
                session.add(affinity)
            elif (
                affinity.tenant_id != context.tenant_id
                or affinity.capability_id != context.capability_id
                or affinity.access_key_id != context.access_key_id
                or affinity.backend_id != selection.backend_id
                or affinity.corpus_version != selection.corpus_version
            ):
                await upstream.aclose()
                deny_gateway(
                    session,
                    request,
                    HubError(
                        502,
                        "backend_protocol_error",
                        "The Scholar backend returned an invalid MCP session.",
                    ),
                    context=context,
                    reason="backend_session_collision",
                    metadata=metadata,
                    selection=selection,
                    mcp_session_digest=response_digest,
                    quota_service=quota_service,
                    reservation=reservation,
                )
            else:
                affinity.last_seen_at = now
                affinity.expires_at = affinity_expires_at
        if request.method == "DELETE" and session_digest is not None:
            affinity = session.get(McpSessionAffinity, session_digest)
            if affinity is not None and upstream.status_code < 500:
                session.delete(affinity)

        try:
            credential = (
                session.get(DshCapability, context.capability_id)
                if context.capability_id is not None
                else session.get(AccessKey, context.access_key_id)
            )
            if credential is None:
                await upstream.aclose()
                deny_gateway(
                    session,
                    request,
                    HubError(
                        403,
                        "credential_denied",
                        "The Scholar credential is no longer available.",
                    ),
                    context=context,
                    reason="credential_missing",
                    metadata=metadata,
                    selection=selection,
                    mcp_session_digest=session_digest,
                    quota_service=quota_service,
                    reservation=reservation,
                )
            credential.last_used_at = now
            append_gateway_audit(
                session,
                request,
                context=context,
                outcome="forwarded" if upstream.status_code < 500 else "failed",
                decision="permit",
                reason="forwarded",
                metadata=metadata,
                selection=selection,
                mcp_session_digest=(
                    digest_token(response_session)
                    if response_session is not None
                    else session_digest
                ),
                latency_ms=int((monotonic() - started_at) * 1000),
                result_class=result_class(upstream.status_code),
                returned_bytes=response_size(upstream),
                quota_delta=1 if reservation.enforced else None,
            )
            session.commit()
        except Exception:
            await upstream.aclose()
            session.rollback()
            quota_service.complete(
                session,
                reservation,
                succeeded=False,
                at=utc_now(),
            )
            session.commit()
            raise
        return StreamingResponse(
            stream_with_quota(
                upstream,
                database,
                quota_service,
                reservation,
                refresh_seconds=settings.quota_reservation_ttl_seconds / 2,
                maximum_bytes=settings.mcp_response_max_bytes,
            ),
            status_code=upstream.status_code,
            headers=response_headers(upstream),
        )

    return router
