"""The complete analysis of one call.

The aggregate the rest of the system stores, serves and aggregates over. It holds
domain objects rather than model output: by the time a ``CallAnalysis`` exists,
every marker has been validated against the transcript and the score has been
computed by the rubric, so nothing downstream has to wonder whether it can trust
what it is reading.

Layer narratives are kept as plain mappings. They are prose written by the model
for a human to read, and the domain has no rules about their internals — but the
*structured* findings inside each layer are extracted into the typed collections
above them, which is what the dashboard aggregates.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from domain.entities.assist_event import AssistEvent
from domain.entities.broker_signal import BrokerSignal
from domain.entities.l4_signal import L4Signal
from domain.entities.score_marker import ScoreMarker
from domain.entities.transcript import Transcript
from domain.errors import ValidationError
from domain.scoring.rubric_engine import ScoreResult
from domain.value_objects.category import Category
from domain.value_objects.resolution import Resolution
from domain.value_objects.sentiment_arc import SentimentArc


class Layer(str, Enum):
    """The five layers of the NanoVox architecture."""

    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    L5 = "L5"


class AnalysisSource(str, Enum):
    """How a call entered the system.

    Distinguishing them matters for honesty on the dashboard: a corpus figure
    should never be presented as though a user submitted it.
    """

    PASTED = "PASTED"
    CORPUS_RUN = "CORPUS_RUN"


@dataclass(frozen=True)
class AnalysisLayer:
    """One layer's narrative payload, as written by the model."""

    layer: Layer
    payload: Mapping[str, object]


@dataclass(frozen=True)
class Provenance:
    """Which model, prompts and rubric produced this analysis.

    Recorded on every call because DEC-01 makes every dashboard figure
    model-derived: without this, "why did the numbers change?" is unanswerable.
    """

    provider: str
    model: str
    prompt_version: str
    rubric_version: str
    analysed_at: datetime
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    duration_ms: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens


@dataclass(frozen=True)
class CallAnalysis:
    """Everything known about one analysed call."""

    reference: str
    title: str
    summary: str
    category: Category
    resolution: Resolution
    sentiment: SentimentArc
    transcript: Transcript
    score: ScoreResult
    provenance: Provenance
    source: AnalysisSource = AnalysisSource.PASTED
    agent_name: str | None = None
    # Read from the transcript, not written by a model. Absent when the call
    # never states one, which is a fact about the call rather than a failure.
    member_id: str | None = None
    member_context: str | None = None
    # Read out of ``member_context`` when it opens with one. Only the leading
    # form is trusted: a name is the one thing on this dashboard a reader
    # recognises personally, and the wrong one is worse than none.
    member_name: str | None = None
    duration_minutes: int | None = None
    # Handle time to the second, where the source states it that precisely.
    # Whole minutes lose 30 seconds on a five-minute call, which is 10% of it.
    duration_seconds: int | None = None
    # When the call actually happened, not when it was analysed. Two fields
    # because "how long did it run" and "when in the day was it" are different
    # questions, and end - start is not always the handle time.
    started_at: datetime | None = None
    ended_at: datetime | None = None
    # MEMBER, EMPLOYER or BROKER. Not every caller is a member: an employer's HR
    # director and a broker both reach the same queue, and counting them as
    # members would inflate every per-member figure on the dashboard.
    caller_type: str | None = None
    signal_codes: tuple[str, ...] = ()
    accepted_markers: tuple[ScoreMarker, ...] = ()
    rejected_marker_notes: tuple[str, ...] = ()
    rejected_attribution_notes: tuple[str, ...] = ()
    l4_signals: tuple[L4Signal, ...] = ()
    broker_signals: tuple[BrokerSignal, ...] = ()
    assist_events: tuple[AssistEvent, ...] = ()
    layers: tuple[AnalysisLayer, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise ValidationError("A call analysis must have a reference.")
        if not self.title.strip():
            raise ValidationError(f"Call {self.reference} must have a title.")

        seen: set[Layer] = set()
        for layer in self.layers:
            if layer.layer in seen:
                raise ValidationError(
                    f"Call {self.reference} has two payloads for layer {layer.layer.value}."
                )
            seen.add(layer.layer)

    def layer(self, layer: Layer) -> AnalysisLayer | None:
        for candidate in self.layers:
            if candidate.layer is layer:
                return candidate
        return None

    @property
    def has_broker_attribution(self) -> bool:
        return bool(self.broker_signals)

    @property
    def assist_gaps(self) -> tuple[AssistEvent, ...]:
        """Rules that should have fired and did not — the L5 finding."""
        return tuple(event for event in self.assist_events if event.is_gap)
