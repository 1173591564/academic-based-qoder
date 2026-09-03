"""Scholar MCP gateway authentication, forwarding, and isolation tests."""

from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from json import dumps

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from proxy_hub.app import create_app
from proxy_hub.config import Settings
from proxy_hub.models import (
    AuditEvent,
    Base,
    DshCapability,
    McpSessionAffinity,
    Membership,
    Principal,
    ScholarBackend,
    Tenant,
    TenantRoute,
    utc_now,
)
from proxy_hub.secrets import SecretResolutionError
from proxy_hub.security import digest_token

CAPABILITY = "dsh-capability"
SERVICE_CREDENTIAL = "scholar-service-credential"
MCP_SESSION = "scholar-mcp-session"
BACKEND_URL = "https://scholar.test/mcp"


@dataclass(frozen=True)
class StaticSecretResolver:
    """Resolve the test backend credential without environment state."""

    credential: str = SERVICE_CREDENTIAL
    unavailable: bool = False

    def resolve(self, reference: str) -> str:
        assert reference == "env:SCHOLAR_TEST_TOKEN"
        if self.unavailable:
            raise SecretResolutionError("unavailable")
        return self.credential


class ChunkedAsyncStream(httpx.AsyncByteStream):
    """Yield finite chunks through HTTPX's real async streaming path."""

    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self.chunks:
            yield chunk


@dataclass(frozen=True)
class GatewayHarness:
    """Isolated gateway client, control database, and upstream requests."""

    client: TestClient
    engine: Engine
    upstream_requests: list[httpx.Request]


def seed_gateway_state(engine: Engine, scopes: list[str] | None = None) -> None:
    """Create one active capability with an explicit healthy backend route."""
    now = utc_now()
    with Session(engine) as session:
        session.add(
            Principal(
                id="principal_gateway",
                issuer="https://identity.test",
                subject="gateway-user",
            )
        )
        session.add(
            Tenant(
                id="tenant_gateway",
                slug="tenant-gateway",
                name="Gateway Tenant",
            )
        )
        session.add(
            Membership(
                id="membership_gateway",
                principal_id="principal_gateway",
                tenant_id="tenant_gateway",
            )
        )
        session.add(
            DshCapability(
                id="cap_gateway",
                token_digest=digest_token(CAPABILITY),
                principal_id="principal_gateway",
                tenant_id="tenant_gateway",
                scopes=scopes or ["scholar_info", "scholar_search"],
                expires_at=now + timedelta(hours=1),
            )
        )
        session.add(
            ScholarBackend(
                id="backend_gateway",
                name="Scholar Gateway",
                base_url=BACKEND_URL,
                corpus_version="corpus-v1",
                credential_ref="env:SCHOLAR_TEST_TOKEN",
                status="active",
                last_probe_at=now,
                last_probe_ready=True,
            )
        )
        session.add(
            TenantRoute(
                tenant_id="tenant_gateway",
                backend_id="backend_gateway",
                corpus_version="corpus-v1",
            )
        )
        session.commit()


