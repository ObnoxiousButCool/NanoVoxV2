"""drop broker attributions with no broker evidence

Removes attributions already stored that the evidence rule now refuses: the
named party is the agent who answered the call, or the quote says nothing about
a broker relationship at all. Surgeons, pharmacies, provider groups, the plan
itself and three of the agents had reached a screen that names people for
Compliance review.

Applied as a data fix rather than by re-analysing the corpus. The rule is
deterministic and every input it needs — the quote, the broker name, the agent —
is already stored, so re-running a hundred calls through a model would spend
money to reach the same answer, and would change unrelated scores on the way.

Nothing is silently deleted. Each removed row leaves the same note on its call
that the pipeline would have written, so the count on the Brokers screen still
says what it is not showing.

Revision ID: 0c89854bcd9d
Revises: 1d657a252921
Created: 2026-08-31 09:45:00.000000+00:00
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from domain.attribution_notes import is_the_agent_note, not_a_broker_note
from domain.broker_evidence import compile_broker_terms, is_the_agent, quote_names_a_broker
from infrastructure.config.settings import get_settings

revision: str = "0c89854bcd9d"
down_revision: str | None = "1d657a252921"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STORED = sa.text(
    """
    SELECT b.id, b.call_id, b.broker_name, b.quote, c.agent_name,
           c.rejected_attribution_notes
    FROM broker_signals b
    JOIN calls c ON c.id = b.call_id
    """
)


def upgrade() -> None:
    # Reviewed: deletes rows from broker_signals only, and appends a note to the
    # calls they belonged to. No table is recreated, so the cascade hazard that
    # batch_alter_table carries on SQLite does not apply here.
    terms = compile_broker_terms(get_settings().broker_evidence_terms)
    connection = op.get_bind()

    doomed: list[int] = []
    notes: dict[int, list[str]] = {}

    for row_id, call_id, broker_name, quote, agent_name, existing in connection.execute(_STORED):
        if is_the_agent(broker_name, agent_name):
            note = is_the_agent_note(broker_name)
        elif not quote_names_a_broker(quote or "", terms):
            note = not_a_broker_note(broker_name, quote or "")
        else:
            continue

        doomed.append(row_id)
        if call_id not in notes:
            notes[call_id] = list(_existing_notes(existing))
        notes[call_id].append(note)

    for call_id, call_notes in notes.items():
        connection.execute(
            sa.text("UPDATE calls SET rejected_attribution_notes = :notes WHERE id = :id"),
            {"notes": json.dumps(call_notes), "id": call_id},
        )

    for row_id in doomed:
        connection.execute(sa.text("DELETE FROM broker_signals WHERE id = :id"), {"id": row_id})


def _existing_notes(stored: object) -> list[str]:
    """The notes already on a call, tolerating either JSON text or a list."""
    if isinstance(stored, list):
        return [str(item) for item in stored]
    if isinstance(stored, str) and stored.strip():
        try:
            parsed = json.loads(stored)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return []


def downgrade() -> None:
    # Reviewed: not reversible. The removed rows were attributions against people
    # who were never the member's broker, and recreating them would put those
    # names back on a Compliance screen. Re-analysing the corpus is the way back
    # to any attribution this removed in error.
    pass
