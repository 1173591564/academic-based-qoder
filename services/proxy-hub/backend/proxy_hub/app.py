"""Proxy Hub ASGI application factory."""

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.base import RequestResponseEndpoint

from proxy_hub.admin import build_admin_router
from proxy_hub.admin_rate_limit import consume_admin_request
from proxy_hub.audit import AuditEntry, append_audit_event
from proxy_hub.auth import build_auth_components, ensure_utc
from proxy_hub.circuit import BackendCircuitBreaker
from proxy_hub.config import Settings, get_settings
from proxy_hub.database import Database, create_database
from proxy_hub.errors import (
    HubError,
    error_response,
    hub_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from proxy_hub.health import build_health_router
from proxy_hub.mcp_gateway import build_mcp_gateway_router
from proxy_hub.models import BrowserSession, utc_now
from proxy_hub.production_check import assert_migrations_current
from proxy_hub.quota import DatabaseQuotaService, QuotaService
from proxy_hub.secrets import EnvironmentSecretResolver, SecretResolver
from proxy_hub.security import digest_token
from proxy_hub.session import build_session_router

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,96}$")


@dataclass(frozen=True)
class AppResources:
    """Resources shared by one application instance."""

    settings: Settings
    database: Database
    http_client: httpx.AsyncClient
    secret_resolver: SecretResolver
    quota_service: QuotaService
    circuit_breaker: BackendCircuitBreaker
    owns_http_client: bool


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    http_client: httpx.AsyncClient | None = None,
    secret_resolver: SecretResolver | None = None,
    quota_service: QuotaService | None = None,
    circuit_breaker: BackendCircuitBreaker | None = None,
) -> FastAPI:
    """Create a configured Proxy Hub application."""
    active_settings = settings or get_settings()
    if engine is None:
        database = create_database(active_settings)
    else:
        database = Database(
            engine=engine,
            sessions=sessionmaker[Session](bind=engine, expire_on_commit=False),
        )
    active_http_client = http_client or httpx.AsyncClient(
        timeout=httpx.Timeout(
            active_settings.backend_request_timeout_seconds,
            connect=active_settings.backend_connect_timeout_seconds,
        ),
        follow_redirects=False,
    )
    resources = AppResources(
        settings=active_settings,
        database=database,
        http_client=active_http_client,
        secret_resolver=secret_resolver or EnvironmentSecretResolver(),
        quota_service=quota_service
        or DatabaseQuotaService(
            timedelta(seconds=active_settings.quota_reservation_ttl_seconds)
        ),
        circuit_breaker=circuit_breaker
        or BackendCircuitBreaker(
            active_settings.backend_circuit_failure_threshold,
            active_settings.backend_circuit_recovery_seconds,
        ),
        owns_http_client=http_client is None,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if resources.settings.environment == "production":
            assert_migrations_current(resources.database.engine)
        yield
        if resources.owns_http_client:
            await resources.http_client.aclose()
        resources.database.engine.dispose()

    app = FastAPI(
        title="Scholar Proxy Hub",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        supplied_request_id = request.headers.get("X-Request-ID")
        request_id = (
            supplied_request_id
            if supplied_request_id is not None
            and REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
            else f"req_{uuid4().hex}"
        )
        request.state.request_id = request_id
        rate_headers: dict[str, str] = {}
        if request.url.path.startswith("/v1/admin"):
            raw_session = request.cookies.get(active_settings.cookie_name)
            if raw_session is not None:
                rate_session = resources.database.sessions()
                try:
                    browser_session = rate_session.get(
                        BrowserSession,
                        digest_token(raw_session),
                    )
                    now = utc_now()
                    if (
                        browser_session is not None
                        and browser_session.revoked_at is None
                        and ensure_utc(browser_session.expires_at) > now
                    ):
                        decision = consume_admin_request(
                            rate_session,
                            browser_session.id,
                            request_limit=(active_settings.admin_rate_limit_requests),
                            period_seconds=(
                                active_settings.admin_rate_limit_period_seconds
                            ),
                            at=now,
                        )
                        rate_headers = {
                            "RateLimit-Limit": str(
                                active_settings.admin_rate_limit_requests
                            ),
                            "RateLimit-Remaining": str(decision.remaining),
                            "RateLimit-Reset": str(decision.retry_after_seconds),
                        }
                        if not decision.allowed:
                            append_audit_event(
                                rate_session,
                                AuditEntry(
                                    request_id=request_id,
                                    principal_id=browser_session.principal_id,
                                    action="admin:rate_limit",
                                    resource_type="administration_api",
                                    outcome="rejected",
                                    decision="deny",
                                    details={"reason": "rate_limit_exceeded"},
                                ),
                            )
                            rate_session.commit()
                            return error_response(
                                request,
                                429,
                                "admin_rate_limit_exceeded",
                                "The administration request rate is exhausted.",
                                {
                                    **rate_headers,
                                    "Retry-After": str(decision.retry_after_seconds),
                                    "X-Request-ID": request_id,
                                },
                            )
                        rate_session.commit()
                except Exception:
                    rate_session.rollback()
                    return error_response(
                        request,
                        503,
                        "control_plane_unavailable",
                        "The administration control plane is unavailable.",
                        {"X-Request-ID": request_id},
                    )
                finally:
                    rate_session.close()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        for name, value in rate_headers.items():
            response.headers[name] = value
        return response

    app.add_exception_handler(HubError, hub_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
    auth = build_auth_components(resources.database, resources.settings)
    app.include_router(auth.router)
    app.include_router(build_session_router(resources.database, resources.settings))
    app.include_router(
        build_mcp_gateway_router(
            resources.database,
            resources.settings,
            resources.http_client,
            resources.secret_resolver,
            resources.quota_service,
            resources.circuit_breaker,
        )
    )
    app.include_router(
        build_admin_router(
            resources.database,
            auth,
            resources.settings,
            resources.http_client,
            resources.secret_resolver,
        )
    )
    app.include_router(build_health_router(resources.database))
    return app


app = create_app()


def run() -> None:
    """Run the development ASGI server."""
    settings = get_settings()
    uvicorn.run(
        "proxy_hub.app:app",
        host="127.0.0.1",
        port=8000,
        reload=settings.environment == "development",
    )
