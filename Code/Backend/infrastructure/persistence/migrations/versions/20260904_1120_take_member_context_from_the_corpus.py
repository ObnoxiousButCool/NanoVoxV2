"""take member context from the corpus header, and recover the names

The earlier backfill read ``calls.member_context`` and found no names in it.
That was not a fault in the reader: the column holds the model's own account of
the caller — *"The member is at the dentist's office and is confused about their
coverage"* — while the name is only ever in the file header, in the form the
reader expects: *"Priya Raman, 36 · ChoiceBuilder dental · ..."*.

The header is not recoverable from the words. Across the shipped corpus 28 of
50 files name the member and only **3** of those names are ever spoken in the
call, so no amount of prompting would have retrieved them. The header line was
being parsed all along and stored on ``ground_truth``, which the analysis never
read.

This copies it across for calls already stored, so the fix shows without a
corpus re-run costing fifty model calls. Matched on ``reference``, which both
tables carry. Every call analysed after this takes the same value through
``AnalyzeTranscriptCommand``.

Revision ID: e2b7f45a91c8
Revises: d5a83c1f9e64
Created: 2026-09-04 11:20:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from domain.member_name import find_member_name

revision: str = "e2b7f45a91c8"
down_revision: str | None = "d5a83c1f9e64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Reviewed: no schema change. Copies an authored field onto rows that were
    # storing a derived one, and re-reads the name from it.
    connection = op.get_bind()

    rows = connection.execute(
        sa.text(
            "SELECT c.id, g.member_context "
            "FROM calls AS c "
            "JOIN ground_truth AS g ON g.reference = c.reference "
            "WHERE g.member_context IS NOT NULL AND g.member_context <> ''"
        )
    ).fetchall()

    update = sa.text(
        "UPDATE calls SET member_context = :context, member_name = :name WHERE id = :call_id"
    )
    for call_id, context in rows:
        # The name may still be absent — an employer call's header names a
        # company and a job title, not a member — and absent is a real answer.
        connection.execute(
            update,
            {"context": context, "name": find_member_name(context), "call_id": call_id},
        )


def downgrade() -> None:
    # The model's own wording is not kept anywhere, so it cannot be restored.
    # Clearing the name is the honest reversal: it is derived from the context
    # this migration wrote, and leaving it would outlive its source.
    op.get_bind().execute(sa.text("UPDATE calls SET member_name = NULL"))
