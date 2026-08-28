"""Entities enforce the rules that keep evidence honest."""

from __future__ import annotations

import pytest

from domain.entities.assist_event import AssistEvent, AssistOutcome
from domain.entities.broker_signal import AttributionBasis, BrokerSignal
from domain.entities.l4_signal import L4Signal
from domain.entities.score_marker import ScoreMarker
from domain.entities.transcript import Transcript
from domain.entities.turn import Turn, normalise_for_matching
from domain.errors import ValidationError
from domain.taxonomy import L4Category, Owner
from domain.value_objects.polarity import Polarity
from domain.value_objects.severity import Severity
from domain.value_objects.speaker import SpeakerRole

AGENT = SpeakerRole.AGENT
MEMBER = SpeakerRole.MEMBER


class TestTurn:
    def test_rejects_a_negative_or_non_integer_sequence(self) -> None:
        with pytest.raises(ValidationError, match="non-negative integer"):
            Turn(-1, AGENT, "text")
        with pytest.raises(ValidationError, match="non-negative integer"):
            Turn(True, AGENT, "text")

    def test_rejects_empty_text(self) -> None:
        with pytest.raises(ValidationError, match="no text"):
            Turn(0, AGENT, "   ")

    def test_matches_a_quote_that_really_appears(self) -> None:
        turn = Turn(0, MEMBER, "I've had this pressure in my chest since last night")

        assert turn.contains("pressure in my chest")

    def test_tolerates_wrapped_whitespace_and_case(self) -> None:
        # A model reproduces a quote from text that was line-wrapped in the
        # source; rejecting that would throw away correct evidence.
        turn = Turn(0, MEMBER, "I've had this pressure\n  in my chest since last night")

        assert turn.contains("pressure in my chest")
        assert turn.contains("PRESSURE IN MY CHEST")

    def test_does_not_match_words_that_were_never_said(self) -> None:
        turn = Turn(0, MEMBER, "I've had this pressure in my chest")

        assert not turn.contains("I am having a heart attack")

    def test_an_empty_quote_matches_nothing(self) -> None:
        assert not Turn(0, MEMBER, "anything").contains("   ")

    def test_normalisation_collapses_whitespace_and_case(self) -> None:
        assert normalise_for_matching("  A   B\nC  ") == "a b c"


class TestTranscript:
    def test_requires_at_least_one_turn(self) -> None:
        with pytest.raises(ValidationError, match="at least one speaker turn"):
            Transcript(())

    def test_rejects_duplicate_sequences(self) -> None:
        with pytest.raises(ValidationError, match="duplicate turn sequence"):
            Transcript((Turn(0, AGENT, "a"), Turn(0, MEMBER, "b")))

    def test_rejects_out_of_order_turns(self) -> None:
        with pytest.raises(ValidationError, match="ascending sequence"):
            Transcript((Turn(1, AGENT, "a"), Turn(0, MEMBER, "b")))

    def test_finds_a_turn_by_sequence(self) -> None:
        transcript = Transcript((Turn(0, AGENT, "a"), Turn(1, MEMBER, "b")))

        assert transcript.turn(1) is not None
        assert transcript.turn(99) is None

    def test_counts_turns_and_participating_speakers(self) -> None:
        transcript = Transcript(
            (
                Turn(0, AGENT, "a"),
                Turn(1, MEMBER, "b"),
                Turn(2, SpeakerRole.SYSTEM, "hold music"),
            )
        )

        assert transcript.turn_count == 3
        # System lines are not a participant, and must not be scored as the agent.
        assert transcript.speaker_count == 2

    def test_selects_turns_by_role(self) -> None:
        transcript = Transcript((Turn(0, AGENT, "a"), Turn(1, MEMBER, "b"), Turn(2, AGENT, "c")))

        assert len(transcript.turns_for(AGENT)) == 2


class TestScoreMarker:
    def test_a_marker_without_a_quote_cannot_exist(self) -> None:
        # Evidence is mandatory by construction: this is what makes every point
        # of deduction traceable.
        with pytest.raises(ValidationError, match="must quote the evidence"):
            ScoreMarker(Polarity.NEGATIVE, "empathy", "was curt", 0, "  ")

    def test_requires_a_dimension_and_a_description(self) -> None:
        with pytest.raises(ValidationError, match="must name a rubric dimension"):
            ScoreMarker(Polarity.NEGATIVE, " ", "was curt", 0, "quote")
        with pytest.raises(ValidationError, match="must describe what was observed"):
            ScoreMarker(Polarity.NEGATIVE, "empathy", " ", 0, "quote")

    def test_requires_a_valid_evidence_turn(self) -> None:
        with pytest.raises(ValidationError, match="must be an integer"):
            ScoreMarker(Polarity.NEGATIVE, "empathy", "was curt", True, "quote")
        with pytest.raises(ValidationError, match="must be non-negative"):
            ScoreMarker(Polarity.NEGATIVE, "empathy", "was curt", -1, "quote")

    def test_exposes_its_polarity(self) -> None:
        assert ScoreMarker(Polarity.POSITIVE, "empathy", "kind", 0, "q").is_positive


