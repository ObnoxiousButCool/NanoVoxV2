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


# The tables that make up one analysis. Deleting the call deletes all of them.
ANALYSIS_TABLES = frozenset(
    {
        "turns",
        "analysis_layers",
        "score_markers",
        "l4_signals",
        "broker_signals",
        "assist_events",
        "call_signals",
    }
)

# The corpus run record (P7) and the authored expectations it stores (A3). These
# are about calls without being part of one.
RUN_TABLES = frozenset({"analysis_runs", "analysis_run_items", "ground_truth"})


def test_the_expected_tables_are_mapped() -> None:
    # Replaced the P0 tripwire, which asserted an empty schema and fired the
    # moment P3 added tables — which is what it was there for.
    assert set(Base.metadata.tables) == {"calls"} | ANALYSIS_TABLES | RUN_TABLES


def test_every_part_of_an_analysis_cascades_from_its_call() -> None:
    # An analysis is one atomic thing; a half-deleted one would be worse than
    # either state.
    for name in ANALYSIS_TABLES:
        table = Base.metadata.tables[name]
        call_fk = next(fk for fk in table.foreign_keys if fk.column.table.name == "calls")
        assert call_fk.ondelete == "CASCADE", name


def test_a_run_item_survives_the_call_it_produced() -> None:
    # The opposite rule, and deliberately so: deleting a call must not erase the
    # record that a run once analyzed it. The item stays, with nothing to open.
    table = Base.metadata.tables["analysis_run_items"]
    call_fk = next(fk for fk in table.foreign_keys if fk.column.table.name == "calls")

    assert call_fk.ondelete == "SET NULL"
    assert table.c.call_id.nullable


def test_run_items_cascade_from_their_run() -> None:
    table = Base.metadata.tables["analysis_run_items"]
    run_fk = next(fk for fk in table.foreign_keys if fk.column.table.name == "analysis_runs")

    assert run_fk.ondelete == "CASCADE"


def test_ground_truth_stands_apart_from_the_calls_table() -> None:
    # Plan A3: authored figures are never joined into analysis data. No foreign
    # key to `calls` is what keeps that accidental join from being easy to write.
    assert not Base.metadata.tables["ground_truth"].foreign_keys


def test_constraints_are_named_by_the_convention() -> None:
    # Unnamed constraints cannot be altered by a later migration on SQLite.
    for table in Base.metadata.tables.values():
        for constraint in table.constraints:
            assert constraint.name, f"{table.name} has an unnamed constraint"
