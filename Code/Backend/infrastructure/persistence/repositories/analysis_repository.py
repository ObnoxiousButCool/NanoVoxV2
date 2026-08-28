"""SQLAlchemy implementation of the analysis repository.

One analysis is written in one transaction. A call whose turns saved but whose
markers did not would present as a scored call with no evidence behind the score —
worse than no call at all, because it looks complete.

Taxonomy codes are stored, not labels. Reading a call resolves them against the
currently loaded taxonomy, so renaming a category's label updates every stored
call. A code that is no longer in the taxonomy raises rather than rendering as a
mystery string: it means the taxonomy changed without the re-classification run
that ``taxonomy.yaml`` says is required.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from application.ports.analysis_repository import AnalysisRepository
from domain.entities.analysis import (
    AnalysisLayer,
    AnalysisSource,
    CallAnalysis,
    Layer,
    Provenance,
)
from domain.entities.assist_event import AssistEvent, AssistOutcome
from domain.entities.broker_signal import AttributionBasis, BrokerSignal
from domain.entities.l4_signal import L4Signal
from domain.entities.score_marker import ScoreMarker
from domain.entities.transcript import Transcript
from domain.entities.turn import Turn
from domain.scoring.rubric_engine import ScoreResult
from domain.taxonomy import Taxonomy
from domain.value_objects.polarity import Polarity
from domain.value_objects.resolution import Resolution
from domain.value_objects.score import Score, ScoreStatus
from domain.value_objects.sentiment_arc import SentimentArc
from domain.value_objects.severity import Severity
from domain.value_objects.speaker import SpeakerRole
from domain.value_objects.tier import Tier
from infrastructure.persistence.tables import (
    AssistEventRow,
    BrokerSignalRow,
    CallRow,
    L4SignalRow,
    LayerRow,
    ScoreMarkerRow,
    TurnRow,
)

REFERENCE_PREFIX = "C"
_REFERENCE_DIGITS = 4
UNAVAILABLE_KEY = "unavailable"

_LOAD_OPTIONS = (
    selectinload(CallRow.turns),
    selectinload(CallRow.layers),
    selectinload(CallRow.markers),
    selectinload(CallRow.l4_signals),
    selectinload(CallRow.broker_signals),
    selectinload(CallRow.assist_events),
)


class SqlAnalysisRepository(AnalysisRepository):
    """Stores and reconstitutes analyses in SQLite."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], taxonomy: Taxonomy
    ) -> None:
        self._session_factory = session_factory
        self._taxonomy = taxonomy

    async def save(self, analysis: CallAnalysis) -> int:
        async with self._session_factory() as session, session.begin():
            row = _to_row(analysis)
            session.add(row)
            await session.flush()
            return row.id

    async def get(self, call_id: int) -> CallAnalysis | None:
        async with self._session_factory() as session:
            row = await session.get(CallRow, call_id, options=list(_LOAD_OPTIONS))
            return None if row is None else self._to_domain(row)

    async def get_by_reference(self, reference: str) -> CallAnalysis | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(CallRow).where(CallRow.reference == reference).options(*_LOAD_OPTIONS)
            )
            return None if row is None else self._to_domain(row)

    async def next_reference(self) -> str:
        """Allocate a sequential, human-facing reference like ``C0001``."""
        async with self._session_factory() as session:
            count = await session.scalar(select(func.count()).select_from(CallRow))
            return f"{REFERENCE_PREFIX}{(count or 0) + 1:0{_REFERENCE_DIGITS}d}"

    def _to_domain(self, row: CallRow) -> CallAnalysis:
        return CallAnalysis(
            reference=row.reference,
            title=row.title,
            summary=row.summary,
            category=self._taxonomy.category(row.category_code),
            resolution=Resolution(row.resolution),
            sentiment=SentimentArc(start=row.sentiment_start, end=row.sentiment_end),
            transcript=Transcript(
                tuple(
                    Turn(
                        seq=turn.seq,
                        role=SpeakerRole(turn.role),
                        text=turn.text,
                        speaker_name=turn.speaker_name,
                    )
                    for turn in row.turns
                )
            ),
            score=ScoreResult(
                score=Score(row.score),
                status=ScoreStatus(row.score_status),
                tier=Tier(row.tier),
                # The per-marker working is not reconstituted: the markers
                # themselves are stored with the points each contributed, which is
                # what a reviewer needs. Recomputing the arithmetic on read would
                # risk showing a different score than the one that was stored.
                applied=(),
                dimension_totals={},
                total_positive=row.total_positive,
                total_negative=row.total_negative,
                applied_offset=row.applied_offset,
                triggered_gate_ids=tuple(row.triggered_gate_ids),
                messages=tuple(row.gate_messages),
            ),
            source=AnalysisSource(row.source),
            agent_name=row.agent_name,
            member_context=row.member_context,
            duration_minutes=row.duration_minutes,
            signal_codes=tuple(row.signal_codes),
            accepted_markers=tuple(
                ScoreMarker(
                    polarity=Polarity(marker.polarity),
                    dimension=marker.dimension,
                    description=marker.description,
                    evidence_turn_seq=marker.evidence_turn_seq,
                    quote=marker.quote,
                )
                for marker in row.markers
            ),
            rejected_marker_notes=tuple(row.rejected_marker_notes),
            rejected_attribution_notes=tuple(row.rejected_attribution_notes),
            l4_signals=tuple(
                L4Signal(
                    category=self._taxonomy.l4_category(signal.category_code),
                    severity=Severity(signal.severity),
                    narrative=signal.narrative,
                    recommended_action=signal.recommended_action,
                )
                for signal in row.l4_signals
            ),
            broker_signals=tuple(
                BrokerSignal(
                    broker_name=signal.broker_name,
                    polarity=Polarity(signal.polarity),
                    basis=AttributionBasis(signal.basis),
                    issue=signal.issue,
                    evidence_turn_seq=signal.evidence_turn_seq,
                    quote=signal.quote,
                )
                for signal in row.broker_signals
            ),
            assist_events=tuple(
                AssistEvent(
                    outcome=AssistOutcome(event.outcome),
                    trigger=event.trigger,
                    recommendation=event.recommendation,
                    severity=Severity(event.severity),
                    at_turn_seq=event.at_turn_seq,
                    timestamp_label=event.timestamp_label,
                )
                for event in row.assist_events
            ),
            layers=tuple(
                AnalysisLayer(layer=Layer(layer.layer), payload=dict(layer.payload))
                for layer in row.layers
            ),
            provenance=Provenance(
                provider=row.provider,
                model=row.model,
                prompt_version=row.prompt_version,
                rubric_version=row.rubric_version,
                analysed_at=row.analysed_at,
                total_input_tokens=row.input_tokens,
                total_output_tokens=row.output_tokens,
                duration_ms=row.duration_ms,
            ),
        )


