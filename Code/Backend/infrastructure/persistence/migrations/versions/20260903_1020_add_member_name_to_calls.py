"""add member name to calls

Adds the column and fills it in for calls already stored.

The backfill reads ``member_context``, which every analyzed call already holds.
No model is called and nothing is re-analyzed: most of those summaries open with
the member's name, and this recovers it into a column of its own.

Revision ID: b3f4a19c7d02
Revises: 0c89854bcd9d
Created: 2026-09-03 10:20:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from domain.member_name import find_member_name

revision: str = "b3f4a19c7d02"
down_revision: str | None = "0c89854bcd9d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Reviewed: adds a nullable column and fills it from data already stored.
    # Nullable because roughly a third of these summaries describe the caller
    # instead of naming them, and recording the absence is the honest answer.
    with op.batch_alter_table("calls", schema=None) as batch_op:
        batch_op.add_column(sa.Column("member_name", sa.String(length=64), nullable=True))

    _backfill()


def _backfill() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, member_context FROM calls WHERE member_context IS NOT NULL")
    ).fetchall()

    update = sa.text("UPDATE calls SET member_name = :name WHERE id = :call_id")
    for call_id, context in rows:
        name = find_member_name(context)
        if name:
            connection.execute(update, {"name": name, "call_id": call_id})


def downgrade() -> None:
    with op.batch_alter_table("calls", schema=None) as batch_op:
        batch_op.drop_column("member_name")
