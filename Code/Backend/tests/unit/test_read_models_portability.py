"""The dashboard's aggregate queries must run on Postgres, not only SQLite (D4).

``GROUP_CONCAT`` is a SQLite/MySQL function; Postgres has no such function and
would fail the query outright. ``_joined_references`` is the one seam where
this is resolved, so it is asserted directly rather than trusted by reading.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from infrastructure.persistence.repositories.read_models import _joined_references
from infrastructure.persistence.tables import CallRow


@dataclass
class _FakeDialect:
    name: str


@dataclass
class _FakeBind:
    dialect: _FakeDialect


@dataclass
class _FakeSession:
    """A stand-in exposing only what `_joined_references` reads: `.bind.dialect.name`."""

    bind: _FakeBind | None


def _session(dialect_name: str | None) -> Any:
    return _FakeSession(bind=_FakeBind(_FakeDialect(dialect_name)) if dialect_name else None)


def test_sqlite_uses_group_concat() -> None:
    expression = _joined_references(_session("sqlite"), CallRow.reference)

    assert "group_concat" in str(expression)


def test_postgres_uses_string_agg_not_group_concat() -> None:
    expression = _joined_references(_session("postgresql"), CallRow.reference)

    rendered = str(expression)
    assert "string_agg" in rendered
    assert "group_concat" not in rendered


def test_distinct_values_is_threaded_through_for_both_dialects() -> None:
    sqlite_expression = str(
        _joined_references(_session("sqlite"), CallRow.reference, distinct_values=True)
    )
    postgres_expression = str(
        _joined_references(_session("postgresql"), CallRow.reference, distinct_values=True)
    )

    assert "DISTINCT" in sqlite_expression
    assert "DISTINCT" in postgres_expression


def test_a_session_with_no_bind_yet_defaults_to_sqlite() -> None:
    # A statement can be built before a connection is checked out; falling back
    # to SQLite here matches the application's own local/default database.
    expression = _joined_references(_session(None), CallRow.reference)

    assert "group_concat" in str(expression)
