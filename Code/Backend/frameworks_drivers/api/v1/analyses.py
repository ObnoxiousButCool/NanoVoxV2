"""Analysis endpoint.

Runs the five-layer pipeline against a pasted transcript and returns the complete
result. The response is the contract the Analyze and Call detail screens are built
against, so it carries the evidence — turn indices and quotes — rather than only
the conclusions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from application.use_cases.analyze_transcript import AnalyzeTranscriptCommand
from domain.entities.analysis import CallAnalysis
from frameworks_drivers.api.dependencies import AnalyzeTranscriptDep, ContainerDep

router = APIRouter(tags=["analyses"])

MAX_TRANSCRIPT_CHARS = 200_000


class AnalyzeRequest(BaseModel):
    transcript: str = Field(
        min_length=1,
        max_length=MAX_TRANSCRIPT_CHARS,
        description="Pasted transcript, one speaker turn per line as 'Speaker: text'.",
    )
    provider: str | None = Field(
        default=None, description="Provider name. Defaults to the configured provider."
    )
    model: str | None = Field(default=None, description="Model override for this analysis.")


class TurnResponse(BaseModel):
    seq: int
    role: str
    speaker_name: str | None
    text: str


class MarkerResponse(BaseModel):
    polarity: str
    dimension: str
    description: str
    evidence_turn_seq: int
    quote: str


class ScoreResponse(BaseModel):
    value: int
    status: str
    tier: str
    total_positive: int
    total_negative: int
    applied_offset: int
    gate_messages: list[str]


class L4SignalResponse(BaseModel):
    category: str
    owner: str
    severity: str
    narrative: str
    recommended_action: str | None


class BrokerSignalResponse(BaseModel):
    broker_name: str
    polarity: str
    basis: str
    issue: str
    evidence_turn_seq: int
    quote: str


class AssistEventResponse(BaseModel):
    outcome: str
    trigger: str
    recommendation: str
    severity: str
    at_turn_seq: int | None
    timestamp_label: str | None
    is_gap: bool


class LayerResponse(BaseModel):
    layer: str
    payload: dict[str, Any]


class ProvenanceResponse(BaseModel):
    provider: str
    model: str
    prompt_version: str
    rubric_version: str
    analysed_at: datetime
    input_tokens: int
    output_tokens: int
    duration_ms: float


class AnalysisResponse(BaseModel):
    reference: str
    title: str
    summary: str
    category: str
    category_label: str
    resolution: str
    sentiment_start: str
    sentiment_end: str
    agent_name: str | None
    member_context: str | None
    duration_minutes: int | None
    source: str
    signal_codes: list[str]
    score: ScoreResponse
    markers: list[MarkerResponse]
    rejected_marker_notes: list[str] = Field(
        description="Observations discarded because their evidence did not check out."
    )
    rejected_attribution_notes: list[str] = Field(
        description="Broker attributions discarded because their evidence did not check out."
    )
    l4_signals: list[L4SignalResponse]
    broker_signals: list[BrokerSignalResponse]
    assist_events: list[AssistEventResponse]
    layers: list[LayerResponse]
    transcript: list[TurnResponse]
    provenance: ProvenanceResponse


def to_response(analysis: CallAnalysis) -> AnalysisResponse:
    return AnalysisResponse(
        reference=analysis.reference,
        title=analysis.title,
        summary=analysis.summary,
        category=analysis.category.code,
        category_label=analysis.category.label,
        resolution=analysis.resolution.value,
        sentiment_start=analysis.sentiment.start,
        sentiment_end=analysis.sentiment.end,
        agent_name=analysis.agent_name,
        member_context=analysis.member_context,
        duration_minutes=analysis.duration_minutes,
        source=analysis.source.value,
        signal_codes=list(analysis.signal_codes),
        score=ScoreResponse(
            value=analysis.score.score.value,
            status=analysis.score.status.value,
            tier=analysis.score.tier.value,
            total_positive=analysis.score.total_positive,
            total_negative=analysis.score.total_negative,
            applied_offset=analysis.score.applied_offset,
            gate_messages=list(analysis.score.messages),
        ),
        markers=[
            MarkerResponse(
                polarity=marker.polarity.value,
                dimension=marker.dimension,
                description=marker.description,
                evidence_turn_seq=marker.evidence_turn_seq,
                quote=marker.quote,
            )
            for marker in analysis.accepted_markers
        ],
        rejected_marker_notes=list(analysis.rejected_marker_notes),
        rejected_attribution_notes=list(analysis.rejected_attribution_notes),
        l4_signals=[
            L4SignalResponse(
                category=signal.category.code,
                owner=signal.owner_name,
                severity=signal.severity.value,
                narrative=signal.narrative,
                recommended_action=signal.recommended_action,
            )
            for signal in analysis.l4_signals
        ],
        broker_signals=[
            BrokerSignalResponse(
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
            AssistEventResponse(
                outcome=event.outcome.value,
                trigger=event.trigger,
                recommendation=event.recommendation,
                severity=event.severity.value,
                at_turn_seq=event.at_turn_seq,
                timestamp_label=event.timestamp_label,
                is_gap=event.is_gap,
            )
            for event in analysis.assist_events
        ],
        layers=[
            LayerResponse(layer=layer.layer.value, payload=dict(layer.payload))
            for layer in analysis.layers
        ],
        transcript=[
            TurnResponse(
                seq=turn.seq,
                role=turn.role.value,
                speaker_name=turn.speaker_name,
                text=turn.text,
            )
            for turn in analysis.transcript.turns
        ],
        provenance=ProvenanceResponse(
            provider=analysis.provenance.provider,
            model=analysis.provenance.model,
            prompt_version=analysis.provenance.prompt_version,
            rubric_version=analysis.provenance.rubric_version,
            analysed_at=analysis.provenance.analysed_at,
            input_tokens=analysis.provenance.total_input_tokens,
            output_tokens=analysis.provenance.total_output_tokens,
            duration_ms=analysis.provenance.duration_ms,
        ),
    )


@router.post(
    "/analyses",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Analyse a pasted transcript",
)
async def analyse(
    request: AnalyzeRequest,
    use_case: AnalyzeTranscriptDep,
    container: ContainerDep,
) -> AnalysisResponse:
    provider = container.create_provider(request.provider, request.model)
    try:
        analysis = await use_case.execute(
            AnalyzeTranscriptCommand(transcript=request.transcript), provider
        )
    finally:
        await provider.aclose()
    return to_response(analysis)
