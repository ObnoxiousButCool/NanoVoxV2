"""Alembic migration environment.

Reads the database URL from the application settings rather than from
alembic.ini, so the URL has a single source of truth (D4).

``render_as_batch`` is enabled because SQLite cannot ALTER most column
properties in place; batch mode rebuilds the table instead. Turning it on before
the first migration avoids reworking migrations later.
"""

from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from infrastructure.config.settings import get_settings

# Importing the table definitions registers them on Base.metadata; without
# this, autogenerate would see an empty schema and propose dropping everything.
from infrastructure.persistence import tables as _tables  # noqa: F401
from infrastructure.persistence.engine import create_database_engine
from infrastructure.persistence.models import Base

target_metadata = Base.metadata


def _disable_foreign_keys(connection: Connection) -> None:
    """Turn foreign keys off for the duration of the migration, on SQLite only.

    SQLite cannot ALTER most columns, so ``batch_alter_table`` drops and recreates
    the table instead. With ``PRAGMA foreign_keys=ON`` — which the application
    engine sets — that DROP performs an implicit DELETE FROM, which fires every
    child table's ON DELETE CASCADE. A migration that only meant to add a column
    silently empties turns, layers, markers and every other child row.

    This is the documented approach for SQLite batch migrations, and the reason
    it is here rather than in the engine is that the application very much does
    want foreign keys enforced at runtime. Postgres has no such pragma — it
    supports real ALTER TABLE, so ``batch_alter_table`` never rebuilds the table
    there in the first place, and this step is a no-op.
    """
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")


def _restore_foreign_keys(connection: Connection) -> None:
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def _configure(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
        compare_server_default=True,
    )


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting to a database."""
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection) -> None:
    _disable_foreign_keys(connection)
    _configure(connection)
    try:
        with context.begin_transaction():
            context.run_migrations()
    finally:
        _restore_foreign_keys(connection)


async def _run_async(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        await connection.run_sync(_run)
        await connection.commit()
    await engine.dispose()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    asyncio.run(_run_async(create_database_engine(get_settings())))


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
