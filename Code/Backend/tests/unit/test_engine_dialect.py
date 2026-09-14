"""The SQLite-only pragmas must never reach a Postgres connection (D4).

Postgres rejects ``PRAGMA`` outright — it is not a no-op, it is a syntax error
on every single connection. The engine must only wire the pragma listener up
for SQLite, never unconditionally.
"""

from __future__ import annotations

from sqlalchemy import event

from infrastructure.persistence.engine import (
    _apply_sqlite_pragmas,
    _connect_args_for,
    create_database_engine,
)
from tests.support.settings import make_settings


def test_sqlite_engine_gets_the_pragma_listener() -> None:
    engine = create_database_engine(make_settings(database_url="sqlite+aiosqlite:///:memory:"))

    assert event.contains(engine.sync_engine, "connect", _apply_sqlite_pragmas)


def test_postgres_engine_does_not_get_the_pragma_listener() -> None:
    # No real server is contacted here — constructing an async engine does not
    # open a connection, so this is safe without a live Postgres instance.
    engine = create_database_engine(
        make_settings(database_url="postgresql+asyncpg://user:password@localhost/db")
    )

    assert engine.dialect.name == "postgresql"
    assert not event.contains(engine.sync_engine, "connect", _apply_sqlite_pragmas)


def test_postgres_disables_asyncpgs_statement_cache() -> None:
    # Required against a PgBouncer-pooled endpoint (Neon's, among others) in
    # transaction-pooling mode — see the docstring in engine.py for why.
    assert _connect_args_for("postgresql+asyncpg://user:password@host/db") == {
        "statement_cache_size": 0
    }


def test_sqlite_gets_no_special_connect_args() -> None:
    assert _connect_args_for("sqlite+aiosqlite:///:memory:") == {}
