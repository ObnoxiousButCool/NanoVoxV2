"""normalise call signals into a table

Revision ID: 067891d530f7
Revises: d5d2d66f1983
Created: 2026-08-28 11:50:24.109312+00:00
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import sqlite

revision: str = "067891d530f7"
down_revision: str | None = "d5d2d66f1983"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Signal codes move from a JSON column on calls to their own table, so the
    # dashboard can both count them and filter calls by them in SQL rather than
    # in Python after pagination.
    #
    # ORDER MATTERS. On SQLite, batch_alter_table drops and recreates `calls`.
    # With PRAGMA foreign_keys=ON that drop fires call_signals' ON DELETE
    # CASCADE, so any rows written before the rebuild are wiped. The existing
    # data is therefore read into memory first, the child table is created after
    # the rebuild, and only then are the rows written.
    existing = _read_signal_codes()

    with op.batch_alter_table("calls", schema=None) as batch_op:
        batch_op.alter_column(
            "rejected_attribution_notes",
            existing_type=sqlite.JSON(),
            server_default=None,
            existing_nullable=False,
        )
        batch_op.drop_column("signal_codes")

    op.create_table(
        "call_signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("call_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["call_id"],
            ["calls.id"],
            name=op.f("fk_call_signals_call_id_calls"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_call_signals")),
        sa.UniqueConstraint("call_id", "code", name="uq_call_signals_call_id"),
    )
    with op.batch_alter_table("call_signals", schema=None) as batch_op:
        batch_op.create_index("ix_call_signals_code", ["code"], unique=False)

    _write_signal_rows(existing)


def downgrade() -> None:
    grouped = _read_signal_rows()
    op.drop_table("call_signals")

    with op.batch_alter_table("calls", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("signal_codes", sqlite.JSON(), nullable=False, server_default="[]")
        )
        batch_op.alter_column(
            "rejected_attribution_notes",
            existing_type=sqlite.JSON(),
            server_default=sa.text("'[]'"),
            existing_nullable=False,
        )

    _write_signal_codes(grouped)


def _read_signal_codes() -> dict[int, list[str]]:
    """Read the JSON arrays off `calls` before the column is dropped."""
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, signal_codes FROM calls")).fetchall()
    collected: dict[int, list[str]] = {}
    for call_id, raw in rows:
        if not raw:
            continue
        codes = json.loads(raw) if isinstance(raw, str) else raw
        if codes:
            collected[int(call_id)] = [str(code) for code in codes]
    return collected


def _write_signal_rows(grouped: dict[int, list[str]]) -> None:
    bind = op.get_bind()
    for call_id, codes in grouped.items():
        for code in codes:
            bind.execute(
                sa.text("INSERT INTO call_signals (call_id, code) VALUES (:call_id, :code)"),
                {"call_id": call_id, "code": code},
            )


def _read_signal_rows() -> dict[int, list[str]]:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT call_id, code FROM call_signals ORDER BY call_id, code")
    ).fetchall()
    grouped: dict[int, list[str]] = {}
    for call_id, code in rows:
        grouped.setdefault(int(call_id), []).append(str(code))
    return grouped


def _write_signal_codes(grouped: dict[int, list[str]]) -> None:
    """Rebuild the JSON array from the table, so the downgrade is lossless too."""
    bind = op.get_bind()
    for call_id, codes in grouped.items():
        bind.execute(
            sa.text("UPDATE calls SET signal_codes = :codes WHERE id = :call_id"),
            {"codes": json.dumps(codes), "call_id": call_id},
        )
