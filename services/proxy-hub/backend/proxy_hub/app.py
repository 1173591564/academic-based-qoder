"""Proxy Hub ASGI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import uuid4

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
from proxy_hub.session import build_session_router


@dataclass(frozen=True)
class AppResources:
    """Resources shared by one application instance."""

    settings: Settings
    database: Database


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
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
    resources = AppResources(settings=active_settings, database=database)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
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
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid4().hex}"
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
