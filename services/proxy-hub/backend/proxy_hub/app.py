"""Proxy Hub ASGI application factory."""

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import uuid4

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.base import RequestResponseEndpoint

from proxy_hub.admin import build_admin_router
from proxy_hub.auth import build_auth_components
from proxy_hub.config import Settings, get_settings
from proxy_hub.database import Database, create_database
from proxy_hub.errors import (
    HubError,
    hub_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from proxy_hub.health import build_health_router
from proxy_hub.mcp_gateway import build_mcp_gateway_router
from proxy_hub.secrets import EnvironmentSecretResolver, SecretResolver
from proxy_hub.session import build_session_router

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,96}$")


@dataclass(frozen=True)
class AppResources:
    """Resources shared by one application instance."""

    settings: Settings
    database: Database
    http_client: httpx.AsyncClient
    secret_resolver: SecretResolver
    owns_http_client: bool


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    http_client: httpx.AsyncClient | None = None,
    secret_resolver: SecretResolver | None = None,
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
        owns_http_client=http_client is None,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
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
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
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
        )
    )
    app.include_router(build_admin_router(resources.database, auth))
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
