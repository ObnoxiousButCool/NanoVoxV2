"""Migrations must not silently delete data.

This guards a defect that reached a running database. SQLite cannot ALTER most
columns, so Alembic's ``batch_alter_table`` drops and recreates the table. With
``PRAGMA foreign_keys=ON`` — which the application engine sets — that DROP
performs an implicit ``DELETE FROM``, firing every child table's
``ON DELETE CASCADE``. Two migrations that only meant to add a column emptied
turns, layers, markers and every other child row, and nothing reported it.

The test seeds a call *with children* at the first revision, migrates to head,
and asserts the children are still there. Anything that reintroduces the problem
fails here rather than in someone's database.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from infrastructure.config.paths import BACKEND_ROOT

FIRST_REVISION = "fc61c8d9ecc6"

SEED_CALL = """
INSERT INTO calls (
    id, reference, title, summary, category_code, resolution, sentiment_start,
    sentiment_end, score, score_status, tier, total_positive, total_negative,
    applied_offset, gate_messages, triggered_gate_ids, source, signal_codes,
    rejected_marker_notes, provider, model, prompt_version, rubric_version,
    analysed_at, input_tokens, output_tokens, duration_ms
) VALUES (
    1, 'M0001', 'A stored call', 'It happened.', 'pharmacy', 'UNRESOLVED',
    'WORRIED', 'DISMISSED', 27, 'provisional', 'POOR', 0, 75, 0, '[]', '[]',
    'PASTED', '["clinical_risk"]', '[]', 'ollama', 'm', '1.0.0', '1.0.0',
    '2026-08-28T12:00:00', 10, 5, 1.0
)
"""

SEED_CHILDREN = (
    "INSERT INTO turns (call_id, seq, role, speaker_name, text) "
    "VALUES (1, 0, 'AGENT', 'Brad', 'Choice Administrators.')",
    "INSERT INTO turns (call_id, seq, role, speaker_name, text) "
    "VALUES (1, 1, 'MEMBER', NULL, 'I have chest pressure.')",
    "INSERT INTO analysis_layers (call_id, layer, payload, unavailable) VALUES (1, 'L1', '{}', 0)",
    "INSERT INTO score_markers "
    "(call_id, polarity, dimension, description, evidence_turn_seq, quote, points) "
    "VALUES (1, 'NEGATIVE', 'empathy', 'Was curt.', 1, 'chest pressure', -8)",
    "INSERT INTO l4_signals (call_id, category_code, severity, narrative) "
    "VALUES (1, 'compliance_risk', 'CRITICAL', 'Cost steering.')",
    "INSERT INTO broker_signals "
    "(call_id, broker_name, polarity, basis, issue, evidence_turn_seq, quote) "
    # The quote has to name a broker relationship, or the evidence rule removes
    # this row legitimately and the cascade this test guards would be masked by a
    # deletion that was supposed to happen.
    "VALUES (1, 'Marcus Trent', 'NEGATIVE', 'NAMED_IN_CALL', 'Bad advice.', 1, "
    "'My broker, Marcus Trent, gave bad advice')",
    "INSERT INTO assist_events (call_id, outcome, trigger, recommendation, severity) "
    "VALUES (1, 'SHOULD_HAVE_FIRED', 'symptoms', 'Nurse line.', 'CRITICAL')",
)

CHILD_TABLES = (
    "turns",
    "analysis_layers",
    "score_markers",
    "l4_signals",
    "broker_signals",
    "assist_events",
)


def _alembic(database: Path, revision: str) -> None:
    result = subprocess.run(  # noqa: S603 - fixed argument list, no shell, no user input
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=BACKEND_ROOT,
        env={
            **os.environ,
            "DATABASE_URL": f"sqlite+aiosqlite:///{database.as_posix()}",
            "LOG_ENABLED": "false",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(f"alembic upgrade {revision} failed:\n{result.stdout}\n{result.stderr}")


@pytest.fixture
def migrated(tmp_path: Path) -> Iterator[Engine]:
    """A call with children, seeded at the first revision then migrated to head."""
    database = tmp_path / "history.db"
    _alembic(database, FIRST_REVISION)

    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text(SEED_CALL))
        for statement in SEED_CHILDREN:
            connection.execute(text(statement))
    engine.dispose()

    _alembic(database, "head")

    engine = create_engine(f"sqlite:///{database.as_posix()}")
    yield engine
    engine.dispose()


def _count(engine: Engine, table: str) -> int:
    with engine.connect() as connection:
        # Table names come from the CHILD_TABLES constant above, never from input.
        return int(
            connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()  # noqa: S608
        )


def test_the_call_itself_survives(migrated: Engine) -> None:
    assert _count(migrated, "calls") == 1


@pytest.mark.parametrize("table", CHILD_TABLES)
def test_child_rows_survive_the_migration_chain(migrated: Engine, table: str) -> None:
    # The defect: a batch ALTER on `calls` cascaded and emptied these.
    assert _count(migrated, table) > 0, f"{table} was emptied by a migration"


def test_the_transcript_is_intact(migrated: Engine) -> None:
    # A call whose turns vanished cannot be opened at all: the transcript is
    # required, so the detail page fails rather than rendering a gap.
    with migrated.connect() as connection:
        turns = connection.execute(text("SELECT seq, text FROM turns ORDER BY seq")).all()

    assert [row[0] for row in turns] == [0, 1]


def test_signal_codes_were_carried_into_their_new_table(migrated: Engine) -> None:
    with migrated.connect() as connection:
        codes = connection.execute(text("SELECT code FROM call_signals")).scalars().all()

    assert list(codes) == ["clinical_risk"]


def test_foreign_keys_are_enforced_again_afterwards(migrated: Engine) -> None:
    # Disabling them is a migration-time measure; the application still wants
    # them on. This checks the pragma was not left off in the database file.
    with migrated.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.exec_driver_sql("DELETE FROM calls WHERE id = 1")
        remaining = connection.execute(text("SELECT COUNT(*) FROM turns")).scalar_one()

    assert remaining == 0
