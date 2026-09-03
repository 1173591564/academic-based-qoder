"""Quota lifecycle helpers for streaming MCP responses."""

from collections.abc import AsyncIterator

import anyio
import httpx

from proxy_hub.database import Database
from proxy_hub.mcp_transport import stream_body
from proxy_hub.models import utc_now
from proxy_hub.quota import QuotaReservation, QuotaService


async def stream_with_quota(
    response: httpx.Response,
    database: Database,
    quota_service: QuotaService,
    reservation: QuotaReservation,
    *,
    refresh_seconds: float,
    maximum_bytes: int,
) -> AsyncIterator[bytes]:
    """Relay a response while refreshing and finally settling its lease."""
    completed = False
    active_reservation = reservation
    stopped = anyio.Event()
    returned_bytes = 0

    async def refresh_lease() -> None:
        nonlocal active_reservation
        while True:
            with anyio.move_on_after(refresh_seconds):
                await stopped.wait()
            if stopped.is_set():
                return
            with database.sessions() as session:
                active_reservation = quota_service.refresh(
                    session,
                    active_reservation,
                    at=utc_now(),
                )
                session.commit()

    try:
        async with anyio.create_task_group() as task_group:
            if active_reservation.enforced:
                task_group.start_soon(refresh_lease)
            try:
                async for chunk in stream_body(response):
                    returned_bytes += len(chunk)
                    if returned_bytes > maximum_bytes:
                        raise RuntimeError(
                            "Scholar response exceeded the configured limit"
                        )
                    yield chunk
            finally:
                stopped.set()
        completed = True
    finally:
        with database.sessions() as session:
            quota_service.complete(
                session,
                active_reservation,
                succeeded=completed and response.status_code < 400,
                at=utc_now(),
            )
            session.commit()
