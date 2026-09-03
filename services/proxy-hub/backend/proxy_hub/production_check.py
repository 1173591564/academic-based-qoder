"""Production configuration and migration preflight checks."""

from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine

from proxy_hub.config import Settings
from proxy_hub.database import create_database


def migration_config() -> Config:
    """Load the packaged Proxy Hub Alembic graph."""
    candidates = (
        Path.cwd(),
        Path(__file__).resolve().parents[1],
    )
    backend_root = next(
        (
            candidate
            for candidate in candidates
            if (candidate / "alembic.ini").is_file()
            and (candidate / "migrations").is_dir()
        ),
        None,
    )
    if backend_root is None:
        raise RuntimeError("Proxy Hub Alembic files are unavailable")
    config = Config(backend_root / "alembic.ini")
    config.set_main_option(
        "script_location",
        str(backend_root / "migrations"),
    )
    return config


def assert_migrations_current(engine: Engine) -> None:
    """Fail when the connected database is not at every Alembic head."""
    config = migration_config()
    expected_heads = set(ScriptDirectory.from_config(config).get_heads())
    with engine.connect() as connection:
        current_heads = set(MigrationContext.configure(connection).get_current_heads())
    if current_heads != expected_heads:
        raise RuntimeError("control database migrations are not current")


def main() -> None:
    """Validate production settings, database connectivity, and migrations."""
    settings = Settings()
    if settings.environment != "production":
        raise RuntimeError(
            "production preflight requires PROXY_HUB_ENVIRONMENT=production"
        )
    database = create_database(settings)
    try:
        assert_migrations_current(database.engine)
    finally:
        database.engine.dispose()
    print("Proxy Hub production preflight passed.")


if __name__ == "__main__":
    main()
