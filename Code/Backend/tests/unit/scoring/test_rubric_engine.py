"""The scoring engine is the component leadership's trust rests on (DEC-03)."""

from __future__ import annotations

import pytest

from domain.errors import NotFoundError
from domain.scoring.rubric_engine import RubricEngine
from domain.value_objects.polarity import Polarity
from domain.value_objects.score import ScoreStatus
from domain.value_objects.tier import Tier
from tests.support.rubric import CLINICAL_GATE, dimension, marker, rubric

POSITIVE = Polarity.POSITIVE


def test_a_call_with_no_markers_scores_the_base() -> None:
    result = RubricEngine(rubric()).score([])

    assert result.score.value == 100
    assert result.tier is Tier.GOOD
    assert result.status is ScoreStatus.CONFIRMED
    assert result.applied == ()


def test_each_negative_marker_subtracts_its_dimension_weight() -> None:
    engine = RubricEngine(rubric(dimension("empathy", negative=8, max_negative=24)))

    result = engine.score([marker("empathy"), marker("empathy")])

    assert result.score.value == 84
    assert result.total_negative == 16


def test_negative_markers_are_capped_per_dimension() -> None:
    # Five criticisms on one axis must not sink a call on that axis alone.
    engine = RubricEngine(rubric(dimension("empathy", negative=8, max_negative=24)))

    result = engine.score([marker("empathy") for _ in range(5)])

    assert result.dimension_totals["empathy"].negative == 24
    assert result.dimension_totals["empathy"].negative_before_cap == 40
    assert result.dimension_totals["empathy"].negative_was_capped
    assert result.score.value == 76


def test_positive_markers_offset_penalties() -> None:
    engine = RubricEngine(
        rubric(
            dimension("empathy", positive=3, max_positive=9),
            dimension("accuracy", negative=12, max_negative=36),
        )
    )

    result = engine.score(
        [
            marker("accuracy"),
            marker("empathy", polarity=POSITIVE),
            marker("empathy", polarity=POSITIVE),
        ]
    )

    assert result.total_negative == 12
    assert result.total_positive == 6
    assert result.applied_offset == 6
    assert result.score.value == 94


def test_positive_markers_cannot_lift_a_call_above_the_base_score() -> None:
    # 100 means "nothing went wrong". Praise cannot make a call better than that.
    engine = RubricEngine(rubric(dimension("empathy", positive=3, max_positive=9)))

    result = engine.score([marker("empathy", polarity=POSITIVE) for _ in range(3)])

    assert result.score.value == 100
    assert result.applied_offset == 0


def test_positive_offset_is_capped_so_praise_cannot_erase_a_serious_failure() -> None:
    engine = RubricEngine(
        rubric(
            dimension("empathy", positive=3, max_positive=9),
            dimension("compliance", negative=45, max_negative=45),
            max_positive_offset=5,
        )
    )

    result = engine.score(
        [marker("compliance")] + [marker("empathy", polarity=POSITIVE) for _ in range(3)]
    )

    assert result.total_positive == 9
    assert result.applied_offset == 5  # not 9
    assert result.score.value == 60


def test_positive_markers_are_capped_per_dimension() -> None:
    engine = RubricEngine(
        rubric(
            dimension("empathy", positive=3, max_positive=6),
            dimension("accuracy", negative=12, max_negative=36),
        )
    )

    result = engine.score(
        [marker("accuracy")] + [marker("empathy", polarity=POSITIVE) for _ in range(4)]
    )

    assert result.dimension_totals["empathy"].positive == 6
    assert result.dimension_totals["empathy"].positive_before_cap == 12
    assert result.dimension_totals["empathy"].positive_was_capped


def test_the_score_is_clamped_at_zero() -> None:
    engine = RubricEngine(
        rubric(
            dimension("a", negative=40, max_negative=40),
            dimension("b", negative=40, max_negative=40),
            dimension("c", negative=40, max_negative=40),
        )
    )

    result = engine.score([marker("a"), marker("b"), marker("c")])

    assert result.score.value == 0
    assert result.tier is Tier.POOR


