"""ORM mapping for analysed calls.

Findings are stored as rows, not only inside the layer JSON. The dashboard has to
aggregate across calls — signals by owner, brokers by name, score distributions —
and doing that by unpacking JSON per row would be slow and unqueryable. The
narrative payload is kept alongside as written, because that is what the call
detail page shows.

Every child row cascades from its call: an analysis is one atomic thing, and a
half-deleted one would be worse than either state.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.persistence.models import Base

_REF = 32
_SHORT = 64
_NAME = 128
_LABEL = 256


class CallRow(Base):
    """One analysed call."""

    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(String(_REF), nullable=False)
    title: Mapped[str] = mapped_column(String(_LABEL), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")

    category_code: Mapped[str] = mapped_column(String(_SHORT), nullable=False)
    resolution: Mapped[str] = mapped_column(String(_SHORT), nullable=False)
    sentiment_start: Mapped[str] = mapped_column(String(_SHORT), nullable=False)
    sentiment_end: Mapped[str] = mapped_column(String(_SHORT), nullable=False)

    agent_name: Mapped[str | None] = mapped_column(String(_NAME))
    member_context: Mapped[str | None] = mapped_column(Text)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)

    score: Mapped[int] = mapped_column(Integer, nullable=False)
    score_status: Mapped[str] = mapped_column(String(_SHORT), nullable=False)
    tier: Mapped[str] = mapped_column(String(_SHORT), nullable=False)
    total_positive: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_negative: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    applied_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gate_messages: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    triggered_gate_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    source: Mapped[str] = mapped_column(String(_SHORT), nullable=False)
    rejected_marker_notes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    rejected_attribution_notes: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )

    # Provenance: which model, prompts and rubric produced this (DEC-01).
    provider: Mapped[str] = mapped_column(String(_SHORT), nullable=False)
    model: Mapped[str] = mapped_column(String(_NAME), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(_LABEL), nullable=False)
    rubric_version: Mapped[str] = mapped_column(String(_SHORT), nullable=False)
    analysed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    turns: Mapped[list[TurnRow]] = relationship(
        back_populates="call", cascade="all, delete-orphan", order_by="TurnRow.seq"
    )
    layers: Mapped[list[LayerRow]] = relationship(
        back_populates="call", cascade="all, delete-orphan", order_by="LayerRow.layer"
    )
    markers: Mapped[list[ScoreMarkerRow]] = relationship(
        back_populates="call", cascade="all, delete-orphan"
    )
    l4_signals: Mapped[list[L4SignalRow]] = relationship(
        back_populates="call", cascade="all, delete-orphan"
    )
    broker_signals: Mapped[list[BrokerSignalRow]] = relationship(
        back_populates="call", cascade="all, delete-orphan"
    )
    assist_events: Mapped[list[AssistEventRow]] = relationship(
        back_populates="call", cascade="all, delete-orphan"
    )
    signals: Mapped[list[CallSignalRow]] = relationship(
        back_populates="call", cascade="all, delete-orphan", order_by="CallSignalRow.code"
    )

    __table_args__ = (
        UniqueConstraint("reference", name="uq_calls_reference"),
        Index("ix_calls_category_code", "category_code"),
        Index("ix_calls_agent_name", "agent_name"),
        Index("ix_calls_resolution", "resolution"),
    )


class CallSignalRow(Base):
    """A named condition a call raises, such as ``clinical_risk``.

    A table rather than a JSON column because the dashboard both counts these and
    filters calls by them. Filtering a JSON array would mean either
    dialect-specific SQL or filtering in Python after pagination, which silently
    breaks the result count.
    """

    __tablename__ = "call_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(_SHORT), nullable=False)

    call: Mapped[CallRow] = relationship(back_populates="signals")

    __table_args__ = (
        UniqueConstraint("call_id", "code", name="uq_call_signals_call_id"),
        Index("ix_call_signals_code", "code"),
    )


class TurnRow(Base):
    """One speaker turn. ``seq`` is the anchor every quotation cites."""

    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(_SHORT), nullable=False)
    speaker_name: Mapped[str | None] = mapped_column(String(_NAME))
    text: Mapped[str] = mapped_column(Text, nullable=False)

    call: Mapped[CallRow] = relationship(back_populates="turns")

    __table_args__ = (UniqueConstraint("call_id", "seq", name="uq_turns_call_id"),)


class LayerRow(Base):
    """One layer's narrative payload, exactly as the model wrote it."""

    __tablename__ = "analysis_layers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    layer: Mapped[str] = mapped_column(String(_SHORT), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    unavailable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    call: Mapped[CallRow] = relationship(back_populates="layers")

    __table_args__ = (UniqueConstraint("call_id", "layer", name="uq_analysis_layers_call_id"),)


class ScoreMarkerRow(Base):
    """A scored observation, with the evidence that justified it."""

    __tablename__ = "score_markers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    polarity: Mapped[str] = mapped_column(String(_SHORT), nullable=False)
    dimension: Mapped[str] = mapped_column(String(_SHORT), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_turn_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    call: Mapped[CallRow] = relationship(back_populates="markers")

    __table_args__ = (Index("ix_score_markers_dimension", "dimension"),)


class L4SignalRow(Base):
    """An operational finding with an owning team."""

    __tablename__ = "l4_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    category_code: Mapped[str] = mapped_column(String(_SHORT), nullable=False)
    severity: Mapped[str] = mapped_column(String(_SHORT), nullable=False)
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str | None] = mapped_column(Text)

    call: Mapped[CallRow] = relationship(back_populates="l4_signals")

    __table_args__ = (Index("ix_l4_signals_category_code", "category_code"),)


class BrokerSignalRow(Base):
    """A broker attribution. Never stored without its evidence quote."""

    __tablename__ = "broker_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    broker_name: Mapped[str] = mapped_column(String(_NAME), nullable=False)
    polarity: Mapped[str] = mapped_column(String(_SHORT), nullable=False)
    basis: Mapped[str] = mapped_column(String(_SHORT), nullable=False)
    issue: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_turn_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)

    call: Mapped[CallRow] = relationship(back_populates="broker_signals")

    __table_args__ = (Index("ix_broker_signals_broker_name", "broker_name"),)


class AssistEventRow(Base):
    """A real-time assist observation, including one that should have fired."""

    __tablename__ = "assist_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    outcome: Mapped[str] = mapped_column(String(_SHORT), nullable=False)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(_SHORT), nullable=False)
    at_turn_seq: Mapped[int | None] = mapped_column(Integer)
    timestamp_label: Mapped[str | None] = mapped_column(String(_SHORT))

    call: Mapped[CallRow] = relationship(back_populates="assist_events")

    __table_args__ = (Index("ix_assist_events_outcome", "outcome"),)
