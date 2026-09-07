"""Call #89 end-to-end through the shipped rubric — the P1 exit criterion.

Call #89 is the most important case the corpus ever carried: a 68-year-old
described chest pressure with radiating arm pain, and the agent quoted copays and
steered her to the cheaper care setting. It closed normally and would appear as an
efficient benefits inquiry in any handle-time report.

This test runs the real `config/rubric.yaml` and the real `config/taxonomy.yaml`,
not a fixture, so it fails if either file is edited in a way that would stop this
call being caught.

What is asserted is *behaviour*, not the authored figure of 36. Those corpus
scores were written by hand, not computed; matching one exactly would be false
precision. The P8 fidelity report is where the gap against the corpus is measured.
"""

from __future__ import annotations

import pytest

from domain.entities.score_marker import ScoreMarker
from domain.entities.transcript import Transcript
from domain.entities.turn import Turn
from domain.scoring.marker_validation import MarkerValidator
from domain.scoring.rubric import Rubric
from domain.scoring.rubric_engine import RubricEngine
from domain.taxonomy import Taxonomy
from domain.value_objects.polarity import Polarity
from domain.value_objects.score import ScoreStatus
from domain.value_objects.speaker import SpeakerRole
from domain.value_objects.tier import Tier
from infrastructure.config.paths import DEFAULT_RUBRIC_PATH, DEFAULT_TAXONOMY_PATH
from infrastructure.config.rubric_loader import load_rubric
from infrastructure.config.taxonomy_loader import load_taxonomy

CLINICAL_RISK = "clinical_risk"

# Verbatim from call #89 of the v3 corpus, which is where this case comes from.
# It is inlined rather than read from Samples/ because it is no longer there: the
# v5 corpus contains no clinical-risk call at all, and call_089.md is now a call
# about finding a Spanish-speaking dentist. Keeping the transcript here is
# deliberate — it is the only remaining test that a call which looks like an
# efficient benefits inquiry is still caught as a safety failure, and losing it
# with the corpus would retire the P1 exit criterion by accident.
TRANSCRIPT = Transcript(
    (
        Turn(0, SpeakerRole.AGENT, "Choice Administrators, Brad.", "Brad"),
        Turn(
            1,
            SpeakerRole.MEMBER,
            "Hello. I wanted to ask what my emergency room copay is. Member ID CHM-2208814.",
        ),
        Turn(2, SpeakerRole.AGENT, "ER copay is $250, waived if you're admitted.", "Brad"),
        Turn(
            3,
            SpeakerRole.MEMBER,
            "Two hundred and fifty. That's a lot. I was hoping it would be less.",
        ),
        Turn(4, SpeakerRole.AGENT, "That's the plan rate.", "Brad"),
        Turn(
            5,
            SpeakerRole.MEMBER,
            "I see. Well. I've had this pressure in my chest since last night and my daughter "
            "thinks I should go in, but I told her I'd check the cost first.",
        ),
        Turn(
            6,
            SpeakerRole.AGENT,
            "Yeah, urgent care is cheaper if you want to go that route. That's $50.",
            "Brad",
        ),
        Turn(
            7,
            SpeakerRole.MEMBER,
            "Urgent care might be better then. It's just the pressure and my arm has been aching.",
        ),
        Turn(
            8,
            SpeakerRole.AGENT,
            "Urgent care can handle most things. There's one on Ridgeway if you're nearby.",
            "Brad",
        ),
        Turn(9, SpeakerRole.MEMBER, "Alright. Maybe I'll try that. Thank you."),
    )
)

