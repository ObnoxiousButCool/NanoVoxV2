"""Async SQLAlchemy engine and session factory.

SQLite is configured for the access pattern this application actually has: a
background corpus run writing while the dashboard reads. Write-ahead logging lets
readers proceed during a write, and a busy timeout turns a transient lock into a
short wait instead of an immediate ``database is locked`` error. Postgres needs
none of this — a real database server already handles concurrent readers and
writers itself — so the pragmas below are conditional on the engine actually
being SQLite.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from domain.errors import ConfigurationError
from infrastructure.config.settings import Settings

logger = logging.getLogger(__name__)

_BUSY_TIMEOUT_MS = 5_000


def _apply_sqlite_pragmas(dbapi_connection: Any, _record: Any) -> None:
    """Apply connection-level SQLite settings.

    Registered on the sync engine because pragmas are set on the raw DB-API
    connection, which is what SQLAlchemy hands to the ``connect`` event even for
    an async engine.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
    finally:
        cursor.close()


def create_database_engine(settings: Settings) -> AsyncEngine:
    """Create the async engine, ensuring the database directory exists."""
    database_file = settings.database_file
    if database_file is not None:
        try:
            database_file.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ConfigurationError(
                f"DATABASE_URL points at a directory that cannot be created: "
                f"{database_file.parent}",
                detail=str(exc),
            ) from exc

    engine = create_async_engine(settings.database_url, echo=settings.db_echo, future=True)
    # Postgres has no equivalent of these pragmas and would reject them outright
    # on every new connection; only SQLite gets them.
    if engine.dialect.name == "sqlite":
        event.listen(engine.sync_engine, "connect", _apply_sqlite_pragmas)
    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create the session factory used by repositories and units of work."""
    return async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


async def verify_connection(engine: AsyncEngine) -> None:
    """Open one connection at startup so a broken database fails fast.

    Without this the first failure would surface inside a request, long after the
    process reported itself as started.
    """
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    logger.info("Database connection verified", extra={"database": engine.url.render_as_string()})
