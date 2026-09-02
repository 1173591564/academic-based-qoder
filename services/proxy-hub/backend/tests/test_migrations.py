"""Control-plane migration integration tests."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError


def test_migrated_audit_table_rejects_updates_and_deletes(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.db"
    database_url = f"sqlite:///{database_path}"
    backend_root = Path(__file__).parents[1]
    config = Config(backend_root / "alembic.ini")
    config.set_main_option("script_location", str(backend_root / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
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
