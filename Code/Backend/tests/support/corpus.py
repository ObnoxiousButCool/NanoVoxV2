"""A small fixture corpus with figures that can be checked by hand.

Eleven calls, deliberately shaped so every dashboard definition has something to
prove:

* Two agents above the significance threshold and one below it, so the "shown but
  not tier-rated" rule has both cases.
* A resolution mix where RESOLVED, PARTIALLY RESOLVED, ESCALATED and UNRESOLVED
  are all present and distinguishable — a first-contact-resolution figure that
  quietly counted partials would be visibly wrong.
* One broker who is net positive and one who is not.
* An L4 category with no signals at all, so "absence is shown" is testable.
* One call raising two findings in the same L4 category, so calls-not-signals
  counting is testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

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
from domain.entities.transcript import Transcript
from domain.entities.turn import Turn
from domain.scoring.rubric_engine import ScoreResult
from domain.taxonomy import Taxonomy
from domain.value_objects.caller_type import CallerType
from domain.value_objects.polarity import Polarity
from domain.value_objects.resolution import Resolution
from domain.value_objects.score import Score, ScoreStatus
from domain.value_objects.severity import Severity
from domain.value_objects.speaker import SpeakerRole
from domain.value_objects.tier import Tier

BASE_TIME = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)

RESOLVED = Resolution.RESOLVED
PARTIAL = Resolution.PARTIALLY_RESOLVED
ESCALATED = Resolution.ESCALATED
UNRESOLVED = Resolution.UNRESOLVED


@dataclass(frozen=True)
class CallSpec:
    """The shape of one fixture call."""

    reference: str
    agent: str | None
    category: str
    resolution: Resolution
    score: int
    provisional: bool = False
    signals: tuple[str, ...] = ()
    l4: tuple[str, ...] = ()
    broker: tuple[str, Polarity] | None = None
    # Defaults to one member per call. Set it explicitly to give two calls the
    # same member, which is what makes repeat contact testable.
    member_id: str | None = None
    # Who called. Defaults to MEMBER, as most of a real corpus does; the two
    # non-member callers below are what makes the caller filter testable.
    caller: CallerType = CallerType.MEMBER


# Sarah: 5 calls, scores 90/95/88/70/60 -> avg 80.6, tier-rated.
# Brad:  5 calls, scores 30/40/25/55/50 -> avg 40.0, tier-rated, 3 unresolved.
# Priya: 1 call,  score 96              -> below threshold, NOT tier-rated.
SPECS: tuple[CallSpec, ...] = (
    # F0001 and F0002 share a member: the corpus needs one repeat contact for
    # member-level aggregation to be testable at all.
    CallSpec("F0001", "Sarah", "coverage_benefits", RESOLVED, 90, member_id="CHM-REPEAT"),
    CallSpec("F0002", "Sarah", "claims_eob", RESOLVED, 95, member_id="CHM-REPEAT"),
    CallSpec("F0003", "Sarah", "coverage_benefits", PARTIAL, 88),
    CallSpec(
        "F0004",
        "Sarah",
        "enrollment_id_cards",
        ESCALATED,
        70,
        broker=("Patricia Nunez", Polarity.POSITIVE),
        l4=("broker_attribution",),
    ),
    CallSpec(
        "F0005",
        "Sarah",
        "pharmacy",
        RESOLVED,
        60,
        broker=("Patricia Nunez", Polarity.POSITIVE),
    ),
    CallSpec(
        "F0006",
        "Brad",
        "coverage_benefits",
        UNRESOLVED,
        30,
        provisional=True,
        signals=("clinical_risk",),
        l4=("compliance_risk", "agent_coaching"),
    ),
    CallSpec(
        "F0007",
        "Brad",
        "coverage_benefits",
        UNRESOLVED,
        40,
        signals=("compliance_disclosure_missing",),
        l4=("compliance_risk",),
    ),
    CallSpec(
        "F0008",
        "Brad",
        "claims_eob",
        UNRESOLVED,
        25,
        signals=("compliance_disclosure_missing",),
        # Two findings in one category: the call counts once.
        l4=("process_breakdown", "process_breakdown"),
        broker=("Marcus Trent", Polarity.NEGATIVE),
    ),
    # An employer's call: a group's renewal, not a member's claim. It still has
    # a member_id from the builder's default, which is the point — the caller
    # type is what separates the populations, not the presence of an identifier.
    CallSpec(
        "F0009",
        "Brad",
        "billing_premium",
        ESCALATED,
        55,
        l4=("process_breakdown",),
        broker=("Marcus Trent", Polarity.NEGATIVE),
        caller=CallerType.EMPLOYER,
    ),
    CallSpec(
        "F0010",
        "Brad",
        "provider_network",
        PARTIAL,
        50,
        l4=("process_breakdown",),
        broker=("Marcus Trent", Polarity.NEGATIVE),
        caller=CallerType.BROKER,
    ),
    CallSpec("F0011", "Priya", "claims_eob", RESOLVED, 96),
)

# Figures a reader can verify against SPECS above without running anything.
TOTAL_CALLS = 11
RESOLVED_COUNT = 4  # F0001, F0002, F0005, F0011
ESCALATED_COUNT = 2  # F0004, F0009
UNRESOLVED_COUNT = 3  # F0006, F0007, F0008
PARTIAL_COUNT = 2  # F0003, F0010
SCORES = (90, 95, 88, 70, 60, 30, 40, 25, 55, 50, 96)
MEMBER_CALLS = 9  # every call but F0009 and F0010


def _transcript(reference: str) -> Transcript:
    return Transcript(
        (
            Turn(0, SpeakerRole.AGENT, f"Choice Administrators, call {reference}.", "Agent"),
            Turn(1, SpeakerRole.MEMBER, "I have a question about my plan."),
        )
    )


def build_analysis(spec: CallSpec, taxonomy: Taxonomy, index: int) -> CallAnalysis:
    """Turn a spec into a storable analysis."""
    score = Score(spec.score)
    return CallAnalysis(
        reference=spec.reference,
        title=f"Fixture call {spec.reference}",
        summary=f"A {spec.category} call that ended {spec.resolution.value}.",
        category=taxonomy.category(spec.category),
        resolution=spec.resolution,
        sentiment=taxonomy.sentiment_arc("NEUTRAL", "SATISFIED"),
        # A distinct member per call unless the spec says otherwise, mirroring a
        # real corpus where most members appear once.
        member_id=spec.member_id or f"CHM{spec.reference}",
        caller_type=spec.caller.value,
        transcript=_transcript(spec.reference),
        score=ScoreResult(
            score=score,
            status=ScoreStatus.PROVISIONAL if spec.provisional else ScoreStatus.CONFIRMED,
            tier=_tier(spec.score),
            applied=(),
            dimension_totals={},
            total_positive=0,
            total_negative=100 - spec.score,
            applied_offset=0,
            triggered_gate_ids=("clinical_urgency_unrecognised",) if spec.provisional else (),
            messages=("Score withheld pending clinical review.",) if spec.provisional else (),
        ),
        source=AnalysisSource.CORPUS_RUN,
        agent_name=spec.agent,
        duration_minutes=6,
        # Spread a call a day from BASE_TIME, so the fixture spans three weeks
        # and the weekly trend has something to be a trend of. Handle time
        # alternates either side of six minutes, which is what makes the
        # speed-against-quality split land on a boundary worth testing.
        duration_seconds=300 if index % 2 else 480,
        started_at=BASE_TIME + timedelta(days=index, hours=index % 6),
        signal_codes=spec.signals,
        l4_signals=tuple(
            L4Signal(
                category=taxonomy.l4_category(code),
                severity=Severity.HIGH,
                narrative=f"A {code} finding on {spec.reference}.",
            )
            for code in spec.l4
        ),
        broker_signals=(
            (
                BrokerSignal(
                    broker_name=spec.broker[0],
                    polarity=spec.broker[1],
                    basis=AttributionBasis.NAMED_IN_CALL,
                    issue=f"Broker conduct reported on {spec.reference}.",
                    evidence_turn_seq=1,
                    quote="I have a question about my plan.",
                ),
            )
            if spec.broker
            else ()
        ),
        assist_events=(
            AssistEvent(
                outcome=AssistOutcome.SHOULD_HAVE_FIRED,
                trigger="symptom keywords",
                recommendation="Transfer to the nurse line.",
                severity=Severity.CRITICAL,
                at_turn_seq=1,
            ),
        )
        if spec.provisional
        else (),
        layers=(AnalysisLayer(layer=Layer.L1, payload={"call_type": spec.category}),),
        provenance=Provenance(
            provider="fixture",
            model="fixture-model",
            prompt_version="1.0.0",
            rubric_version="1.0.0",
            analysed_at=BASE_TIME + timedelta(hours=index),
            total_input_tokens=100,
            total_output_tokens=50,
        ),
    )


def _tier(score: int) -> Tier:
    if score >= 86:
        return Tier.GOOD
    if score >= 60:
        return Tier.AVERAGE
    return Tier.POOR


def build_corpus(taxonomy: Taxonomy) -> tuple[CallAnalysis, ...]:
    return tuple(build_analysis(spec, taxonomy, index) for index, spec in enumerate(SPECS))
