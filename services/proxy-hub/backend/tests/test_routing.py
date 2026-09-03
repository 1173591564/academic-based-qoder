"""Tenant route and MCP affinity isolation tests."""

from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from proxy_hub.models import (
    Base,
    DshCapability,
    McpSessionAffinity,
    Principal,
    ScholarBackend,
    Tenant,
    TenantRoute,
    utc_now,
)
from proxy_hub.routing import RouteResolutionError, resolve_route

MAX_PROBE_AGE = timedelta(minutes=5)


def add_route_state(session: Session) -> None:
    """Create one active tenant, backend, route, and capability."""
    now = utc_now()
    session.add(
        Principal(
            id="principal_test",
            issuer="https://issuer.test",
            subject="principal-test",
        )
    )
    session.add(Tenant(id="tenant_test", slug="tenant-test", name="Tenant"))
    session.add(
        ScholarBackend(
            id="backend_test",
            name="Scholar Test",
            base_url="https://scholar.test/mcp",
            corpus_version="corpus-v1",
            credential_ref="env:SCHOLAR_TEST_TOKEN",
            status="active",
            last_probe_at=now,
            last_probe_ready=True,
        )
    )
    session.add(
        TenantRoute(
            tenant_id="tenant_test",
            backend_id="backend_test",
            corpus_version="corpus-v1",
        )
    )
    session.add(
        DshCapability(
            id="cap_test",
            token_digest="capability_digest",
            principal_id="principal_test",
            tenant_id="tenant_test",
            scopes=["scholar_search"],
            expires_at=now + timedelta(hours=1),
        )
    )
    session.commit()


def test_route_requires_explicit_ready_version_matched_backend() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        add_route_state(session)

        selection = resolve_route(
            session,
            "tenant_test",
            "cap_test",
            utc_now(),
            MAX_PROBE_AGE,
        )

        assert selection.backend_id == "backend_test"
        assert selection.corpus_version == "corpus-v1"
        assert selection.workspace_writes_allowed is False
        assert selection.from_affinity is False
    engine.dispose()


def test_route_affinity_is_bound_to_tenant_and_capability() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        add_route_state(session)
        session.add(
            McpSessionAffinity(
                session_digest="session_digest",
                tenant_id="tenant_test",
                backend_id="backend_test",
                corpus_version="corpus-v1",
                capability_id="cap_test",
                expires_at=utc_now() + timedelta(hours=1),
            )
        )
        session.commit()

        selection = resolve_route(
            session,
            "tenant_test",
            "cap_test",
            utc_now(),
            MAX_PROBE_AGE,
            mcp_session_digest="session_digest",
        )
        assert selection.from_affinity is True

        with pytest.raises(RouteResolutionError) as error:
            resolve_route(
                session,
                "tenant_test",
                "another_capability",
                utc_now(),
                MAX_PROBE_AGE,
                mcp_session_digest="session_digest",
            )
        assert error.value.code == "session_affinity_mismatch"

        session.add(Tenant(id="tenant_other", slug="tenant-other", name="Other"))
        session.add(
            TenantRoute(
                tenant_id="tenant_other",
                backend_id="backend_test",
                corpus_version="corpus-v1",
            )
        )
        session.commit()
        with pytest.raises(RouteResolutionError) as error:
            resolve_route(
                session,
                "tenant_other",
                "cap_test",
                utc_now(),
                MAX_PROBE_AGE,
                mcp_session_digest="session_digest",
            )
        assert error.value.code == "session_affinity_mismatch"
    engine.dispose()


def test_route_rejects_unknown_session_affinity() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        add_route_state(session)

        with pytest.raises(RouteResolutionError) as error:
            resolve_route(
                session,
                "tenant_test",
                "cap_test",
                utc_now(),
                MAX_PROBE_AGE,
                mcp_session_digest="unknown_session",
            )

        assert error.value.code == "session_affinity_missing"
    engine.dispose()


def test_route_rejects_expired_session_affinity() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        add_route_state(session)
        session.add(
            McpSessionAffinity(
                session_digest="expired_session",
                tenant_id="tenant_test",
                backend_id="backend_test",
                corpus_version="corpus-v1",
                capability_id="cap_test",
                expires_at=utc_now() - timedelta(seconds=1),
            )
        )
        session.commit()

        with pytest.raises(RouteResolutionError) as error:
            resolve_route(
                session,
                "tenant_test",
                "cap_test",
                utc_now(),
                MAX_PROBE_AGE,
                mcp_session_digest="expired_session",
            )

        assert error.value.code == "session_affinity_missing"
    engine.dispose()


def test_route_fails_closed_for_unready_backend() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        add_route_state(session)
        backend = session.get(ScholarBackend, "backend_test")
        assert backend is not None
        backend.last_probe_ready = False
        session.commit()

        with pytest.raises(RouteResolutionError) as error:
            resolve_route(
                session,
                "tenant_test",
                "cap_test",
                utc_now(),
                MAX_PROBE_AGE,
            )

        assert error.value.code == "backend_unready"
    engine.dispose()


def test_route_rejects_stale_backend_probe() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        add_route_state(session)
        backend = session.get(ScholarBackend, "backend_test")
        assert backend is not None
        backend.last_probe_at = utc_now() - timedelta(minutes=10)
        session.commit()

        with pytest.raises(RouteResolutionError) as error:
            resolve_route(
                session,
                "tenant_test",
                "cap_test",
                utc_now(),
                MAX_PROBE_AGE,
            )

        assert error.value.code == "backend_probe_stale"
    engine.dispose()


def test_affinity_does_not_bypass_explicit_active_route() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        add_route_state(session)
        session.add(
            McpSessionAffinity(
                session_digest="session_digest",
                tenant_id="tenant_test",
                backend_id="backend_test",
                corpus_version="corpus-v1",
                capability_id="cap_test",
                expires_at=utc_now() + timedelta(hours=1),
            )
        )
        route = session.get(TenantRoute, "tenant_test")
        assert route is not None
        route.status = "disabled"
        session.commit()

        with pytest.raises(RouteResolutionError) as error:
            resolve_route(
                session,
                "tenant_test",
                "cap_test",
                utc_now(),
                MAX_PROBE_AGE,
                mcp_session_digest="session_digest",
            )

        assert error.value.code == "route_missing"
    engine.dispose()
