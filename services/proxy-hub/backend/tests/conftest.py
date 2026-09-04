"""Shared Proxy Hub API test resources."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from proxy_hub.app import create_app
from proxy_hub.config import Settings
from proxy_hub.models import (
    Base,
    BrowserSession,
    Principal,
    RoleBinding,
    new_id,
    utc_now,
)
from proxy_hub.rbac import PLATFORM_ADMIN
from proxy_hub.security import digest_token


@dataclass(frozen=True)
class ApiHarness:
    """Authenticated test client and its control-plane database."""

    client: TestClient
    engine: Engine
    principal_id: str
    csrf_token: str

    @property
    def mutation_headers(self) -> dict[str, str]:
        return {
            "Origin": "http://testserver",
            "X-CSRF-Token": self.csrf_token,
        }


@pytest.fixture
def api_harness(monkeypatch: pytest.MonkeyPatch) -> ApiHarness:
    """Create an isolated platform-administrator browser session."""
    monkeypatch.setenv("SCHOLAR_TEST_TOKEN", "scholar-service-token")

    def scholar_backend(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/private/health/ready"):
            return httpx.Response(
                200,
                json={
                    "status": "ready",
                    "corpus_version": "corpus-v1",
                    "parsed_papers": 12,
                    "vector_chunks": 240,
                    "graph_built_at": "2026-09-03T00:00:00Z",
                    "synchronized_at": "2026-09-03T00:05:00Z",
                    "workspace_isolation": "tenant",
                },
            )
        if request.url.path.endswith("/mcp"):
            assert request.headers["authorization"] == ("Bearer scholar-service-token")
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"content": [{"type": "text", "text": "ok"}]},
                },
            )
        return httpx.Response(404)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(scholar_backend))
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    principal_id = new_id("principal")
    raw_session = "browser-session"
    csrf_token = "csrf-token"
    with Session(engine) as session:
        session.add(
            Principal(
                id=principal_id,
                issuer="https://identity.test",
                subject="platform-admin",
                email="admin@example.test",
                display_name="Platform Admin",
            )
        )
        session.add(
            RoleBinding(
                id=new_id("role"),
                principal_id=principal_id,
                tenant_id=None,
                role=PLATFORM_ADMIN,
            )
        )
        session.add(
            BrowserSession(
                id=digest_token(raw_session),
                principal_id=principal_id,
                csrf_digest=digest_token(csrf_token),
                expires_at=utc_now() + timedelta(hours=1),
            )
        )
        session.commit()
    app = create_app(
        settings=Settings(
            environment="test",
            database_url="sqlite://",
            public_origin="http://testserver",
        ),
        engine=engine,
        http_client=http_client,
    )
    with TestClient(app) as client:
        client.cookies.set("proxy_hub_session", raw_session)
        client.cookies.set("proxy_hub_csrf", csrf_token)
        yield ApiHarness(
            client=client,
            engine=engine,
            principal_id=principal_id,
            csrf_token=csrf_token,
        )
    asyncio.run(http_client.aclose())
