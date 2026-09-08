"""Signals have to prove what they claim."""

from __future__ import annotations

from domain.entities.transcript import Transcript
from domain.entities.turn import Turn
from domain.signal_evidence import RaisedSignal, SignalRejection, validate_signals
from domain.value_objects.speaker import SpeakerRole

KNOWN = ("clinical_risk", "compliance_disclosure_missing", "repeat_contact")

TRANSCRIPT = Transcript(
    turns=(
        Turn(seq=0, role=SpeakerRole.AGENT, text="Choice Administrators."),
        Turn(
            seq=1,
            role=SpeakerRole.MEMBER,
            text="I have been having chest pain since Tuesday and I ran out of my heart tablets.",
        ),
        Turn(seq=2, role=SpeakerRole.AGENT, text="Your copay is forty."),
    )
)


def signal(code: str = "clinical_risk", quote: str = "chest pain", turn: int = 1) -> RaisedSignal:
    return RaisedSignal(code=code, quote=quote, evidence_turn_seq=turn)


class TestEvidenceThatHolds:
    def test_a_quote_found_in_the_cited_turn_is_kept(self) -> None:
        result = validate_signals([signal()], TRANSCRIPT, KNOWN)

        assert result.accepted == ("clinical_risk",)
        assert not result.has_rejections

    def test_two_quotes_for_one_condition_are_one_condition(self) -> None:
        # The scoring gate asks only whether a code is present, so a second
        # piece of evidence must not become a second signal on the call.
        result = validate_signals(
            [signal(quote="chest pain"), signal(quote="ran out of my heart tablets")],
            TRANSCRIPT,
            KNOWN,
        )

        assert result.accepted == ("clinical_risk",)

    def test_codes_keep_the_order_they_were_raised_in(self) -> None:
        result = validate_signals(
            [
                signal(code="repeat_contact", quote="Choice Administrators", turn=0),
                signal(),
            ],
            TRANSCRIPT,
            KNOWN,
        )

        assert result.accepted == ("repeat_contact", "clinical_risk")


class TestEvidenceThatDoesNot:
    def test_a_quote_absent_from_the_turn_is_refused(self) -> None:
        # The failure that made this module necessary: a signal asserted about a
        # call whose transcript never said it.
        result = validate_signals([signal(quote="my prescription changed")], TRANSCRIPT, KNOWN)

        assert result.accepted == ()
        assert result.rejected[0].reason is SignalRejection.QUOTE_NOT_IN_TURN
        assert "quoted text absent from turn 1" in result.rejection_notes[0].lower()

    def test_a_quote_from_a_different_turn_is_refused(self) -> None:
        # The words exist in the call, just not where the signal says. Accepting
        # it would make the citation decorative.
        result = validate_signals([signal(turn=2)], TRANSCRIPT, KNOWN)

        assert result.accepted == ()
        assert result.rejected[0].reason is SignalRejection.QUOTE_NOT_IN_TURN

    def test_a_turn_that_does_not_exist_is_refused(self) -> None:
        result = validate_signals([signal(turn=99)], TRANSCRIPT, KNOWN)

        assert result.rejected[0].reason is SignalRejection.MISSING_TURN
        assert "does not exist" in result.rejection_notes[0]

    def test_a_missing_turn_index_is_refused_not_read_as_turn_zero(self) -> None:
        # -1 is what the caller passes when the field was absent. Defaulting to
        # zero would let an unevidenced signal match the greeting.
        result = validate_signals([signal(turn=-1)], TRANSCRIPT, KNOWN)

        assert result.rejected[0].reason is SignalRejection.MISSING_TURN

    def test_an_empty_quote_is_no_evidence_rather_than_a_match(self) -> None:
        # An empty string is "in" every turn. Read literally it would accept
        # every signal that cited nothing at all.
        result = validate_signals([signal(quote="   ")], TRANSCRIPT, KNOWN)

        assert result.accepted == ()
        assert result.rejected[0].reason is SignalRejection.NO_QUOTE
        assert "cited no evidence" in result.rejection_notes[0]

    def test_a_code_outside_the_taxonomy_is_refused(self) -> None:
        result = validate_signals([signal(code="invented_signal")], TRANSCRIPT, KNOWN)

        assert result.rejected[0].reason is SignalRejection.UNKNOWN_CODE
        assert "not in the taxonomy" in result.rejection_notes[0]

    def test_a_refused_signal_still_reports_the_others(self) -> None:
        # One bad claim must not discard a good one made beside it.
        result = validate_signals(
            [signal(quote="never said this"), signal(quote="ran out of my heart tablets")],
            TRANSCRIPT,
            KNOWN,
        )

        assert result.accepted == ("clinical_risk",)
        assert len(result.rejected) == 1


class TestNothingRaised:
    def test_no_signals_is_not_an_error(self) -> None:
        result = validate_signals([], TRANSCRIPT, KNOWN)

        assert result.accepted == ()
        assert not result.has_rejections
