"""Scholar readiness probe safety tests."""

import asyncio

import httpx
import pytest

from proxy_hub.backend_probe import ProbeResult, probe_scholar_backend, readiness_url
from proxy_hub.errors import HubError
from proxy_hub.secrets import EnvironmentSecretResolver


def run_probe(
    handler: httpx.MockTransport,
    *,
    maximum_bytes: int = 65_536,
    corpus_version: str = "corpus-v1",
) -> ProbeResult:
    async def execute() -> ProbeResult:
        async with httpx.AsyncClient(transport=handler) as client:
            return await probe_scholar_backend(
                client,
                EnvironmentSecretResolver(),
                base_url="http://scholar.test/mcp",
                credential_ref="env:SCHOLAR_TEST_TOKEN",
                expected_corpus_version=corpus_version,
                production=False,
                request_id="request-probe",
                maximum_bytes=maximum_bytes,
            )

    return asyncio.run(execute())


def test_probe_authenticates_and_validates_readiness(monkeypatch) -> None:
    monkeypatch.setenv("SCHOLAR_TEST_TOKEN", "service-token")

    def backend(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/private/health/ready"
        assert request.headers["authorization"] == "Bearer service-token"
        assert request.headers["x-request-id"] == "request-probe"
        return httpx.Response(
            200,
            json={
                "status": "ready",
                "corpus_version": "corpus-v1",
                "parsed_papers": 3,
                "vector_chunks": 24,
                "workspace_isolation": "shared",
            },
        )

    result = run_probe(httpx.MockTransport(backend))

    assert result.ready is True
    assert result.reason == "ready"
    assert result.capacity["parsed_papers"] == 3
    assert result.capacity["vector_chunks"] == 24


def test_probe_rejects_redirects_wrong_corpus_and_large_bodies(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SCHOLAR_TEST_TOKEN", "service-token")
    redirect = run_probe(httpx.MockTransport(lambda _request: httpx.Response(302)))
    wrong_corpus = run_probe(
        httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={
                    "status": "ready",
                    "corpus_version": "corpus-v2",
                    "parsed_papers": 0,
                    "vector_chunks": 0,
                },
            )
        )
    )
    oversized = run_probe(
        httpx.MockTransport(lambda _request: httpx.Response(200, content=b"x" * 1_025)),
        maximum_bytes=1_024,
    )

    assert redirect.reason == "backend_redirect_denied"
    assert wrong_corpus.reason == "corpus_version_mismatch"
    assert oversized.reason == "backend_readiness_invalid"


def test_probe_fails_closed_for_missing_credential(monkeypatch) -> None:
    monkeypatch.delenv("SCHOLAR_TEST_TOKEN", raising=False)
    result = run_probe(httpx.MockTransport(lambda _request: httpx.Response(200)))
    assert result.ready is False
    assert result.reason == "credential_unavailable"


def test_production_readiness_url_requires_https() -> None:
    with pytest.raises(HubError) as caught:
        readiness_url("http://scholar.test/mcp", production=True)
    assert caught.value.code == "backend_unavailable"
