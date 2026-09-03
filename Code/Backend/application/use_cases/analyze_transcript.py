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

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from re import Pattern
from typing import Any

from application.dto.analysis_schemas import NO_TURN, AnalysisSchemas
from application.ports.analysis_repository import AnalysisRepository
from application.ports.clock import Clock
from application.ports.llm_provider import LLMProvider, LlmRequest, StructuredResult, TokenUsage
from application.ports.prompts import PromptSource
from application.ports.redaction import RedactionPort
from domain.attribution_notes import (
    broker_name_in,
    is_the_agent_note,
    missing_turn_note,
    not_a_broker_note,
    quote_not_found_note,
)
from domain.broker_evidence import is_the_agent, quote_names_a_broker
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
from domain.member_id import find_member_id
from domain.parsing import parse_transcript
from domain.scoring.marker_validation import MarkerValidator
from domain.scoring.rubric import Rubric
from domain.scoring.rubric_engine import RubricEngine
from domain.signal_evidence import RaisedSignal, validate_signals
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
class StoredAnalysis:
    """A completed analysis and the id it was stored under.

    The id is returned because the caller's next move is almost always to open
    the call it just created; without it the UI would have to search for the
    record it has in its hand.
    """

    call_id: int
    analysis: CallAnalysis


@dataclass(frozen=True)
class AnalyzeTranscriptCommand:
    """A request to analyse one pasted transcript."""

    transcript: str
    source: AnalysisSource = AnalysisSource.PASTED
    reference: str | None = None
    # Set when the source states how long the call ran. It wins over the model's
    # estimate: the corpus files carry the real figure in their header, and a
    # model reading only the words produces a plausible number instead — six
    # round values across a hundred calls, against the fourteen the corpus
    # actually contains. Pasted transcripts carry no header, so they still fall
    # back to the estimate.
    duration_minutes: int | None = None
    # The rest of what the source states about the call. Carried through
    # untouched: no model sees them, and none of them is derived.
    duration_seconds: int | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    caller_type: str | None = None


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
        member_id_pattern: Pattern[str] | None = None,
        broker_terms: Pattern[str] | None = None,
    ) -> None:
        self._prompts = prompts
        self._schemas = schemas
        self._taxonomy = taxonomy
        self._rubric = rubric
        self._engine = RubricEngine(rubric)
        self._redaction = redaction
        self._repository = repository
        self._clock = clock
        # Optional: a deployment that does not issue member identifiers, or has
        # not configured their shape, simply stores none.
        self._member_id_pattern = member_id_pattern
        # The words that make a quote evidence of a broker relationship. None
        # disables the check rather than rejecting everything.
        self._broker_terms = broker_terms

    async def execute(
        self, command: AnalyzeTranscriptCommand, provider: LLMProvider
    ) -> StoredAnalysis:
        started = self._clock.now()
        transcript = self._prepare(command.transcript)
        rendered = _render_turns(transcript)

        usage = _UsageTally()
        layers: list[AnalysisLayer] = []

        # --- Essential layers: a failure here means there is no analysis. -----
        l1 = await self._run(provider, L1_PROMPT, self._schemas.l1, usage, transcript=rendered)
        layers.append(_layer(Layer.L1, l1))

        # Checked against the transcript before anything is told about it. A
        # signal withholds the score and opens a review queue, so it is the last
        # claim that should be taken on trust — and, until this check existed,
        # the only one that was. Validated here rather than at scoring time so a
        # signal that failed its evidence is not fed to the later layers either.
        signals = validate_signals(
            _raised_signals(l1), transcript, (item.code for item in self._taxonomy.signal_types)
        )

        l2 = await self._run(
            provider,
            L2_PROMPT,
            self._schemas.l2,
            usage,
            transcript=rendered,
            l1_summary=_summarise_l1(l1, signals.accepted),
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

        validation = MarkerValidator(self._rubric, transcript).validate(_markers(l3))
        score = self._engine.score(validation.accepted, signal_codes=signals.accepted)

        # Resolved before the attributions are checked, which needs it: an
        # attribution naming the agent on the call is not a member naming a broker.
        agent_name = _text(l3, "agent_name") or _agent_from(transcript)

        context = _summarise_context(l1, l2, score.score.value, signals.accepted)

        # --- Additive layers: a failure degrades the layer, not the call. ----
        l4, l4_error = await self._try_run(
            provider,
            L4_PROMPT,
            self._schemas.l4,
            usage,
            transcript=rendered,
            context=context,
            l4_categories=self._describe_l4_categories(),
            correction="",
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
        attributions = _validated_attributions(
            _broker_signals(l4),
            transcript,
            agent_name=agent_name,
            broker_terms=self._broker_terms,
        )
        if attributions.rejected and l4 is not None:
            attributions = await self._repair_attributions(
                provider, attributions, transcript, usage, rendered, context, agent_name
            )

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
            agent_name=agent_name,
            member_id=find_member_id(transcript, self._member_id_pattern)
            if self._member_id_pattern
            else None,
            member_context=_text(l1, "member_context") or None,
            duration_minutes=(
                command.duration_minutes
                if command.duration_minutes is not None
                else _positive_int(l2, "duration_minutes")
            ),
            duration_seconds=command.duration_seconds,
            started_at=command.started_at,
            ended_at=command.ended_at,
            caller_type=command.caller_type,
            signal_codes=signals.accepted,
            accepted_markers=validation.accepted,
            rejected_marker_notes=(
                *(item.explanation for item in validation.rejected),
                # Kept in the same place a rejected marker goes: both are the
                # model claiming something the transcript does not say, and a
                # reader looking for that has one list to read.
                *signals.rejection_notes,
            ),
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

        call_id = await self._repository.save(analysis)
        return StoredAnalysis(call_id=call_id, analysis=analysis)

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

    async def _repair_attributions(
        self,
        provider: LLMProvider,
        first: _Attributions,
        transcript: Transcript,
        usage: _UsageTally,
        rendered: str,
        context: str,
        agent_name: str | None,
    ) -> _Attributions:
        """Ask once more for attributions whose quote did not match.

        The evidence rule is not relaxed here — the second answer is validated
        exactly as the first. What changes is that the model is told which quote
        failed and shown the turn it was supposed to be copying, which is the
        difference between a model that elided a few words and a model that
        invented them. Only the first is recoverable, and only by asking again.

        A failure to repair is not a failure of the call: the original rejections
        stand and the analysis continues.
        """
        l4, _ = await self._try_run(
            provider,
            L4_PROMPT,
            self._schemas.l4,
            usage,
            transcript=rendered,
            context=context,
            l4_categories=self._describe_l4_categories(),
            correction=_attribution_correction(first.rejected, transcript),
        )
        if l4 is None:
            return first

        second = _validated_attributions(
            _broker_signals(l4),
            transcript,
            agent_name=agent_name,
            broker_terms=self._broker_terms,
        )

        # Union, not replacement: the retry must not cost us an attribution the
        # first pass had already evidenced properly.
        accepted = list(first.accepted)
        seen = {_attribution_key(signal) for signal in accepted}
        for signal in second.accepted:
            if _attribution_key(signal) not in seen:
                accepted.append(signal)
                seen.add(_attribution_key(signal))

        recovered = {signal.broker_name for signal in second.accepted}
        rejected = tuple(
            note for note in first.rejected if (broker_name_in(note) or "") not in recovered
        )
        return _Attributions(accepted=tuple(accepted), rejected=rejected)

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


def _raised_signals(payload: dict[str, Any] | None) -> list[RaisedSignal]:
    """The signals L1 raised, with whatever evidence each one carries.

    A malformed entry is kept rather than skipped, so the validator refuses it
    and the refusal is recorded. Dropping it here would make an unevidenced
    signal indistinguishable from one that was never raised.
    """
    return [
        RaisedSignal(
            code=_text(entry, "code"),
            quote=_text(entry, "quote"),
            # -1 when absent or not a number, which no transcript has, so the
            # validator reports it as citing a turn that does not exist rather
            # than silently pointing at turn zero.
            evidence_turn_seq=(
                entry["evidence_turn_seq"]
                if isinstance(entry.get("evidence_turn_seq"), int)
                else -1
            ),
        )
        for entry in _entries(payload, "signals")
    ]


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
    signals: tuple[BrokerSignal, ...],
    transcript: Transcript,
    *,
    agent_name: str | None = None,
    broker_terms: Pattern[str] | None = None,
) -> _Attributions:
    """Keep only attributions the transcript genuinely supports.

    Three questions, in order of how cheaply they can be answered wrong:

    1. Does the cited turn exist?
    2. Were the quoted words actually said in it?
    3. Do those words say what the attribution claims — that this person is the
       member's *broker*, and is not the agent who answered the call?

    The third was missing, and its absence is why surgeons, pharmacies and the
    agents themselves reached a screen that names people for Compliance review.
    """
    accepted: list[BrokerSignal] = []
    rejected: list[str] = []

    for signal in signals:
        turn = transcript.turn(signal.evidence_turn_seq)
        if turn is None:
            rejected.append(missing_turn_note(signal.broker_name, signal.evidence_turn_seq))
        elif not turn.contains(signal.quote):
            rejected.append(
                quote_not_found_note(signal.broker_name, signal.evidence_turn_seq, signal.quote)
            )
        elif is_the_agent(signal.broker_name, agent_name):
            rejected.append(is_the_agent_note(signal.broker_name))
        elif not quote_names_a_broker(signal.quote, broker_terms):
            rejected.append(not_a_broker_note(signal.broker_name, signal.quote))
        else:
            accepted.append(signal)

    return _Attributions(accepted=tuple(accepted), rejected=tuple(rejected))


def _attribution_key(signal: BrokerSignal) -> tuple[str, int, str]:
    return (signal.broker_name, signal.evidence_turn_seq, signal.quote)


def _attribution_correction(rejected: tuple[str, ...], transcript: Transcript) -> str:
    """Tell the model exactly which quote failed, and show it the turn to copy."""
    lines = [
        "",
        "CORRECTION — your previous broker_signals were rejected because their",
        "quotes did not appear verbatim in the turn they cited:",
        "",
    ]
    lines.extend(f"- {note}" for note in rejected)
    lines.extend(
        [
            "",
            "The exact text of those turns is:",
            "",
        ]
    )
    for seq in sorted(set(_cited_turns(rejected))):
        turn = transcript.turn(seq)
        if turn is not None:
            lines.append(f"  turn {seq}: {turn.text}")
    lines.extend(
        [
            "",
            "Re-issue every broker signal you still believe is supported, quoting one",
            "unbroken run of characters copied from the turn above — no words skipped",
            "from the middle, no punctuation changed at either end. If no continuous",
            "span supports the attribution, omit that broker entirely.",
        ]
    )
    return "\n".join(lines)


def _cited_turns(rejected: tuple[str, ...]) -> tuple[int, ...]:
    """The turn numbers named in rejection notes, which this module wrote."""
    return tuple(int(match) for note in rejected for match in re.findall(r"turn (\d+)", note))


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


def _summarise_l1(payload: dict[str, Any], signal_codes: Sequence[str]) -> str:
    return (
        f"Call type: {_text(payload, 'call_type')}. "
        f"Member sentiment: {_text(payload, 'member_sentiment_start')} to "
        f"{_text(payload, 'member_sentiment_end')}. "
        f"Agent tone: {_text(payload, 'agent_tone')}. "
        # The validated codes, not what L1 raised: a later layer must not be
        # told about a condition whose evidence did not survive checking.
        f"Signals: {', '.join(signal_codes) or 'none'}."
    )


def _summarise_l2(payload: dict[str, Any]) -> str:
    return (
        f"{_text(payload, 'title')}. {_text(payload, 'summary')} "
        f"Category: {_text(payload, 'category')}. Resolution: {_text(payload, 'resolution')}."
    )


def _summarise_context(
    l1: dict[str, Any], l2: dict[str, Any], score: int, signal_codes: Sequence[str]
) -> str:
    return (
        f"{_summarise_l1(l1, signal_codes)}\n{_summarise_l2(l2)}\n"
        f"Computed agent score: {score}/100."
    )
