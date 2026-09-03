"""Quota contract calculation tests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from proxy_hub.models import (
    Base,
    QuotaPolicy,
    QuotaReservationRecord,
    QuotaWindow,
    Tenant,
)
from proxy_hub.quota import (
    DatabaseQuotaService,
    QuotaExceeded,
    load_quota_limit,
    quota_window_start,
    remaining_requests,
    retry_after_seconds,
)

AT = datetime(2026, 9, 3, 1, 37, 42, tzinfo=timezone.utc)


def seed_quota_policy(
    session: Session,
    *,
    request_limit: int,
    concurrency_limit: int,
    enforcement_enabled: bool = True,
) -> None:
    """Create one tenant and quota policy."""
    session.add(Tenant(id="tenant_quota", slug="tenant-quota", name="Quota Tenant"))
    session.add(
        QuotaPolicy(
            tenant_id="tenant_quota",
            quota_class="test",
            request_limit=request_limit,
            period_seconds=3600,
            concurrency_limit=concurrency_limit,
            enforcement_enabled=enforcement_enabled,
        )
    )
    session.commit()


def test_quota_window_start_uses_utc_epoch_boundaries() -> None:
    assert quota_window_start(AT, 3600) == datetime(
        2026,
        9,
        3,
        1,
        0,
        tzinfo=timezone.utc,
    )


def test_quota_calculations_reject_invalid_values() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        quota_window_start(datetime(2026, 9, 3), 60)
    with pytest.raises(ValueError, match="positive"):
        quota_window_start(datetime.now(timezone.utc), 0)
    with pytest.raises(ValueError, match="non-negative"):
        remaining_requests(10, -1)


def test_remaining_requests_never_becomes_negative() -> None:
    assert remaining_requests(10, 3) == 7
    assert remaining_requests(10, 12) == 0
    assert retry_after_seconds(AT, 200_000, AT) == 86_400


def test_quota_reservation_completes_once() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = DatabaseQuotaService(reservation_ttl=timedelta(seconds=30))
    with Session(engine) as session:
        seed_quota_policy(session, request_limit=2, concurrency_limit=1)
        limit = load_quota_limit(session, "tenant_quota")
        reservation = service.reserve(session, "tenant_quota", limit, AT)
        session.commit()

        assert reservation.remaining == 1
        service.complete(session, reservation, succeeded=True, at=AT)
        service.complete(session, reservation, succeeded=False, at=AT)
        session.commit()

        window = session.get(
            QuotaWindow,
            ("tenant_quota", quota_window_start(AT, 3600), 3600),
        )
        record = session.get(QuotaReservationRecord, reservation.reservation_id)
        assert window is not None
        assert window.reserved_count == 1
        assert window.active_count == 0
        assert window.completed_count == 1
        assert window.failed_count == 0
        assert record is not None
        assert record.status == "completed"
    engine.dispose()


def test_missing_and_disabled_policies_do_not_create_quota_state() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = DatabaseQuotaService(reservation_ttl=timedelta(seconds=30))
    with Session(engine) as session:
        session.add(Tenant(id="tenant_quota", slug="tenant-quota", name="Quota Tenant"))
        session.commit()
        missing = service.reserve(session, "tenant_quota", None, AT)
        assert not missing.enforced
        assert session.scalar(select(QuotaWindow)) is None

        session.add(
            QuotaPolicy(
                tenant_id="tenant_quota",
                quota_class="disabled",
                request_limit=1,
                period_seconds=3600,
                concurrency_limit=1,
                enforcement_enabled=False,
            )
        )
        session.commit()
        disabled = service.reserve(
            session,
            "tenant_quota",
            load_quota_limit(session, "tenant_quota"),
            AT,
        )
        assert not disabled.enforced
        assert session.scalar(select(QuotaWindow)) is None
    engine.dispose()


def test_request_and_concurrency_limits_fail_closed() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = DatabaseQuotaService(reservation_ttl=timedelta(seconds=30))
    with Session(engine) as session:
        seed_quota_policy(session, request_limit=2, concurrency_limit=1)
        limit = load_quota_limit(session, "tenant_quota")

        first = service.reserve(session, "tenant_quota", limit, AT)
        session.commit()
        with pytest.raises(QuotaExceeded) as concurrency_error:
            service.reserve(session, "tenant_quota", limit, AT)
        session.rollback()
        assert concurrency_error.value.reason == "concurrency_limit_exceeded"

        service.complete(session, first, succeeded=False, at=AT)
        session.commit()
        second = service.reserve(session, "tenant_quota", limit, AT)
        service.complete(session, second, succeeded=True, at=AT)
        session.commit()
        with pytest.raises(QuotaExceeded) as request_error:
            service.reserve(session, "tenant_quota", limit, AT)
        assert request_error.value.reason == "request_limit_exceeded"
        assert request_error.value.retry_after_seconds == 1338
    engine.dispose()


def test_expired_reservation_releases_concurrency_but_consumes_request() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = DatabaseQuotaService(reservation_ttl=timedelta(seconds=30))
    with Session(engine) as session:
        seed_quota_policy(session, request_limit=2, concurrency_limit=1)
        limit = load_quota_limit(session, "tenant_quota")

        first = service.reserve(session, "tenant_quota", limit, AT)
        session.commit()
        second = service.reserve(
            session,
            "tenant_quota",
            limit,
            AT + timedelta(seconds=31),
        )
        session.commit()

        window = session.get(
            QuotaWindow,
            ("tenant_quota", quota_window_start(AT, 3600), 3600),
        )
        first_record = session.get(
            QuotaReservationRecord,
            first.reservation_id,
        )
        assert second.remaining == 0
        assert window is not None
        assert window.reserved_count == 2
        assert window.active_count == 1
        assert window.failed_count == 1
        assert first_record is not None
        assert first_record.status == "failed"
    engine.dispose()


def test_conditional_update_prevents_concurrent_over_reservation(
    tmp_path: Path,
) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'quota-concurrency.db'}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    Base.metadata.create_all(engine)
    service = DatabaseQuotaService(reservation_ttl=timedelta(seconds=30))
    window_start = quota_window_start(AT, 3600)
    with Session(engine) as session:
        seed_quota_policy(session, request_limit=2, concurrency_limit=1)
        session.add(
            QuotaWindow(
                tenant_id="tenant_quota",
                window_start=window_start,
                period_seconds=3600,
            )
        )
        session.commit()
    barrier = Barrier(2)

    def reserve() -> str:
        with Session(engine) as session:
            limit = load_quota_limit(session, "tenant_quota")
            barrier.wait()
            try:
                service.reserve(session, "tenant_quota", limit, AT)
                session.commit()
                return "reserved"
            except QuotaExceeded as error:
                session.rollback()
                return error.reason

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = sorted(executor.map(lambda _: reserve(), range(2)))

    assert outcomes == ["concurrency_limit_exceeded", "reserved"]
    with Session(engine) as session:
        window = session.get(
            QuotaWindow,
            ("tenant_quota", window_start, 3600),
        )
        assert window is not None
        assert window.reserved_count == 1
        assert window.active_count == 1
    engine.dispose()
