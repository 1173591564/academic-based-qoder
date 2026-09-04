"""Scholar readiness probe safety tests."""

import asyncio

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from proxy_hub.backend_probe import ProbeResult, probe_scholar_backend, readiness_url
from proxy_hub.config import Settings
from proxy_hub.database import Database
from proxy_hub.errors import HubError
from proxy_hub.models import Base, ScholarBackend, TenantRoute
from proxy_hub.secrets import EnvironmentSecretResolver
from proxy_hub.single_lab import bootstrap_single_lab, refresh_single_lab_backend


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


def test_single_lab_refresh_keeps_route_eligible(monkeypatch) -> None:
    monkeypatch.setenv("SCHOLAR_TEST_TOKEN", "service-token")
    settings = Settings(
        environment="development",
        database_url="sqlite://",
        public_origin="http://127.0.0.1:8000",
        single_lab_backend_url="http://scholar.test/mcp",
        single_lab_corpus_version="corpus-v1",
        single_lab_backend_credential_ref="env:SCHOLAR_TEST_TOKEN",
    )
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    database = Database(
        engine=engine,
        sessions=sessionmaker(bind=engine, expire_on_commit=False),
    )
    bootstrap_single_lab(database, settings)

    def backend(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "ready",
                "corpus_version": "corpus-v1",
                "parsed_papers": 563,
                "vector_chunks": 0,
                "workspace_isolation": "shared",
            },
        )

    async def refresh() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(backend),
        ) as client:
            await refresh_single_lab_backend(
                database,
                settings,
                client,
                EnvironmentSecretResolver(),
            )

    asyncio.run(refresh())

    with Session(engine) as session:
        backend_row = session.query(ScholarBackend).one()
        route = session.query(TenantRoute).one()
        assert backend_row.status == "active"
        assert backend_row.last_probe_ready is True
        assert backend_row.last_probe_reason == "ready"
        assert backend_row.last_probe_at is not None
        assert backend_row.capacity["parsed_papers"] == 563
        assert route.status == "active"
