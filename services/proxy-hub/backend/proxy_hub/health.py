"""Private health endpoints."""

from fastapi import APIRouter
from sqlalchemy import text

from proxy_hub.database import Database
from proxy_hub.errors import HubError


def build_health_router(database: Database) -> APIRouter:
    """Build health routes bound to application database resources."""
    router = APIRouter(prefix="/private/health", tags=["private"])

    @router.get("/live")
    def live() -> dict[str, str]:
        return {"status": "live"}

    @router.get("/ready")
    def ready() -> dict[str, str]:
        try:
            with database.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as exc:
            raise HubError(
                503,
                "control_database_unavailable",
                "The control-plane database is unavailable.",
            ) from exc
        return {"status": "ready"}

    return router
