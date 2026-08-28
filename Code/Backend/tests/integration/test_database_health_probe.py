"""The database probe must report failure rather than raise it."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from domain.errors import ConfigurationError
from domain.value_objects.health import ComponentStatus
from infrastructure.persistence.engine import create_database_engine, verify_connection
from infrastructure.persistence.health_probe import DatabaseHealthProbe
from tests.support.settings import make_settings


def _engine(database_url: str) -> AsyncEngine:
    return create_database_engine(make_settings(database_url=database_url))


async def test_probe_reports_up_against_a_real_database(tmp_path: Path) -> None:
    engine = _engine(f"sqlite+aiosqlite:///{(tmp_path / 'probe.db').as_posix()}")
    try:
        result = await DatabaseHealthProbe(engine).check()
    finally:
        await engine.dispose()

    assert result.status is ComponentStatus.UP
    assert result.name == "database"


async def test_probe_reports_down_instead_of_raising(tmp_path: Path) -> None:
    # A directory where the database file should be: opening it fails at connect time.
    blocked = tmp_path / "blocked.db"
    blocked.mkdir()
    engine = _engine(f"sqlite+aiosqlite:///{blocked.as_posix()}")

    try:
        result = await DatabaseHealthProbe(engine).check()
    finally:
        await engine.dispose()

    assert result.status is ComponentStatus.DOWN
    assert result.detail is not None


async def test_engine_creates_the_database_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deeper" / "nanovox.db"
    engine = _engine(f"sqlite+aiosqlite:///{target.as_posix()}")

    try:
        await verify_connection(engine)
    finally:
        await engine.dispose()

    assert target.parent.is_dir()


def test_unusable_database_directory_is_a_configuration_error(tmp_path: Path) -> None:
    # A file where a directory is required — the engine cannot create the parent.
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="cannot be created"):
        _engine(f"sqlite+aiosqlite:///{(blocker / 'nanovox.db').as_posix()}")


async def test_connection_pragmas_are_applied(tmp_path: Path) -> None:
    # WAL lets the dashboard read while a corpus run writes; foreign keys are off
    # by default in SQLite and must be switched on explicitly; the busy timeout
    # turns a transient lock into a wait rather than an immediate failure.
    engine = _engine(f"sqlite+aiosqlite:///{(tmp_path / 'pragmas.db').as_posix()}")
    try:
        async with engine.connect() as connection:
            journal_mode = (await connection.execute(text("PRAGMA journal_mode"))).scalar_one()
            foreign_keys = (await connection.execute(text("PRAGMA foreign_keys"))).scalar_one()
            busy_timeout = (await connection.execute(text("PRAGMA busy_timeout"))).scalar_one()
    finally:
        await engine.dispose()

    assert str(journal_mode).lower() == "wal"
    assert foreign_keys == 1
    assert busy_timeout > 0
