"""A marker only scores if its evidence is real (plan §5.1 step 2)."""

from __future__ import annotations

from domain.entities.transcript import Transcript
from domain.entities.turn import Turn
from domain.scoring.marker_validation import (
    MarkerValidator,
    RejectionReason,
    accepted_markers,
)
from domain.value_objects.speaker import SpeakerRole
from tests.support.rubric import dimension, marker, rubric

TRANSCRIPT = Transcript(
    (
        Turn(0, SpeakerRole.AGENT, "ER copay is $250, waived if you're admitted."),
        Turn(1, SpeakerRole.MEMBER, "I've had this pressure in my chest since last night."),
    )
)
RUBRIC = rubric(dimension("empathy"), dimension("accuracy"))


def test_a_marker_with_a_real_quote_is_accepted() -> None:
    result = MarkerValidator(RUBRIC, TRANSCRIPT).validate(
        [marker("empathy", seq=1, quote="pressure in my chest")]
    )

    assert len(result.accepted) == 1
    assert not result.has_rejections


def test_an_unknown_dimension_is_rejected() -> None:
    result = MarkerValidator(RUBRIC, TRANSCRIPT).validate(
        [marker("invented_dimension", seq=0, quote="ER copay is $250")]
    )

    assert result.accepted == ()
    assert result.rejected[0].reason is RejectionReason.UNKNOWN_DIMENSION
    assert "not in the rubric" in result.rejected[0].explanation


def test_a_marker_citing_a_turn_that_does_not_exist_is_rejected() -> None:
    result = MarkerValidator(RUBRIC, TRANSCRIPT).validate(
        [marker("empathy", seq=99, quote="anything")]
    )

    assert result.rejected[0].reason is RejectionReason.MISSING_TURN
    assert "no turn 99" in result.rejected[0].explanation


def test_an_invented_quote_is_rejected() -> None:
    # The heart of the guarantee: a model cannot deduct points for a sentence
    # nobody said.
    result = MarkerValidator(RUBRIC, TRANSCRIPT).validate(
        [marker("empathy", seq=1, quote="I am having a heart attack")]
    )

    assert result.rejected[0].reason is RejectionReason.QUOTE_NOT_IN_TURN
    assert "does not appear in turn 1" in result.rejected[0].explanation


def test_a_quote_attributed_to_the_wrong_turn_is_rejected() -> None:
    # The words were said, but not in the turn cited. Evidence must point at the
    # right place or the transcript highlighting would be wrong.
    result = MarkerValidator(RUBRIC, TRANSCRIPT).validate(
        [marker("empathy", seq=0, quote="pressure in my chest")]
    )

    assert result.rejected[0].reason is RejectionReason.QUOTE_NOT_IN_TURN


def test_valid_and_invalid_markers_are_separated_not_all_or_nothing() -> None:
    result = MarkerValidator(RUBRIC, TRANSCRIPT).validate(
        [
            marker("empathy", seq=1, quote="pressure in my chest"),
            marker("empathy", seq=1, quote="never said this"),
            marker("accuracy", seq=0, quote="ER copay is $250"),
        ]
    )

    assert len(result.accepted) == 2
    assert len(result.rejected) == 1


def test_the_rejection_summary_lists_every_problem_for_the_log() -> None:
    result = MarkerValidator(RUBRIC, TRANSCRIPT).validate(
        [
            marker("nope", seq=0, quote="ER copay is $250"),
            marker("empathy", seq=42, quote="x"),
        ]
    )

    summary = result.rejection_summary
    assert "not in the rubric" in summary
    assert "no turn 42" in summary


def test_the_convenience_wrapper_behaves_the_same() -> None:
    markers = [marker("empathy", seq=1, quote="pressure in my chest")]

    assert accepted_markers(RUBRIC, TRANSCRIPT, markers).accepted == tuple(markers)
