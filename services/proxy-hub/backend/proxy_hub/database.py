"""Database engine, transaction, and request dependencies."""

from collections.abc import Generator
from dataclasses import dataclass

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from proxy_hub.config import Settings


@dataclass(frozen=True)
class Database:
    """Database resources owned by one application instance."""

    engine: Engine
    sessions: sessionmaker[Session]


def create_database(settings: Settings) -> Database:
    """Create the SQLAlchemy engine and session factory."""
    connect_args: dict[str, object] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(
        settings.database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    return Database(
        engine=engine,
        sessions=sessionmaker(bind=engine, expire_on_commit=False),
    )


def session_scope(database: Database) -> Generator[Session, None, None]:
    """Commit one unit of work or roll it back on failure."""
    session = database.sessions()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
