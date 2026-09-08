"""add call time and caller type to calls

The timestamped corpus states four things the schema had nowhere to put: handle
time to the second, when the call started and ended, and which kind of caller it
was — MEMBER, EMPLOYER or BROKER.

All nullable. The previous corpus states none of them, so a call analyzed before
this carries nulls rather than a fabricated midnight or a caller type guessed
from the transcript.

Revision ID: d5a83c1f9e64
Revises: c7d1e0b48f35
Created: 2026-09-03 15:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5a83c1f9e64"
down_revision: str | None = "c7d1e0b48f35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Reviewed: four nullable columns and one index. No data is rewritten, so
    # existing rows are untouched and the migration is safe to run on a
    # populated database.
    with op.batch_alter_table("calls", schema=None) as batch_op:
        batch_op.add_column(sa.Column("duration_seconds", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("started_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("ended_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("caller_type", sa.String(length=64), nullable=True))
        # Every time-of-day and trend query orders or filters on the start time.
        batch_op.create_index("ix_calls_started_at", ["started_at"])
        batch_op.create_index("ix_calls_caller_type", ["caller_type"])


def downgrade() -> None:
    with op.batch_alter_table("calls", schema=None) as batch_op:
        batch_op.drop_index("ix_calls_caller_type")
        batch_op.drop_index("ix_calls_started_at")
        batch_op.drop_column("caller_type")
        batch_op.drop_column("ended_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("duration_seconds")
