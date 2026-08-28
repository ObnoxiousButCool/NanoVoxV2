"""add corpus run and ground truth tables

Revision ID: 849036540d29
Revises: 067891d530f7
Created: 2026-08-28 16:01:02.399161+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "849036540d29"
down_revision: str | None = "067891d530f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Three new tables and no change to `calls`, which is what makes this
    # migration safe on SQLite: nothing here triggers a batch table rebuild of a
    # parent, so no child's ON DELETE CASCADE fires. See the call_signals
    # migration for what happens when one does.
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("force", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_runs")),
    )
    with op.batch_alter_table("analysis_runs", schema=None) as batch_op:
        batch_op.create_index("ix_analysis_runs_status", ["status"], unique=False)

    op.create_table(
        "ground_truth",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("agent_name", sa.String(length=128), nullable=True),
        sa.Column("tier", sa.String(length=64), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("resolution", sa.String(length=64), nullable=True),
        sa.Column("sentiment_start", sa.String(length=64), nullable=True),
        sa.Column("sentiment_end", sa.String(length=64), nullable=True),
        sa.Column("topics", sa.JSON(), nullable=False),
        sa.Column("broker_names", sa.JSON(), nullable=False),
        sa.Column("member_context", sa.Text(), nullable=True),
        sa.Column("panel_text", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ground_truth")),
        sa.UniqueConstraint("reference", name="uq_ground_truth_reference"),
    )
    op.create_table(
        "analysis_run_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("reference", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("call_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["call_id"],
            ["calls.id"],
            name=op.f("fk_analysis_run_items_call_id_calls"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_analysis_run_items_run_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_run_items")),
        sa.UniqueConstraint("run_id", "source_id", name="uq_run_items_run_source"),
    )
    with op.batch_alter_table("analysis_run_items", schema=None) as batch_op:
        batch_op.create_index("ix_analysis_run_items_status", ["status"], unique=False)


def downgrade() -> None:

    with op.batch_alter_table("analysis_run_items", schema=None) as batch_op:
        batch_op.drop_index("ix_analysis_run_items_status")

    op.drop_table("analysis_run_items")
    op.drop_table("ground_truth")
    with op.batch_alter_table("analysis_runs", schema=None) as batch_op:
        batch_op.drop_index("ix_analysis_runs_status")

    op.drop_table("analysis_runs")
