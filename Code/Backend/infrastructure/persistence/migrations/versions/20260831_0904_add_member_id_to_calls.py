"""add member id to calls

Adds the column and fills it in for calls already stored.

The backfill reads the transcripts already in ``turns``. No model is called and
nothing is re-analysed: a member identifier is a fixed pattern in words the call
already contains, so recovering it is a read of data that was parsed and stored
months ago but never kept in a column of its own.

Revision ID: 1d657a252921
Revises: 849036540d29
Created: 2026-08-31 09:04:59.890950+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from domain.member_id import compile_member_id_pattern
from infrastructure.config.settings import get_settings

revision: str = "1d657a252921"
down_revision: str | None = "849036540d29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The member's own turns are searched first: an agent reads identifiers back and
# handles many members, so a number in an agent's turn is the weaker evidence.
_MEMBER_FIRST = sa.text(
    """
    SELECT call_id, role, text
    FROM turns
    ORDER BY call_id, CASE role WHEN 'MEMBER' THEN 0 ELSE 1 END, seq
    """
)


def upgrade() -> None:
    # Reviewed: adds a nullable column and its index, then fills it from data
    # already stored. Nullable because one call in the shipped corpus never
    # states an identifier, and inventing one would be worse than recording its
    # absence.
    with op.batch_alter_table("calls", schema=None) as batch_op:
        batch_op.add_column(sa.Column("member_id", sa.String(length=64), nullable=True))
        batch_op.create_index("ix_calls_member_id", ["member_id"])

    _backfill()


def _backfill() -> None:
    """Recover identifiers from transcripts already stored."""
    configured = get_settings().member_id_pattern.strip()
    if not configured:
        return

    pattern = compile_member_id_pattern(configured)
    connection = op.get_bind()

    found: dict[int, str] = {}
    for call_id, _role, text in connection.execute(_MEMBER_FIRST):
        if call_id in found:
            # The ordering puts the member's turns first, so the first match for
            # a call is already the best one available.
            continue
        match = pattern.search(text or "")
        if match is not None:
            captured = match.group(1) if match.re.groups else match.group(0)
            found[call_id] = "".join(ch for ch in captured if ch.isalnum()).upper()

    for call_id, member_id in found.items():
        connection.execute(
            sa.text("UPDATE calls SET member_id = :member_id WHERE id = :id"),
            {"member_id": member_id, "id": call_id},
        )


def downgrade() -> None:
    # Reviewed: drops the index and column. The identifiers are recoverable from
    # the transcripts, so nothing is permanently lost by going back.
    with op.batch_alter_table("calls", schema=None) as batch_op:
        batch_op.drop_index("ix_calls_member_id")
        batch_op.drop_column("member_id")
