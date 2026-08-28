"""Turn a pasted transcript into a complete, evidence-anchored analysis.

The pipeline (plan §7.2)::

    parse -> redact -> L1 -> L2 -> L3 markers -> validate -> rubric -> gates
          -> L4 -> L5 -> persist

**Why five calls instead of one.** A small local model reliably fills a focused
schema and routinely fails a large one. Splitting also means each layer is
retryable on its own, and a failure in one is visible as a failure in *that* layer.

**Which failures are fatal.** L1, L2 and L3 produce the call's classification and
its score, so losing one means there is no analysis — the request fails and
nothing is stored. L4 and L5 are additive findings: if one fails, the call is
still scored and classified, and that layer is recorded as *unavailable with a
reason*. An unavailable layer must never be presented as an empty one, for the
same reason the L5 panel shows a missing trigger as a finding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application.dto.analysis_schemas import NO_TURN, AnalysisSchemas
from application.ports.analysis_repository import AnalysisRepository
from application.ports.clock import Clock
from application.ports.llm_provider import LLMProvider, LlmRequest, StructuredResult, TokenUsage
from application.ports.prompts import PromptSource
from application.ports.redaction import RedactionPort
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
from domain.errors import NanoVoxError, ValidationError
from domain.parsing import parse_transcript
from domain.scoring.marker_validation import MarkerValidator
from domain.scoring.rubric import Rubric
from domain.scoring.rubric_engine import RubricEngine
from domain.taxonomy import Taxonomy
from domain.value_objects.polarity import Polarity
from domain.value_objects.resolution import Resolution
from domain.value_objects.severity import Severity

L1_PROMPT = "l1_understanding"
L2_PROMPT = "l2_insights"
L3_PROMPT = "l3_quality"
L4_PROMPT = "l4_operational_bi"
L5_PROMPT = "l5_assist"

UNAVAILABLE_KEY = "unavailable"
REASON_KEY = "reason"

_MAX_TRANSCRIPT_CHARS = 200_000


@dataclass(frozen=True)
class AnalyzeTranscriptCommand:
    """A request to analyse one pasted transcript."""

    transcript: str
    source: AnalysisSource = AnalysisSource.PASTED
    reference: str | None = None


class AnalyzeTranscript:
    """Runs the five-layer pipeline and stores the result."""

    def __init__(
        self,
        *,
        prompts: PromptSource,
        schemas: AnalysisSchemas,
        taxonomy: Taxonomy,
        rubric: Rubric,
        redaction: RedactionPort,
        repository: AnalysisRepository,
        clock: Clock,
    ) -> None:
        self._prompts = prompts
        self._schemas = schemas
        self._taxonomy = taxonomy
        self._rubric = rubric
        self._engine = RubricEngine(rubric)
        self._redaction = redaction
        self._repository = repository
        self._clock = clock

    async def execute(
        self, command: AnalyzeTranscriptCommand, provider: LLMProvider
    ) -> CallAnalysis:
        started = self._clock.now()
        transcript = self._prepare(command.transcript)
        rendered = _render_turns(transcript)

        usage = _UsageTally()
        layers: list[AnalysisLayer] = []

        # --- Essential layers: a failure here means there is no analysis. -----
        l1 = await self._run(provider, L1_PROMPT, self._schemas.l1, usage, transcript=rendered)
        layers.append(_layer(Layer.L1, l1))

        l2 = await self._run(
            provider,
            L2_PROMPT,
            self._schemas.l2,
            usage,
            transcript=rendered,
            l1_summary=_summarise_l1(l1),
        )
        layers.append(_layer(Layer.L2, l2))

        l3 = await self._run(
            provider,
            L3_PROMPT,
            self._schemas.l3,
            usage,
            transcript=rendered,
            l2_summary=_summarise_l2(l2),
            dimensions=self._describe_dimensions(),
        )
        layers.append(_layer(Layer.L3, l3))

        signal_codes = tuple(_strings(l1, "signals"))
        validation = MarkerValidator(self._rubric, transcript).validate(_markers(l3))
        score = self._engine.score(validation.accepted, signal_codes=signal_codes)

        context = _summarise_context(l1, l2, score.score.value)

        # --- Additive layers: a failure degrades the layer, not the call. ----
        l4, l4_error = await self._try_run(
            provider,
            L4_PROMPT,
            self._schemas.l4,
            usage,
            transcript=rendered,
            context=context,
            l4_categories=self._describe_l4_categories(),
        )
        layers.append(_layer(Layer.L4, l4) if l4 else _unavailable(Layer.L4, l4_error))

        l5, l5_error = await self._try_run(
            provider, L5_PROMPT, self._schemas.l5, usage, transcript=rendered, context=context
        )
        layers.append(_layer(Layer.L5, l5) if l5 else _unavailable(Layer.L5, l5_error))

        # A broker record names a real person, so its evidence is checked against
        # the transcript exactly as a score marker's is. Requiring the field to be
        # present is not enough: a model that has no broker to report will fill it
        # with a plausible-looking placeholder.
        attributions = _validated_attributions(_broker_signals(l4), transcript)

        finished = self._clock.now()
        analysis = CallAnalysis(
            reference=command.reference or await self._repository.next_reference(),
            title=_text(l2, "title") or _text(l1, "call_type") or "Untitled call",
            summary=_text(l2, "summary"),
            category=self._taxonomy.category(_text(l2, "category")),
            resolution=Resolution(_text(l2, "resolution")),
            sentiment=self._taxonomy.sentiment_arc(
                _text(l1, "member_sentiment_start"), _text(l1, "member_sentiment_end")
            ),
            transcript=transcript,
            score=score,
            source=command.source,
            agent_name=_text(l3, "agent_name") or _agent_from(transcript),
            member_context=_text(l1, "member_context") or None,
            duration_minutes=_positive_int(l2, "duration_minutes"),
            signal_codes=signal_codes,
            accepted_markers=validation.accepted,
            rejected_marker_notes=tuple(item.explanation for item in validation.rejected),
            rejected_attribution_notes=attributions.rejected,
            l4_signals=self._l4_signals(l4),
            broker_signals=attributions.accepted,
            assist_events=_assist_events(l5),
            layers=tuple(layers),
            provenance=Provenance(
                provider=provider.name,
                model=provider.model,
                prompt_version=self._prompt_versions(),
                rubric_version=self._rubric.version,
                analysed_at=started,
                total_input_tokens=usage.input_tokens,
                total_output_tokens=usage.output_tokens,
                duration_ms=(finished - started).total_seconds() * 1000,
            ),
        )

        await self._repository.save(analysis)
        return analysis

    # --- pipeline steps ---------------------------------------------------

    def _prepare(self, text: str) -> Transcript:
        if len(text) > _MAX_TRANSCRIPT_CHARS:
            raise ValidationError(
                "The transcript is too long to analyse in one call.",
                detail=f"Limit is {_MAX_TRANSCRIPT_CHARS:,} characters.",
            )
        return self._redaction.redact(parse_transcript(text))

    async def _run(
        self,
        provider: LLMProvider,
        prompt_id: str,
        schema: type[Any],
        usage: _UsageTally,
        **values: Any,
    ) -> dict[str, Any]:
        prompt = self._prompts.render(prompt_id, **values)
        result: StructuredResult[Any] = await provider.complete(
            LlmRequest(
                prompt=prompt.text,
                response_model=schema,
                prompt_id=prompt.id,
                prompt_version=prompt.version,
            )
        )
        usage.add(result.usage)
        payload = result.value.model_dump()
        return dict(payload)

    async def _try_run(
        self,
        provider: LLMProvider,
        prompt_id: str,
        schema: type[Any],
        usage: _UsageTally,
        **values: Any,
    ) -> tuple[dict[str, Any] | None, str]:
        """Run an additive layer, converting failure into a recorded reason."""
        try:
            return await self._run(provider, prompt_id, schema, usage, **values), ""
        except NanoVoxError as exc:
            return None, exc.message

    # --- prompt context ---------------------------------------------------

    def _describe_dimensions(self) -> str:
        return "\n".join(
            f"- {code}: {dimension.label}"
            for code, dimension in sorted(self._rubric.dimensions.items())
        )

    def _describe_l4_categories(self) -> str:
        return "\n".join(
            f"- {category.code}: {category.label} (owner: {category.owner.name})"
            for category in self._taxonomy.l4_categories
        )

    def _prompt_versions(self) -> str:
        versions = {
            prompt_id: self._prompts.version_of(prompt_id)
            for prompt_id in (L1_PROMPT, L2_PROMPT, L3_PROMPT, L4_PROMPT, L5_PROMPT)
        }
        distinct = set(versions.values())
        if len(distinct) == 1:
            return distinct.pop()
        return ",".join(f"{key}={value}" for key, value in sorted(versions.items()))

    # --- payload conversion ------------------------------------------------

    def _l4_signals(self, payload: dict[str, Any] | None) -> tuple[L4Signal, ...]:
        if payload is None:
            return ()
        signals: list[L4Signal] = []
        for entry in _entries(payload, "signals"):
            narrative = _text(entry, "narrative")
            if not narrative:
                continue
            signals.append(
                L4Signal(
                    category=self._taxonomy.l4_category(_text(entry, "category")),
                    severity=Severity(_text(entry, "severity")),
                    narrative=narrative,
                    recommended_action=_text(entry, "recommended_action") or None,
                )
            )
        return tuple(signals)


class _UsageTally:
    """Accumulates token usage across the five calls."""

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0

    def add(self, usage: TokenUsage) -> None:
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens


# --- helpers --------------------------------------------------------------


def _render_turns(transcript: Transcript) -> str:
    """Number every turn so the model can cite evidence by index."""
    lines = []
    for turn in transcript.turns:
        speaker = turn.speaker_name or turn.role.value.title()
        lines.append(f"[{turn.seq}] {turn.role.value} {speaker}: {turn.text}")
    return "\n".join(lines)


def _layer(layer: Layer, payload: dict[str, Any]) -> AnalysisLayer:
    return AnalysisLayer(layer=layer, payload=payload)


def _unavailable(layer: Layer, reason: str) -> AnalysisLayer:
    # Explicitly unavailable, never silently empty.
    return AnalysisLayer(layer=layer, payload={UNAVAILABLE_KEY: True, REASON_KEY: reason})


def _text(payload: dict[str, Any] | None, key: str) -> str:
    if payload is None:
        return ""
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def _positive_int(payload: dict[str, Any] | None, key: str) -> int | None:
    if payload is None:
        return None
    value = payload.get(key)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def _strings(payload: dict[str, Any] | None, key: str) -> list[str]:
    if payload is None:
        return []
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _entries(payload: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    if payload is None:
        return []
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _markers(payload: dict[str, Any] | None) -> list[ScoreMarker]:
    markers: list[ScoreMarker] = []
    for entry in _entries(payload, "markers"):
        description = _text(entry, "description")
        quote = _text(entry, "quote")
        dimension = _text(entry, "dimension")
        turn = entry.get("evidence_turn_seq")
        if not (description and quote and dimension) or not isinstance(turn, int):
            # A marker missing its evidence cannot be scored; the validator would
            # reject it anyway, and constructing it would raise.
            continue
        markers.append(
            ScoreMarker(
                polarity=Polarity(_text(entry, "polarity") or Polarity.NEGATIVE.value),
                dimension=dimension,
                description=description,
                evidence_turn_seq=max(0, turn),
                quote=quote,
            )
        )
    return markers


@dataclass(frozen=True)
class _Attributions:
    """Broker signals that survived evidence checking, and why the rest did not."""

    accepted: tuple[BrokerSignal, ...]
    rejected: tuple[str, ...]


def _validated_attributions(
    signals: tuple[BrokerSignal, ...], transcript: Transcript
) -> _Attributions:
    """Keep only attributions whose quote genuinely appears in the turn they cite."""
    accepted: list[BrokerSignal] = []
    rejected: list[str] = []

    for signal in signals:
        turn = transcript.turn(signal.evidence_turn_seq)
        if turn is None:
            rejected.append(
                f"Attribution to {signal.broker_name!r} cites turn "
                f"{signal.evidence_turn_seq}, which does not exist."
            )
        elif not turn.contains(signal.quote):
            rejected.append(
                f"Attribution to {signal.broker_name!r} quotes text that does not appear "
                f"in turn {signal.evidence_turn_seq}: {signal.quote!r}"
            )
        else:
            accepted.append(signal)

    return _Attributions(accepted=tuple(accepted), rejected=tuple(rejected))


def _broker_signals(payload: dict[str, Any] | None) -> tuple[BrokerSignal, ...]:
    signals: list[BrokerSignal] = []
    for entry in _entries(payload, "broker_signals"):
        name = _text(entry, "broker_name")
        issue = _text(entry, "issue")
        quote = _text(entry, "quote")
        turn = entry.get("evidence_turn_seq")
        if not (name and issue and quote) or not isinstance(turn, int):
            # Attribution without evidence names a real person on no basis.
            continue
        signals.append(
            BrokerSignal(
                broker_name=name,
                polarity=Polarity(_text(entry, "polarity") or Polarity.NEGATIVE.value),
                basis=AttributionBasis.NAMED_IN_CALL,
                issue=issue,
                evidence_turn_seq=max(0, turn),
                quote=quote,
            )
        )
    return tuple(signals)


def _assist_events(payload: dict[str, Any] | None) -> tuple[AssistEvent, ...]:
    events: list[AssistEvent] = []
    for entry in _entries(payload, "events"):
        trigger = _text(entry, "trigger")
        recommendation = _text(entry, "recommendation")
        if not (trigger and recommendation):
            continue
        turn = entry.get("at_turn_seq")
        at_turn = turn if isinstance(turn, int) and turn > NO_TURN else None
        events.append(
            AssistEvent(
                outcome=AssistOutcome(_text(entry, "outcome") or AssistOutcome.FIRED.value),
                trigger=trigger,
                recommendation=recommendation,
                severity=Severity(_text(entry, "severity") or Severity.MEDIUM.value),
                at_turn_seq=at_turn,
                timestamp_label=_text(entry, "timestamp_label") or None,
            )
        )
    return tuple(events)


def _agent_from(transcript: Transcript) -> str | None:
    for turn in transcript.turns:
        if turn.speaker_name:
            return turn.speaker_name
    return None


def _summarise_l1(payload: dict[str, Any]) -> str:
    return (
        f"Call type: {_text(payload, 'call_type')}. "
        f"Member sentiment: {_text(payload, 'member_sentiment_start')} to "
        f"{_text(payload, 'member_sentiment_end')}. "
        f"Agent tone: {_text(payload, 'agent_tone')}. "
        f"Signals: {', '.join(_strings(payload, 'signals')) or 'none'}."
    )


def _summarise_l2(payload: dict[str, Any]) -> str:
    return (
        f"{_text(payload, 'title')}. {_text(payload, 'summary')} "
        f"Category: {_text(payload, 'category')}. Resolution: {_text(payload, 'resolution')}."
    )


def _summarise_context(l1: dict[str, Any], l2: dict[str, Any], score: int) -> str:
    return f"{_summarise_l1(l1)}\n{_summarise_l2(l2)}\nComputed agent score: {score}/100."
