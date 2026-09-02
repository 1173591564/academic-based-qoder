"""Shared Proxy Hub API test resources."""

from dataclasses import dataclass
from datetime import timedelta

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
def api_harness() -> ApiHarness:
    """Create an isolated platform-administrator browser session."""
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
