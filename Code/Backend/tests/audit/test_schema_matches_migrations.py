"""The migrations and the ORM mapping must describe the same schema.

Tests build their database from ``Base.metadata`` because it is fast. Production
builds it from Alembic. If those two drift, the suite passes against a schema
that does not exist anywhere real — which is the worst kind of green.

This test runs the migrations for real, once, and compares the result to the
mapping.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from infrastructure.config.paths import BACKEND_ROOT
from infrastructure.persistence import tables as _tables  # noqa: F401
from infrastructure.persistence.models import Base

# Alembic keeps its own bookkeeping table, which the ORM knows nothing about.
_ALEMBIC_TABLE = "alembic_version"


@pytest.fixture(scope="module")
def migrated_database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A database built by running every migration in order."""
    database = tmp_path_factory.mktemp("migrations") / "migrated.db"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        # Inherit the environment: a stripped one cannot start Python on Windows,
        # which needs SystemRoot to seed hash randomisation.
        env={
            **os.environ,
            "DATABASE_URL": f"sqlite+aiosqlite:///{database.as_posix()}",
            "LOG_ENABLED": "false",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(f"alembic upgrade head failed:\n{result.stdout}\n{result.stderr}")
    return database


def test_the_migrations_create_every_mapped_table(migrated_database: Path) -> None:
    engine = create_engine(f"sqlite:///{migrated_database.as_posix()}")
    try:
        migrated = set(inspect(engine).get_table_names()) - {_ALEMBIC_TABLE}
    finally:
        engine.dispose()

    assert migrated == set(Base.metadata.tables)


def test_every_mapped_column_exists_in_the_migrated_schema(migrated_database: Path) -> None:
    engine = create_engine(f"sqlite:///{migrated_database.as_posix()}")
    try:
        inspector = inspect(engine)
        differences: list[str] = []
        for name, table in Base.metadata.tables.items():
            migrated = {column["name"] for column in inspector.get_columns(name)}
            mapped = {column.name for column in table.columns}
            if migrated != mapped:
                differences.append(
                    f"{name}: only in migrations {sorted(migrated - mapped)}, "
                    f"only in mapping {sorted(mapped - migrated)}"
                )
    finally:
        engine.dispose()

    assert not differences, "Schema drift between migrations and ORM:\n" + "\n".join(differences)
