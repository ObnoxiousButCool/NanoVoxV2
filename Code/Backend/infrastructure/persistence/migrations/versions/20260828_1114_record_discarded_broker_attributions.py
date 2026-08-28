"""record discarded broker attributions

Revision ID: d5d2d66f1983
Revises: fc61c8d9ecc6
Created: 2026-08-28 11:14:43.867200+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5d2d66f1983"
down_revision: str | None = "fc61c8d9ecc6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Reviewed: adds the discarded-attribution column. Existing rows get an
    # empty list, which is accurate — none were recorded before this column.
    with op.batch_alter_table("calls", schema=None) as batch_op:
        # server_default is required: the column is NOT NULL and the table
        # already has rows. Autogenerate omitted it, which would fail on upgrade.
        batch_op.add_column(
            sa.Column(
                "rejected_attribution_notes",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            )
        )


def downgrade() -> None:
    # Reviewed: adds the discarded-attribution column. Existing rows get an
    # empty list, which is accurate — none were recorded before this column.
    with op.batch_alter_table("calls", schema=None) as batch_op:
        batch_op.drop_column("rejected_attribution_notes")
