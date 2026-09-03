"""Safe Scholar backend readiness probes."""

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from proxy_hub.errors import HubError
from proxy_hub.mcp_transport import (
    validated_backend_url,
    validated_service_credential,
)
from proxy_hub.secrets import SecretResolutionError, SecretResolver


class ScholarReadiness(BaseModel):
    """Validated non-sensitive Scholar readiness metadata."""

    model_config = ConfigDict(extra="ignore")

    status: str
    corpus_version: str = Field(min_length=1, max_length=128)
    parsed_papers: int = Field(ge=0)
    vector_chunks: int = Field(ge=0)
    graph_built_at: datetime | None = None
    synchronized_at: datetime | None = None
    workspace_isolation: str = "shared"


@dataclass(frozen=True)
class ProbeResult:
    """One controlled backend readiness observation."""

    ready: bool
    reason: str
    capacity: dict[str, object]


def readiness_url(base_url: str, *, production: bool) -> str:
    """Derive the private readiness endpoint beside an MCP endpoint."""
    validated_backend_url(base_url, production=production)
    parsed = urlsplit(base_url)
    parent = parsed.path.rstrip("/").rsplit("/", 1)[0]
    readiness_path = f"{parent}/private/health/ready"
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            readiness_path,
            "",
            "",
        )
    )


async def _bounded_response(
    response: httpx.Response,
    maximum_bytes: int,
) -> bytes:
    chunks: list[bytes] = []
    size = 0
    try:
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > maximum_bytes:
                raise ValueError("probe_response_too_large")
            chunks.append(chunk)
    finally:
        await response.aclose()
    return b"".join(chunks)


async def probe_scholar_backend(
    client: httpx.AsyncClient,
    secret_resolver: SecretResolver,
    *,
    base_url: str,
    credential_ref: str,
    expected_corpus_version: str,
    production: bool,
    request_id: str,
    maximum_bytes: int,
) -> ProbeResult:
    """Probe one backend without retaining credentials or arbitrary content."""
    try:
        credential = validated_service_credential(
            secret_resolver.resolve(credential_ref)
        )
    except (HubError, SecretResolutionError):
        return ProbeResult(False, "credential_unavailable", {})
    try:
        url = readiness_url(base_url, production=production)
    except HubError:
        return ProbeResult(False, "backend_url_invalid", {})
    request = client.build_request(
        "GET",
        url,
        headers={
            "accept": "application/json",
            "authorization": f"Bearer {credential}",
            "x-request-id": request_id,
        },
    )
    try:
        response = await client.send(request, stream=True)
    except httpx.HTTPError:
        return ProbeResult(False, "backend_unreachable", {})
    if 300 <= response.status_code < 400:
        await response.aclose()
        return ProbeResult(False, "backend_redirect_denied", {})
    if response.status_code != 200:
        await response.aclose()
        return ProbeResult(False, f"backend_http_{response.status_code}", {})
    try:
        body = await _bounded_response(response, maximum_bytes)
        readiness = ScholarReadiness.model_validate_json(body)
    except (httpx.HTTPError, ValidationError, ValueError):
        return ProbeResult(False, "backend_readiness_invalid", {})
    if readiness.status != "ready":
        return ProbeResult(False, "backend_not_ready", {})
    if readiness.corpus_version != expected_corpus_version:
        return ProbeResult(False, "corpus_version_mismatch", {})
    if readiness.workspace_isolation not in {"shared", "tenant"}:
        return ProbeResult(False, "workspace_isolation_invalid", {})
    return ProbeResult(
        True,
        "ready",
        {
            "parsed_papers": readiness.parsed_papers,
            "vector_chunks": readiness.vector_chunks,
            "graph_built_at": (
                readiness.graph_built_at.isoformat()
                if readiness.graph_built_at is not None
                else None
            ),
            "synchronized_at": (
                readiness.synchronized_at.isoformat()
                if readiness.synchronized_at is not None
                else None
            ),
            "workspace_isolation": readiness.workspace_isolation,
        },
    )
