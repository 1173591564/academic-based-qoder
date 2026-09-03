"""Streaming quota lease lifecycle tests."""

import asyncio
from collections.abc import AsyncIterator
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from proxy_hub.database import Database
from proxy_hub.mcp_quota import stream_with_quota
from proxy_hub.models import (
    Base,
    QuotaReservationRecord,
    QuotaWindow,
    Tenant,
    utc_now,
)
from proxy_hub.quota import DatabaseQuotaService, QuotaLimit, QuotaReservation


class DelayedStream(httpx.AsyncByteStream):
    """Emit one response chunk after an idle interval."""

    async def __aiter__(self) -> AsyncIterator[bytes]:
        await asyncio.sleep(0.08)
        yield b"response"


class InterruptedStream(httpx.AsyncByteStream):
    """Fail after starting the upstream response."""

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield b"partial"
        raise RuntimeError("stream interrupted")


def quota_state() -> tuple[
    Engine,
    Database,
    DatabaseQuotaService,
    QuotaReservation,
]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    database = Database(
        engine=engine,
        sessions=sessionmaker(bind=engine, expire_on_commit=False),
    )
    service = DatabaseQuotaService(timedelta(seconds=0.05))
    now = utc_now()
    with Session(engine) as session:
        session.add(Tenant(id="tenant_stream", slug="stream", name="Stream"))
        session.commit()
        reservation = service.reserve(
            session,
            "tenant_stream",
            QuotaLimit(
                quota_class="test",
                request_limit=1,
                period_seconds=3600,
                concurrency_limit=1,
                enforcement_enabled=True,
            ),
            now,
        )
        session.commit()
    return engine, database, service, reservation


def test_idle_stream_refreshes_and_completes_quota_lease() -> None:
    engine, database, service, reservation = quota_state()

    async def consume() -> bytes:
        response = httpx.Response(200, stream=DelayedStream())
        chunks = [
            chunk
            async for chunk in stream_with_quota(
                response,
                database,
                service,
                reservation,
                refresh_seconds=0.02,
            )
        ]
        return b"".join(chunks)

    assert asyncio.run(consume()) == b"response"
    with Session(engine) as session:
        record = session.get(QuotaReservationRecord, reservation.reservation_id)
        window = session.scalar(
            select(QuotaWindow).where(QuotaWindow.tenant_id == "tenant_stream")
        )
        assert record is not None
        assert record.status == "completed"
        assert record.expires_at != reservation.expires_at
        assert window is not None
        assert window.active_count == 0
        assert window.completed_count == 1
    engine.dispose()


def test_interrupted_stream_fails_and_releases_quota_lease() -> None:
    engine, database, service, reservation = quota_state()

    async def consume() -> None:
        response = httpx.Response(200, stream=InterruptedStream())
        async for _chunk in stream_with_quota(
            response,
            database,
            service,
            reservation,
            refresh_seconds=0.02,
        ):
            pass

    with pytest.RaisesGroup(RuntimeError) as error:
        asyncio.run(consume())
    assert str(error.value.exceptions[0]) == "stream interrupted"
    with Session(engine) as session:
        record = session.get(QuotaReservationRecord, reservation.reservation_id)
        window = session.scalar(
            select(QuotaWindow).where(QuotaWindow.tenant_id == "tenant_stream")
        )
        assert record is not None
        assert record.status == "failed"
        assert window is not None
        assert window.active_count == 0
        assert window.failed_count == 1
    engine.dispose()
