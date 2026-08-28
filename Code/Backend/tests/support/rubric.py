"""Builders for scoring test fixtures.

A small, explicit rubric is used for most engine tests rather than the shipped
one, so the arithmetic being asserted is obvious from the test and does not move
when the real weights are recalibrated.
"""

from __future__ import annotations

from domain.entities.score_marker import ScoreMarker
from domain.entities.transcript import Transcript
from domain.entities.turn import Turn
from domain.scoring.rubric import Dimension, Gate, GateCondition, GateEffect, Rubric
from domain.value_objects.polarity import Polarity
from domain.value_objects.speaker import SpeakerRole
from domain.value_objects.tier import TierThresholds

CLINICAL_GATE = Gate(
    id="clinical_urgency_unrecognised",
    condition=GateCondition.SIGNAL_PRESENT,
    argument="clinical_risk",
    effect=GateEffect.SUSPEND_SCORE,
    message="Score withheld pending clinical review.",
)


def dimension(
    code: str,
    *,
    positive: int = 5,
    negative: int = 10,
    max_positive: int = 10,
    max_negative: int = 20,
) -> Dimension:
    return Dimension(
        code=code,
        label=code.replace("_", " ").title(),
        positive=positive,
        negative=negative,
        max_positive=max_positive,
        max_negative=max_negative,
    )


def rubric(
    *dimensions: Dimension,
    base_score: int = 100,
    max_positive_offset: int = 15,
    gates: tuple[Gate, ...] = (),
    good: int = 86,
    average: int = 60,
    min_calls_for_tier_rating: int = 5,
) -> Rubric:
    members = dimensions or (dimension("empathy"), dimension("accuracy"))
    return Rubric(
        version="test-1.0.0",
        base_score=base_score,
        max_positive_offset=max_positive_offset,
        dimensions={item.code: item for item in members},
        tiers=TierThresholds(good=good, average=average),
        min_calls_for_tier_rating=min_calls_for_tier_rating,
        gates=gates,
    )


def marker(
    dimension_code: str,
    *,
    polarity: Polarity = Polarity.NEGATIVE,
    seq: int = 0,
    quote: str = "quoted text",
    description: str = "something was observed",
) -> ScoreMarker:
    return ScoreMarker(
        polarity=polarity,
        dimension=dimension_code,
        description=description,
        evidence_turn_seq=seq,
        quote=quote,
    )


def transcript(*texts: str) -> Transcript:
    """A transcript whose turns alternate agent/member, numbered from zero."""
    lines = texts or ("quoted text", "member reply")
    return Transcript(
        tuple(
            Turn(
                seq=index,
                role=SpeakerRole.AGENT if index % 2 == 0 else SpeakerRole.MEMBER,
                text=text,
            )
            for index, text in enumerate(lines)
        )
    )
