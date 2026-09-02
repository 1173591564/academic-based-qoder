"""Private health endpoint tests."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from proxy_hub.app import create_app
from proxy_hub.config import Settings


def test_health_endpoints() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = create_app(
        settings=Settings(environment="test", database_url="sqlite://"),
        engine=engine,
    )

    with TestClient(app) as client:
        live = client.get("/private/health/live")
        ready = client.get("/private/health/ready")

    assert live.status_code == 200
    assert live.json() == {"status": "live"}
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}
    assert live.headers["X-Request-ID"].startswith("req_")
