"""MCP protocol inspection and HTTP relay helpers."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
from fastapi import Request
from pydantic import TypeAdapter, ValidationError

from proxy_hub.audit import digest_arguments
from proxy_hub.errors import HubError, request_id
from proxy_hub.secrets import SecretResolutionError

MCP_SESSION_HEADER = "mcp-session-id"
MCP_PROTOCOL_HEADER = "mcp-protocol-version"
LAST_EVENT_HEADER = "last-event-id"
REQUEST_HEADER_NAMES = (
    "accept",
    "content-type",
    MCP_SESSION_HEADER,
    MCP_PROTOCOL_HEADER,
    LAST_EVENT_HEADER,
)
RESPONSE_HEADER_NAMES = (
    "cache-control",
    "content-encoding",
    "content-length",
    "content-type",
    MCP_SESSION_HEADER,
    "retry-after",
)
JSON_OBJECT = TypeAdapter(dict[str, object])


@dataclass(frozen=True)
class McpRequestMetadata:
    """Policy and audit metadata extracted without changing the request body."""

    protocol_method: str | None
    tool_name: str | None
    argument_digest: str | None


def mcp_session_id(value: str | None, *, upstream: bool = False) -> str | None:
    """Validate one opaque MCP session identifier."""
    if value is None:
        return None
    if (
        not value
        or len(value) > 512
        or value.strip() != value
        or any(character.isspace() for character in value)
    ):
        if upstream:
            raise HubError(
                502,
                "backend_protocol_error",
                "The Scholar backend returned an invalid MCP session.",
            )
        raise HubError(
            400,
            "invalid_mcp_session",
            "The MCP session identifier is malformed.",
        )
    return value


def inspect_mcp_request(method: str, body: bytes) -> McpRequestMetadata:
    """Extract exact tool metadata while preserving the original JSON bytes."""
    if method != "POST":
        return McpRequestMetadata(None, None, None)
    try:
        message = JSON_OBJECT.validate_json(body)
    except ValidationError as error:
        raise HubError(
            400,
            "invalid_mcp_request",
            "The MCP request must contain one JSON-RPC object.",
        ) from error
    protocol_method = message.get("method")
    if protocol_method is not None and not isinstance(protocol_method, str):
        raise HubError(
            400,
            "invalid_mcp_request",
            "The MCP request method is malformed.",
        )
    if protocol_method != "tools/call":
        return McpRequestMetadata(protocol_method, None, None)
    try:
        params = JSON_OBJECT.validate_python(message.get("params"))
    except ValidationError as error:
        raise HubError(
            400,
            "invalid_mcp_request",
            "The MCP tool call parameters are malformed.",
        ) from error
    tool_name = params.get("name")
    if not isinstance(tool_name, str) or not tool_name:
        raise HubError(
            400,
            "invalid_mcp_request",
            "The MCP tool call name is malformed.",
        )
    raw_arguments = params.get("arguments")
    if raw_arguments is None:
        raw_arguments = {}
    try:
        arguments = JSON_OBJECT.validate_python(raw_arguments)
    except ValidationError as error:
        raise HubError(
            400,
            "invalid_mcp_request",
            "The MCP tool call arguments are malformed.",
        ) from error
    return McpRequestMetadata(
        protocol_method=protocol_method,
        tool_name=tool_name,
        argument_digest=digest_arguments(arguments),
    )


def validated_backend_url(base_url: str, *, production: bool) -> str:
    """Reject malformed, credential-bearing, or insecure production URLs."""
    parsed = urlsplit(base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or (production and parsed.scheme != "https")
    ):
        raise HubError(
            503,
            "backend_unavailable",
            "No eligible Scholar backend is available.",
        )
    return base_url


def validated_service_credential(value: str) -> str:
    """Reject empty or header-unsafe Scholar service credentials."""
    if (
        not value
        or len(value) > 4_096
        or value.strip() != value
        or "\r" in value
        or "\n" in value
    ):
        raise SecretResolutionError("invalid secret value")
    return value


def request_headers(request: Request, service_credential: str) -> dict[str, str]:
    """Build a strict upstream header set without forwarding client credentials."""
    headers = {
        name: value
        for name in REQUEST_HEADER_NAMES
        if (value := request.headers.get(name)) is not None
    }
    headers["authorization"] = f"Bearer {service_credential}"
    headers["x-request-id"] = request_id(request)
    return headers


def response_headers(response: httpx.Response) -> dict[str, str]:
    """Return only end-to-end MCP response headers."""
    return {
        name: value
        for name in RESPONSE_HEADER_NAMES
        if (value := response.headers.get(name)) is not None
    }


def response_size(response: httpx.Response) -> int | None:
    """Parse a trustworthy non-negative Content-Length for audit metadata."""
    value = response.headers.get("content-length")
    if value is None:
        return None
    try:
        size = int(value)
    except ValueError:
        return None
    return size if size >= 0 else None


def result_class(status_code: int) -> str:
    """Classify an upstream HTTP result without retaining response content."""
    return f"http_{status_code // 100}xx"


async def stream_body(response: httpx.Response) -> AsyncIterator[bytes]:
    """Relay raw response chunks and always release the upstream connection."""
    try:
        if response.is_stream_consumed:
            yield response.content
            return
        async for chunk in response.aiter_raw():
            yield chunk
    finally:
        await response.aclose()


async def bounded_request_body(request: Request, maximum_bytes: int) -> bytes:
    """Read a request body without retaining content beyond the configured limit."""
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > maximum_bytes:
            raise HubError(
                413,
                "request_too_large",
                "The MCP request exceeds the configured size limit.",
            )
        chunks.append(chunk)
    return b"".join(chunks)