def _to_row(analysis: CallAnalysis) -> CallRow:
    score = analysis.score
    points_by_marker = {id(applied.marker): applied.points for applied in score.applied}

    return CallRow(
        reference=analysis.reference,
        title=analysis.title,
        summary=analysis.summary,
        category_code=analysis.category.code,
        resolution=analysis.resolution.value,
        sentiment_start=analysis.sentiment.start,
        sentiment_end=analysis.sentiment.end,
        agent_name=analysis.agent_name,
        member_context=analysis.member_context,
        duration_minutes=analysis.duration_minutes,
        score=score.score.value,
        score_status=score.status.value,
        tier=score.tier.value,
        total_positive=score.total_positive,
        total_negative=score.total_negative,
        applied_offset=score.applied_offset,
        gate_messages=list(score.messages),
        triggered_gate_ids=list(score.triggered_gate_ids),
        source=analysis.source.value,
        signal_codes=list(analysis.signal_codes),
        rejected_marker_notes=list(analysis.rejected_marker_notes),
        rejected_attribution_notes=list(analysis.rejected_attribution_notes),
        provider=analysis.provenance.provider,
        model=analysis.provenance.model,
        prompt_version=analysis.provenance.prompt_version,
        rubric_version=analysis.provenance.rubric_version,
        analysed_at=analysis.provenance.analysed_at,
        input_tokens=analysis.provenance.total_input_tokens,
        output_tokens=analysis.provenance.total_output_tokens,
        duration_ms=analysis.provenance.duration_ms,
        turns=[
            TurnRow(
                seq=turn.seq,
                role=turn.role.value,
                speaker_name=turn.speaker_name,
                text=turn.text,
            )
            for turn in analysis.transcript.turns
        ],
        layers=[
            LayerRow(
                layer=layer.layer.value,
                payload=dict(layer.payload),
                unavailable=bool(layer.payload.get(UNAVAILABLE_KEY, False)),
            )
            for layer in analysis.layers
        ],
        markers=[
            ScoreMarkerRow(
                polarity=marker.polarity.value,
                dimension=marker.dimension,
                description=marker.description,
                evidence_turn_seq=marker.evidence_turn_seq,
                quote=marker.quote,
                points=points_by_marker.get(id(marker), 0),
            )
            for marker in analysis.accepted_markers
        ],
        l4_signals=[
            L4SignalRow(
                category_code=signal.category.code,
                severity=signal.severity.value,
                narrative=signal.narrative,
                recommended_action=signal.recommended_action,
            )
            for signal in analysis.l4_signals
        ],
        broker_signals=[
            BrokerSignalRow(
                broker_name=signal.broker_name,
                polarity=signal.polarity.value,
                basis=signal.basis.value,
                issue=signal.issue,
                evidence_turn_seq=signal.evidence_turn_seq,
                quote=signal.quote,
            )
            for signal in analysis.broker_signals
        ],
        assist_events=[
            AssistEventRow(
                outcome=event.outcome.value,
                trigger=event.trigger,
                recommendation=event.recommendation,
                severity=event.severity.value,
                at_turn_seq=event.at_turn_seq,
                timestamp_label=event.timestamp_label,
            )
            for event in analysis.assist_events
        ],
    )
