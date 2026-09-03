"""correct call durations from the corpus files

Durations were being taken from L2 — a model layer — while every corpus file
states the real figure in its header (``- **Duration:** ~11 min``). The parser
ignored it, so 86 of the 100 stored calls carried an estimate rather than the
stated duration, and the dashboard's minute figures were built on it.

This corrects the stored values by re-reading the corpus. No model is called and
nothing is re-analysed: the number was in the source all along.

Only calls created by a corpus run are touched. A pasted transcript carries no
header, so its estimate is the best figure available and must not be cleared.

Revision ID: c7d1e0b48f35
Revises: b3f4a19c7d02
Created: 2026-09-03 13:30:00.000000+00:00
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from infrastructure.config.settings import get_settings
from infrastructure.corpus.markdown_corpus import parse_corpus_file

_log = logging.getLogger("alembic.runtime.migration")

revision: str = "c7d1e0b48f35"
down_revision: str | None = "b3f4a19c7d02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CORPUS_SOURCE = "CORPUS_RUN"


def upgrade() -> None:
    # Reviewed: updates one nullable column on corpus-sourced rows only. No
    # schema change, so it is safe to re-run and safe to skip.
    settings = get_settings()
    directory = settings.corpus_path
    if not directory.is_dir():
        # Migrations must run on a machine without the corpus checked out — a
        # deployment that mounts only the database, for instance. The stored
        # estimates stay as they are rather than the upgrade failing.
        return

    connection = op.get_bind()
    update = sa.text(
        "UPDATE calls SET duration_minutes = :minutes "
        "WHERE reference = :reference AND source = :source"
    )

    for path in sorted(directory.glob(settings.corpus_glob)):
        try:
            call = parse_corpus_file(path.read_text(encoding="utf-8"), path.stem)
        except Exception:
            # One malformed file must not stop the upgrade. Its call keeps the
            # estimate it already had, which is the pre-migration behaviour --
            # logged rather than swallowed, so a corpus defect is visible in the
            # migration output instead of showing up as a stale figure later.
            _log.warning("Skipped %s: it could not be parsed.", path.name, exc_info=True)
            continue
        if call.duration_minutes is None:
            continue
        connection.execute(
            update,
            {
                "minutes": call.duration_minutes,
                "reference": call.reference,
                "source": _CORPUS_SOURCE,
            },
        )


def downgrade() -> None:
    # Not reversible: the estimates this replaces were never stored anywhere
    # else, and re-deriving them would mean running the model again. The column
    # itself is untouched, so there is nothing structural to undo.
    pass