@pytest.mark.parametrize(
    ("negative", "expected_tier"),
    [(0, Tier.GOOD), (14, Tier.GOOD), (15, Tier.AVERAGE), (40, Tier.AVERAGE), (41, Tier.POOR)],
)
def test_tier_boundaries(negative: int, expected_tier: Tier) -> None:
    engine = RubricEngine(rubric(dimension("a", negative=negative, max_negative=100)))
    markers = [marker("a")] if negative else []

    assert engine.score(markers).tier is expected_tier


def test_every_marker_is_reported_with_the_points_it_contributed() -> None:
    # Traceability: a reviewer must be able to see what each observation cost.
    engine = RubricEngine(
        rubric(
            dimension("empathy", positive=3, negative=8),
            dimension("accuracy", negative=12),
        )
    )

    result = engine.score([marker("accuracy"), marker("empathy", polarity=POSITIVE)])

    assert [applied.points for applied in result.applied] == [-12, 3]


def test_an_unknown_dimension_is_an_error_rather_than_a_silently_dropped_penalty() -> None:
    engine = RubricEngine(rubric(dimension("empathy")))

    with pytest.raises(NotFoundError, match="Unknown rubric dimension"):
        engine.score([marker("not_a_dimension")])


def test_scoring_is_deterministic_across_repeated_runs() -> None:
    engine = RubricEngine(rubric())
    markers = [marker("empathy"), marker("accuracy", polarity=POSITIVE), marker("empathy")]

    first = engine.score(markers)
    second = engine.score(markers)

    assert first.score == second.score
    assert first.status == second.status
    assert first.tier == second.tier


def test_the_engine_reports_the_rubric_it_is_scoring_against() -> None:
    # Provenance: a stored result must be traceable to the rubric version used.
    subject = rubric()

    assert RubricEngine(subject).rubric.version == subject.version


def test_net_penalty_is_the_deduction_actually_applied() -> None:
    engine = RubricEngine(
        rubric(
            dimension("empathy", positive=3, max_positive=9),
            dimension("accuracy", negative=12, max_negative=36),
        )
    )

    result = engine.score([marker("accuracy"), marker("empathy", polarity=POSITIVE)])

    assert result.total_negative == 12
    assert result.net_penalty == 9
    assert result.score.value == 100 - result.net_penalty


def test_marker_order_does_not_change_the_score() -> None:
    engine = RubricEngine(rubric())
    markers = [marker("empathy"), marker("accuracy"), marker("empathy", polarity=POSITIVE)]

    forward = engine.score(markers)
    backward = engine.score(list(reversed(markers)))

    assert forward.score == backward.score


class TestGates:
    def test_the_clinical_gate_suspends_the_score(self) -> None:
        engine = RubricEngine(rubric(gates=(CLINICAL_GATE,)))

        result = engine.score([marker("empathy")], signal_codes=["clinical_risk"])

        assert result.status is ScoreStatus.PROVISIONAL
        assert result.is_provisional
        assert result.triggered_gate_ids == ("clinical_urgency_unrecognised",)
        assert result.messages == ("Score withheld pending clinical review.",)

    def test_the_gate_does_not_fire_without_its_signal(self) -> None:
        engine = RubricEngine(rubric(gates=(CLINICAL_GATE,)))

        result = engine.score([marker("empathy")], signal_codes=["repeat_contact"])

        assert result.status is ScoreStatus.CONFIRMED
        assert result.triggered_gate_ids == ()

    def test_a_suspended_score_still_reports_its_number_and_tier(self) -> None:
        # The rubric figure is shown as provisional, not hidden: reviewers need
        # to know how bad the call looks while it awaits clinical sign-off.
        engine = RubricEngine(rubric(dimension("empathy", negative=8), gates=(CLINICAL_GATE,)))

        result = engine.score([marker("empathy")], signal_codes=["clinical_risk"])

        assert result.score.value == 92
        assert result.tier is Tier.GOOD
        assert result.is_provisional
