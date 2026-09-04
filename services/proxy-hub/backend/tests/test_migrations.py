"""Control-plane migration integration tests."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError


def migration_config(database_url: str) -> Config:
    """Build an isolated migration configuration."""
    backend_root = Path(__file__).parents[1]
    config = Config(backend_root / "alembic.ini")
    config.set_main_option("script_location", str(backend_root / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_migrated_audit_table_rejects_updates_and_deletes(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.db"
    database_url = f"sqlite:///{database_path}"
    config = migration_config(database_url)
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO audit_events (
                    id,
                    occurred_at,
                    request_id,
                    action,
                    resource_type,
                    outcome,
                    details
                ) VALUES (
                    'audit_test',
                    CURRENT_TIMESTAMP,
                    'req_test',
                    'test',
                    'test',
                    'accepted',
                    '{}'
                )
                """
            )
        )

    with (
        pytest.raises(DBAPIError, match="append-only"),
        engine.begin() as connection,
    ):
        connection.execute(
            text("UPDATE audit_events SET outcome = 'changed' WHERE id = 'audit_test'")
        )

    with (
        pytest.raises(DBAPIError, match="append-only"),
        engine.begin() as connection,
    ):
        connection.execute(text("DELETE FROM audit_events WHERE id = 'audit_test'"))

    engine.dispose()


def test_gateway_state_migration_upgrades_and_downgrades(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'gateway-state.db'}"
    config = migration_config(database_url)
    engine = create_engine(database_url)

    command.upgrade(config, "head")

    inspector = inspect(engine)
    assert {
        "enrolment_tokens",
        "quota_windows",
        "quota_reservations",
        "mcp_session_affinities",
    }.issubset(inspector.get_table_names())
    assert {
        "capability_id",
        "mcp_session_digest",
        "tool_name",
        "argument_digest",
        "backend_id",
        "corpus_version",
        "decision",
        "latency_ms",
        "result_class",
        "returned_bytes",
        "quota_delta",
    }.issubset({column["name"] for column in inspector.get_columns("audit_events")})
    assert {
        "issued_from_enrolment_id",
        "session_label",
        "last_used_at",
    }.issubset({column["name"] for column in inspector.get_columns("dsh_capabilities")})
    assert "corpus_version" in {
        column["name"] for column in inspector.get_columns("mcp_session_affinities")
    }
    assert {"version", "revoked_at"}.issubset(
        {column["name"] for column in inspector.get_columns("role_bindings")}
    )
    assert "version" in {
        column["name"] for column in inspector.get_columns("enrolment_tokens")
    }
    assert {"concurrency_limit", "enforcement_enabled"}.issubset(
        {column["name"] for column in inspector.get_columns("quota_policies")}
    )
    assert "active_count" in {
        column["name"] for column in inspector.get_columns("quota_windows")
    }
    assert "last_probe_reason" in {
        column["name"] for column in inspector.get_columns("scholar_backends")
    }

    command.downgrade(config, "d737c231b0eb")

    inspector = inspect(engine)
    assert "enrolment_tokens" not in inspector.get_table_names()
    assert "quota_windows" not in inspector.get_table_names()
    assert "quota_reservations" not in inspector.get_table_names()
    assert "mcp_session_affinities" not in inspector.get_table_names()
    assert "capability_id" not in {
        column["name"] for column in inspector.get_columns("audit_events")
    }
    assert "issued_from_enrolment_id" not in {
        column["name"] for column in inspector.get_columns("dsh_capabilities")
    }
    assert "revoked_at" not in {
        column["name"] for column in inspector.get_columns("role_bindings")
    }
    engine.dispose()


def test_quota_migration_preserves_existing_disabled_policies(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'quota-upgrade.db'}"
    config = migration_config(database_url)
    engine = create_engine(database_url)
    command.upgrade(config, "e87fa9c478bf")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO tenants (
                    id, slug, name, status, created_at, updated_at, version
                ) VALUES (
                    'tenant_existing',
                    'existing',
                    'Existing',
                    'active',
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP,
                    1
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO quota_policies (
                    tenant_id,
                    quota_class,
                    request_limit,
                    period_seconds,
                    created_at,
                    updated_at,
                    version
                ) VALUES (
                    'tenant_existing',
                    'standard',
                    100,
                    3600,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP,
                    1
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO quota_windows (
                    tenant_id,
                    window_start,
                    period_seconds,
                    reserved_count,
                    completed_count,
                    failed_count,
                    updated_at
                ) VALUES (
                    'tenant_existing',
                    CURRENT_TIMESTAMP,
                    3600,
                    4,
                    3,
                    1,
                    CURRENT_TIMESTAMP
                )
                """
            )
        )

    command.upgrade(config, "head")
    with engine.connect() as connection:
        policy = connection.execute(
            text(
                """
                SELECT concurrency_limit, enforcement_enabled
                FROM quota_policies
                WHERE tenant_id = 'tenant_existing'
                """
            )
        ).one()
        window = connection.execute(
            text(
                """
                SELECT active_count
                FROM quota_windows
                WHERE tenant_id = 'tenant_existing'
                """
            )
        ).one()
    assert tuple(policy) == (1, 0)
    assert tuple(window) == (0,)

    command.downgrade(config, "e87fa9c478bf")
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    """
                SELECT reserved_count
                FROM quota_windows
                WHERE tenant_id = 'tenant_existing'
                """
                )
            )
            == 4
        )
    engine.dispose()
