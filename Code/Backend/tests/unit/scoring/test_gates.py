"""Gate conditions are evaluated independently of the arithmetic."""

from __future__ import annotations

from domain.scoring.gates import gate_applies, triggered_gates
from domain.scoring.rubric import Gate, GateCondition, GateEffect
from domain.value_objects.score import Score
from tests.support.rubric import CLINICAL_GATE

LOW_SCORE_GATE = Gate(
    id="very_low_score",
    condition=GateCondition.SCORE_BELOW,
    argument="40",
    effect=GateEffect.SUSPEND_SCORE,
    message="Score withheld pending supervisor review.",
)


class TestSignalPresent:
    def test_fires_when_the_signal_is_raised(self) -> None:
        assert gate_applies(CLINICAL_GATE, score=Score(80), signal_codes=["clinical_risk"])

    def test_does_not_fire_on_an_unrelated_signal(self) -> None:
        assert not gate_applies(CLINICAL_GATE, score=Score(80), signal_codes=["exemplar"])

    def test_does_not_fire_when_no_signals_were_raised(self) -> None:
        assert not gate_applies(CLINICAL_GATE, score=Score(10), signal_codes=[])


class TestScoreBelow:
    def test_fires_below_the_threshold(self) -> None:
        assert gate_applies(LOW_SCORE_GATE, score=Score(39), signal_codes=[])

    def test_does_not_fire_at_the_threshold(self) -> None:
        # The threshold is exclusive: "below 40" must not include 40.
        assert not gate_applies(LOW_SCORE_GATE, score=Score(40), signal_codes=[])


def test_every_matching_gate_is_returned_in_declaration_order() -> None:
    fired = triggered_gates(
        (CLINICAL_GATE, LOW_SCORE_GATE), score=Score(20), signal_codes=["clinical_risk"]
    )

    assert [gate.id for gate in fired] == ["clinical_urgency_unrecognised", "very_low_score"]


def test_no_gates_fire_on_a_clean_call() -> None:
    assert triggered_gates((CLINICAL_GATE, LOW_SCORE_GATE), score=Score(95), signal_codes=[]) == ()
