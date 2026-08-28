"""The ORM naming convention must be in place before the first table exists.

Retrofitting it later would mean rewriting migrations, because SQLite leaves
unnamed constraints that Alembic then cannot alter.
"""

from __future__ import annotations

from infrastructure.persistence import tables as _tables  # noqa: F401
from infrastructure.persistence.models import NAMING_CONVENTION, Base


def test_metadata_uses_the_explicit_naming_convention() -> None:
    assert Base.metadata.naming_convention == NAMING_CONVENTION


def test_every_constraint_type_is_named() -> None:
    assert set(NAMING_CONVENTION) == {"ix", "uq", "ck", "fk", "pk"}


def test_the_expected_tables_are_mapped() -> None:
    # Replaced the P0 tripwire, which asserted an empty schema and fired the
    # moment P3 added tables — which is what it was there for.
    assert set(Base.metadata.tables) == {
        "calls",
        "turns",
        "analysis_layers",
        "score_markers",
        "l4_signals",
        "broker_signals",
        "assist_events",
        "call_signals",
    }


def test_every_child_table_cascades_from_its_call() -> None:
    # An analysis is one atomic thing; a half-deleted one would be worse than
    # either state.
    for name, table in Base.metadata.tables.items():
        if name == "calls":
            continue
        call_fk = next(fk for fk in table.foreign_keys if fk.column.table.name == "calls")
        assert call_fk.ondelete == "CASCADE", name


def test_constraints_are_named_by_the_convention() -> None:
    # Unnamed constraints cannot be altered by a later migration on SQLite.
    for table in Base.metadata.tables.values():
        for constraint in table.constraints:
            assert constraint.name, f"{table.name} has an unnamed constraint"