@contextmanager
def gateway_harness(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    scopes: list[str] | None = None,
    secret_resolver: StaticSecretResolver | None = None,
    request_max_bytes: int = 1_048_576,
) -> Iterator[GatewayHarness]:
    """Create an app backed by an HTTPX mock Scholar service."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    seed_gateway_state(engine, scopes)
    upstream_requests: list[httpx.Request] = []

    def recording_handler(request: httpx.Request) -> httpx.Response:
        upstream_requests.append(request)
        return handler(request)

    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(recording_handler),
        follow_redirects=False,
    )
    app = create_app(
        settings=Settings(
            environment="test",
            database_url="sqlite://",
            public_origin="http://testserver",
            mcp_request_max_bytes=request_max_bytes,
        ),
        engine=engine,
        http_client=http_client,
        secret_resolver=secret_resolver or StaticSecretResolver(),
    )
    with TestClient(app) as client:
        yield GatewayHarness(client, engine, upstream_requests)


def authorization_headers(**extra: str) -> dict[str, str]:
    """Build DSH capability headers for a gateway request."""
    return {
        "Authorization": f"Bearer {CAPABILITY}",
        "Accept": "application/json, text/event-stream",
        **extra,
    }


def json_bytes(value: dict[str, object]) -> bytes:
    """Serialize deterministic JSON request or response bytes."""
    return dumps(value, separators=(",", ":")).encode()


def initialize_body() -> bytes:
    """Return one minimal MCP initialize request."""
    return json_bytes(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        }
    )


def tool_call_body(tool_name: str, arguments: dict[str, object]) -> bytes:
    """Return one MCP tools/call request."""
    return json_bytes(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
    )


def test_initialize_and_tool_call_forward_without_rewriting_or_secret_leakage() -> None:
    initialize_response = json_bytes(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "serverInfo": {"name": "scholar", "version": "1"},
            },
        }
    )
    tool_response = json_bytes(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {"content": [{"type": "text", "text": "result"}]},
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("mcp-session-id") is None:
            return httpx.Response(
                200,
                headers={
                    "content-type": "application/json",
                    "mcp-session-id": MCP_SESSION,
                },
                content=initialize_response,
            )
        return httpx.Response(
            200,
            headers={
                "content-type": "application/json",
                "mcp-session-id": MCP_SESSION,
            },
            content=tool_response,
        )

    with gateway_harness(handler) as gateway:
        initial_body = initialize_body()
        initialized = gateway.client.post(
            "/v1/mcp/scholar",
            content=initial_body,
            headers={
                **authorization_headers(),
                "Content-Type": "application/json",
            },
        )
        research_question = "private research question"
        call_body = tool_call_body(
            "scholar_search",
            {"query": research_question, "top_k": 5},
        )
        called = gateway.client.post(
            "/v1/mcp/scholar",
            content=call_body,
            headers={
                **authorization_headers(**{"Mcp-Session-Id": MCP_SESSION}),
                "Content-Type": "application/json",
                "Mcp-Protocol-Version": "2025-06-18",
                "X-Request-ID": research_question,
            },
        )

        assert initialized.status_code == 200
        assert initialized.content == initialize_response
        assert initialized.headers["mcp-session-id"] == MCP_SESSION
        assert called.status_code == 200
        assert called.content == tool_response
        assert called.headers["x-request-id"].startswith("req_")
        assert len(gateway.upstream_requests) == 2
        first_request, second_request = gateway.upstream_requests
        assert str(first_request.url) == BACKEND_URL
        assert first_request.content == initial_body
        assert second_request.content == call_body
        assert second_request.headers["mcp-session-id"] == MCP_SESSION
        assert second_request.headers["mcp-protocol-version"] == "2025-06-18"
        for upstream_request in gateway.upstream_requests:
            assert (
                upstream_request.headers["authorization"]
                == f"Bearer {SERVICE_CREDENTIAL}"
            )
            assert CAPABILITY not in str(upstream_request.headers)

        with Session(gateway.engine) as session:
            affinity = session.get(
                McpSessionAffinity,
                digest_token(MCP_SESSION),
            )
            assert affinity is not None
            assert affinity.capability_id == "cap_gateway"
            assert affinity.backend_id == "backend_gateway"
            assert affinity.session_digest != MCP_SESSION
            capability = session.get(DshCapability, "cap_gateway")
            assert capability is not None
            assert capability.last_used_at is not None
            tool_audit = session.scalar(
                select(AuditEvent).where(AuditEvent.action == "mcp:tool")
            )
            assert tool_audit is not None
            assert tool_audit.tool_name == "scholar_search"
            assert tool_audit.argument_digest is not None
            assert tool_audit.backend_id == "backend_gateway"
            assert tool_audit.corpus_version == "corpus-v1"
            assert tool_audit.request_id.startswith("req_")
            assert research_question not in str(tool_audit.details)
            assert CAPABILITY not in str(tool_audit.details)
            assert SERVICE_CREDENTIAL not in str(tool_audit.details)
            assert MCP_SESSION not in str(tool_audit.details)


def test_credentials_and_tool_policy_fail_before_backend_contact() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with gateway_harness(
        handler,
        scopes=["scholar_search", "scholar_auto_notes"],
    ) as gateway:
        invalid_credential = gateway.client.post(
            "/v1/mcp/scholar",
            content=initialize_body(),
            headers={"Authorization": "Bearer unknown"},
        )
        denied_scope = gateway.client.post(
            "/v1/mcp/scholar",
            content=tool_call_body("scholar_info", {"paper_id": "paper"}),
            headers={
                **authorization_headers(),
                "Content-Type": "application/json",
            },
        )
        denied_write = gateway.client.post(
            "/v1/mcp/scholar",
            content=tool_call_body(
                "scholar_auto_notes",
                {"paper_id": "private-paper"},
            ),
            headers={
                **authorization_headers(),
                "Content-Type": "application/json",
            },
        )
        unknown_tool = gateway.client.post(
            "/v1/mcp/scholar",
            content=tool_call_body("private-unknown-tool", {}),
            headers={
                **authorization_headers(),
                "Content-Type": "application/json",
            },
        )
        malformed_batch = gateway.client.post(
            "/v1/mcp/scholar",
            content=b"[]",
            headers={
                **authorization_headers(),
                "Content-Type": "application/json",
            },
        )

        assert invalid_credential.status_code == 401
        assert denied_scope.status_code == 403
        assert denied_scope.json()["error"]["code"] == "tool_denied"
        assert denied_write.status_code == 403
        assert unknown_tool.status_code == 403
        assert malformed_batch.status_code == 400
        assert gateway.upstream_requests == []
        with Session(gateway.engine) as session:
            audits = session.scalars(select(AuditEvent)).all()
            assert len(audits) == 5
            assert all(CAPABILITY not in str(audit.details) for audit in audits)
            assert all("private-paper" not in str(audit.details) for audit in audits)
            assert all(
                "private-unknown-tool" not in str(audit.tool_name) for audit in audits
            )
            reasons = {audit.details["reason"] for audit in audits}
            assert "tool_denied" in reasons
            assert "workspace_write_denied" in reasons
            assert "tool_unknown" in reasons


def test_unknown_affinity_and_disabled_route_fail_without_backend_contact() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with gateway_harness(handler) as gateway:
        unknown_affinity = gateway.client.post(
            "/v1/mcp/scholar",
            content=tool_call_body("scholar_search", {"query": "query"}),
            headers={
                **authorization_headers(**{"Mcp-Session-Id": "unknown"}),
                "Content-Type": "application/json",
            },
        )
        with Session(gateway.engine) as session:
            route = session.get(TenantRoute, "tenant_gateway")
            assert route is not None
            route.status = "disabled"
            session.commit()
        missing_route = gateway.client.post(
            "/v1/mcp/scholar",
            content=initialize_body(),
            headers={
                **authorization_headers(),
                "Content-Type": "application/json",
            },
        )

        assert unknown_affinity.status_code == 503
        assert missing_route.status_code == 503
        assert gateway.upstream_requests == []


def test_get_stream_and_delete_forward_with_bound_session() -> None:
    event_stream = b'event: message\ndata: {"jsonrpc":"2.0","method":"ping"}\n\n'

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                headers={
                    "content-type": "text/event-stream",
                    "mcp-session-id": MCP_SESSION,
                },
                stream=ChunkedAsyncStream([event_stream[:20], event_stream[20:]]),
            )
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=b"{}",
        )

    with gateway_harness(handler) as gateway:
        with Session(gateway.engine) as session:
            session.add(
                McpSessionAffinity(
                    session_digest=digest_token(MCP_SESSION),
                    tenant_id="tenant_gateway",
                    backend_id="backend_gateway",
                    corpus_version="corpus-v1",
                    capability_id="cap_gateway",
                    expires_at=utc_now() + timedelta(hours=1),
                )
            )
            session.commit()

        streamed = gateway.client.get(
            "/v1/mcp/scholar",
            headers=authorization_headers(
                **{
                    "Mcp-Session-Id": MCP_SESSION,
                    "Accept": "text/event-stream",
                }
            ),
        )
        deleted = gateway.client.delete(
            "/v1/mcp/scholar",
            headers=authorization_headers(**{"Mcp-Session-Id": MCP_SESSION}),
        )

        assert streamed.status_code == 200
        assert streamed.content == event_stream
        assert streamed.headers["content-type"] == "text/event-stream"
        assert deleted.status_code == 200
        assert [request.method for request in gateway.upstream_requests] == [
            "GET",
            "DELETE",
        ]
        assert all(
            request.headers["mcp-session-id"] == MCP_SESSION
            for request in gateway.upstream_requests
        )
        with Session(gateway.engine) as session:
            assert session.get(McpSessionAffinity, digest_token(MCP_SESSION)) is None


def test_backend_redirect_and_transport_failure_are_not_exposed() -> None:
    def redirect_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            307,
            headers={"location": "https://other.test/mcp"},
        )

    with gateway_harness(redirect_handler) as gateway:
        redirected = gateway.client.post(
            "/v1/mcp/scholar",
            content=initialize_body(),
            headers={
                **authorization_headers(),
                "Content-Type": "application/json",
            },
        )
        assert redirected.status_code == 502
        assert "location" not in redirected.headers
        assert len(gateway.upstream_requests) == 1

    def failing_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unavailable", request=request)

    with gateway_harness(failing_handler) as gateway:
        failed = gateway.client.post(
            "/v1/mcp/scholar",
            content=initialize_body(),
            headers={
                **authorization_headers(),
                "Content-Type": "application/json",
            },
        )
        assert failed.status_code == 502
        assert failed.json()["error"]["code"] == "backend_request_failed"
        with Session(gateway.engine) as session:
            audit = session.scalar(select(AuditEvent))
            assert audit is not None
            assert audit.outcome == "failed"
            assert audit.result_class == "transport_error"


def test_backend_server_error_body_is_not_exposed() -> None:
    internal_detail = "internal-hostname scholar-service-credential"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            headers={"content-type": "text/plain"},
            content=internal_detail,
        )

    with gateway_harness(handler) as gateway:
        failed = gateway.client.post(
            "/v1/mcp/scholar",
            content=initialize_body(),
            headers={
                **authorization_headers(),
                "Content-Type": "application/json",
            },
        )

        assert failed.status_code == 502
        assert internal_detail not in failed.text
        with Session(gateway.engine) as session:
            audit = session.scalar(select(AuditEvent))
            assert audit is not None
            assert internal_detail not in str(audit.details)


def test_backend_session_mismatch_and_secret_failure_fail_closed() -> None:
    def mismatch_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "application/json",
                "mcp-session-id": "different-session",
            },
            content=b"{}",
        )

    with gateway_harness(mismatch_handler) as gateway:
        with Session(gateway.engine) as session:
            session.add(
                McpSessionAffinity(
                    session_digest=digest_token(MCP_SESSION),
                    tenant_id="tenant_gateway",
                    backend_id="backend_gateway",
                    corpus_version="corpus-v1",
                    capability_id="cap_gateway",
                    expires_at=utc_now() + timedelta(hours=1),
                )
            )
            session.commit()
        mismatch = gateway.client.post(
            "/v1/mcp/scholar",
            content=tool_call_body("scholar_search", {"query": "query"}),
            headers={
                **authorization_headers(**{"Mcp-Session-Id": MCP_SESSION}),
                "Content-Type": "application/json",
            },
        )
        assert mismatch.status_code == 502
        assert mismatch.json()["error"]["code"] == "backend_protocol_error"

    def unused_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with gateway_harness(
        unused_handler,
        secret_resolver=StaticSecretResolver(unavailable=True),
    ) as gateway:
        unavailable = gateway.client.post(
            "/v1/mcp/scholar",
            content=initialize_body(),
            headers={
                **authorization_headers(),
                "Content-Type": "application/json",
            },
        )
        assert unavailable.status_code == 503
        assert gateway.upstream_requests == []


def test_request_size_limit_fails_before_backend_contact() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with gateway_harness(handler, request_max_bytes=1_024) as gateway:
        oversized = gateway.client.post(
            "/v1/mcp/scholar",
            content=b"{" + (b"x" * 1_024) + b"}",
            headers={
                **authorization_headers(),
                "Content-Type": "application/json",
            },
        )

        assert oversized.status_code == 413
        assert oversized.json()["error"]["code"] == "request_too_large"
        assert gateway.upstream_requests == []