class TestBrokerSignal:
    def test_an_attribution_without_evidence_cannot_be_stored(self) -> None:
        # This record names a real person. An unevidenced claim must be
        # impossible to construct, not merely discouraged.
        with pytest.raises(ValidationError, match="must quote the sentence"):
            BrokerSignal(
                broker_name="Marcus Trent",
                polarity=Polarity.NEGATIVE,
                basis=AttributionBasis.NAMED_IN_CALL,
                issue="Told member no prior authorization was required",
                evidence_turn_seq=4,
                quote="",
            )

    def test_a_valid_attribution_records_its_basis(self) -> None:
        signal = BrokerSignal(
            broker_name="Marcus Trent",
            polarity=Polarity.NEGATIVE,
            basis=AttributionBasis.NAMED_IN_CALL,
            issue="Told member no prior authorization was required",
            evidence_turn_seq=4,
            quote="My broker, Marcus Trent, told me I didn't need one.",
        )

        assert signal.basis is AttributionBasis.NAMED_IN_CALL
        assert signal.is_negative

    def test_requires_a_broker_name_and_an_issue(self) -> None:
        with pytest.raises(ValidationError, match="must name the broker"):
            BrokerSignal(" ", Polarity.NEGATIVE, AttributionBasis.NAMED_IN_CALL, "x", 0, "q")
        with pytest.raises(ValidationError, match="must describe the issue"):
            BrokerSignal("Trent", Polarity.NEGATIVE, AttributionBasis.NAMED_IN_CALL, " ", 0, "q")

    def test_requires_a_valid_evidence_turn(self) -> None:
        with pytest.raises(ValidationError, match="must be an integer"):
            BrokerSignal(
                "Trent",
                Polarity.NEGATIVE,
                AttributionBasis.BROKER_OF_RECORD,
                "x",
                True,
                "q",
            )
        with pytest.raises(ValidationError, match="must be non-negative"):
            BrokerSignal(
                "Trent", Polarity.NEGATIVE, AttributionBasis.BROKER_OF_RECORD, "x", -2, "q"
            )


class TestL4Signal:
    def test_carries_its_owner(self) -> None:
        category = L4Category(
            "compliance_risk",
            "Compliance & Risk",
            Owner("compliance", "Compliance"),
            Severity.CRITICAL,
        )
        signal = L4Signal(category=category, severity=Severity.CRITICAL, narrative="Cost steering.")

        assert signal.owner_name == "Compliance"

    def test_requires_a_narrative(self) -> None:
        category = L4Category("x", "X", Owner("o", "O"), Severity.LOW)
        with pytest.raises(ValidationError, match="must explain what was found"):
            L4Signal(category=category, severity=Severity.LOW, narrative=" ")


class TestAssistEvent:
    def test_a_rule_that_should_have_fired_is_a_finding(self) -> None:
        # Call #89's L5 panel presents the absence as the finding, so "should
        # have fired" is a state rather than an empty list.
        event = AssistEvent(
            outcome=AssistOutcome.SHOULD_HAVE_FIRED,
            trigger="symptom keywords with member age 68",
            recommendation="Mandatory nurse line transfer; suppress cost comparison.",
            severity=Severity.CRITICAL,
            at_turn_seq=5,
            timestamp_label="2:30",
        )

        assert event.is_gap

    def test_a_fired_rule_is_not_a_gap(self) -> None:
        event = AssistEvent(
            outcome=AssistOutcome.FIRED,
            trigger="CPT lookup",
            recommendation="Surfaced the document checklist.",
            severity=Severity.LOW,
        )

        assert not event.is_gap

    def test_requires_a_trigger_and_a_recommendation(self) -> None:
        with pytest.raises(ValidationError, match="must name the trigger"):
            AssistEvent(AssistOutcome.FIRED, " ", "do something", Severity.LOW)
        with pytest.raises(ValidationError, match="must state what should have happened"):
            AssistEvent(AssistOutcome.FIRED, "trigger", " ", Severity.LOW)

    def test_rejects_an_invalid_turn_reference(self) -> None:
        with pytest.raises(ValidationError, match="non-negative integer"):
            AssistEvent(AssistOutcome.FIRED, "t", "r", Severity.LOW, at_turn_seq=-1)