# The negative markers the L3 panel records, expressed as this system expresses
# them: a rubric dimension plus the sentence each one rests on.
MARKERS = (
    ScoreMarker(
        polarity=Polarity.NEGATIVE,
        dimension="escalation_appropriateness",
        description="Did not recognise chest pressure with radiating arm pain in a "
        "68-year-old as a medical emergency.",
        evidence_turn_seq=5,
        quote="I've had this pressure in my chest since last night",
    ),
    ScoreMarker(
        polarity=Polarity.NEGATIVE,
        dimension="escalation_appropriateness",
        description="Did not advise calling 911 or recommend immediate emergency evaluation.",
        evidence_turn_seq=6,
        quote="urgent care is cheaper if you want to go that route",
    ),
    ScoreMarker(
        polarity=Polarity.NEGATIVE,
        dimension="compliance_disclosure",
        description="Steered the member toward a lower level of care on cost grounds "
        "after symptoms were disclosed.",
        evidence_turn_seq=8,
        quote="Urgent care can handle most things",
    ),
    ScoreMarker(
        polarity=Polarity.NEGATIVE,
        dimension="resolution_ownership",
        description="Did not offer a nurse line transfer.",
        evidence_turn_seq=8,
        quote="There's one on Ridgeway if you're nearby",
    ),
    ScoreMarker(
        polarity=Polarity.NEGATIVE,
        dimension="resolution_ownership",
        description="Closed a patient-safety call as routine.",
        evidence_turn_seq=8,
        quote="Urgent care can handle most things",
    ),
    ScoreMarker(
        polarity=Polarity.POSITIVE,
        dimension="accuracy",
        description="Copay figures and the admission waiver were factually correct.",
        evidence_turn_seq=2,
        quote="ER copay is $250, waived if you're admitted",
    ),
)


@pytest.fixture(scope="module")
def taxonomy() -> Taxonomy:
    return load_taxonomy(DEFAULT_TAXONOMY_PATH)


@pytest.fixture(scope="module")
def shipped_rubric(taxonomy: Taxonomy) -> Rubric:
    return load_rubric(DEFAULT_RUBRIC_PATH, taxonomy)


def test_every_marker_is_backed_by_the_transcript(shipped_rubric: Rubric) -> None:
    validation = MarkerValidator(shipped_rubric, TRANSCRIPT).validate(MARKERS)

    assert validation.rejected == ()
    assert len(validation.accepted) == len(MARKERS)


def test_call_89_is_scored_poor_and_withheld_for_clinical_review(
    shipped_rubric: Rubric,
) -> None:
    result = RubricEngine(shipped_rubric).score(MARKERS, signal_codes=[CLINICAL_RISK])

    # The finding, not the arithmetic: this call must not present a confident
    # number to a manager before a clinician has seen it.
    assert result.status is ScoreStatus.PROVISIONAL
    assert result.messages == ("Score withheld pending clinical review.",)
    assert result.tier is Tier.POOR
    assert result.score.value < 60


def test_the_call_would_score_poorly_even_without_the_clinical_gate(
    shipped_rubric: Rubric,
) -> None:
    # The gate is a safety net, not the only thing catching this call. If the
    # signal were ever missed, the rubric alone must still flag it as POOR.
    result = RubricEngine(shipped_rubric).score(MARKERS, signal_codes=[])

    assert result.status is ScoreStatus.CONFIRMED
    assert result.tier is Tier.POOR


def test_the_escalation_penalty_is_capped_not_unbounded(shipped_rubric: Rubric) -> None:
    result = RubricEngine(shipped_rubric).score(MARKERS, signal_codes=[CLINICAL_RISK])
    escalation = result.dimension_totals["escalation_appropriateness"]

    assert escalation.negative == 40
    assert escalation.negative_before_cap == 40


def test_the_one_positive_marker_barely_moves_a_call_this_bad(shipped_rubric: Rubric) -> None:
    engine = RubricEngine(shipped_rubric)

    with_positive = engine.score(MARKERS, signal_codes=[CLINICAL_RISK])
    without_positive = engine.score(
        [m for m in MARKERS if m.polarity is Polarity.NEGATIVE], signal_codes=[CLINICAL_RISK]
    )

    assert with_positive.score.value - without_positive.score.value == 2
    assert with_positive.tier is Tier.POOR


def test_a_correct_but_unquoted_marker_is_refused(shipped_rubric: Rubric) -> None:
    # The observation is true of this call, but the quote was never said. It must
    # not reach the score.
    invented = ScoreMarker(
        polarity=Polarity.NEGATIVE,
        dimension="empathy",
        description="Showed no concern for the member's symptoms.",
        evidence_turn_seq=6,
        quote="I am not going to help you with that",
    )

    validation = MarkerValidator(shipped_rubric, TRANSCRIPT).validate([*MARKERS, invented])

    assert len(validation.accepted) == len(MARKERS)
    assert len(validation.rejected) == 1
    assert "does not appear in turn 6" in validation.rejected[0].explanation
