"""A rubric that is quietly wrong produces numbers that look plausible."""

from __future__ import annotations

import pytest

from domain.errors import NotFoundError, ValidationError
from domain.scoring.rubric import Dimension, Gate, GateCondition, GateEffect, Rubric
from domain.value_objects.tier import TierThresholds
from tests.support.rubric import CLINICAL_GATE, dimension, rubric


class TestDimension:
    def test_rejects_a_negative_magnitude(self) -> None:
        # Weights are magnitudes; the engine applies the sign. A negative value
        # here would invert the meaning of a marker.
        with pytest.raises(ValidationError, match="non-negative magnitude"):
            Dimension(
                "empathy", "Empathy", positive=3, negative=-8, max_positive=9, max_negative=24
            )

    def test_rejects_a_boolean_weight(self) -> None:
        with pytest.raises(ValidationError, match="non-negative magnitude"):
            Dimension(
                "empathy",
                "Empathy",
                positive=True,
                negative=8,
                max_positive=9,
                max_negative=24,
            )

    def test_rejects_a_cap_below_a_single_marker(self) -> None:
        # Otherwise the first marker would already exceed the cap, and the weight
        # would silently never apply in full.
        with pytest.raises(ValidationError, match=r"max_negative .* is below"):
            Dimension(
                "empathy", "Empathy", positive=3, negative=20, max_positive=9, max_negative=10
            )
        with pytest.raises(ValidationError, match=r"max_positive .* is below"):
            Dimension(
                "empathy", "Empathy", positive=10, negative=8, max_positive=5, max_negative=24
            )

    def test_rejects_an_empty_code(self) -> None:
        with pytest.raises(ValidationError, match="code must not be empty"):
            Dimension(" ", "Empathy", positive=1, negative=1, max_positive=1, max_negative=1)


class TestGate:
    def test_score_below_requires_a_numeric_argument(self) -> None:
        with pytest.raises(ValidationError, match="must be a whole number"):
            Gate(
                id="low",
                condition=GateCondition.SCORE_BELOW,
                argument="quite low",
                effect=GateEffect.SUSPEND_SCORE,
                message="review",
            )

    def test_a_numeric_argument_is_exposed_as_a_threshold(self) -> None:
        gate = Gate(
            id="low",
            condition=GateCondition.SCORE_BELOW,
            argument="40",
            effect=GateEffect.SUSPEND_SCORE,
            message="review",
        )

        assert gate.threshold == 40

    def test_requires_an_id_argument_and_message(self) -> None:
        with pytest.raises(ValidationError, match="Gate id"):
            Gate(" ", GateCondition.SIGNAL_PRESENT, "x", GateEffect.SUSPEND_SCORE, "m")
        with pytest.raises(ValidationError, match="must specify an argument"):
            Gate("g", GateCondition.SIGNAL_PRESENT, " ", GateEffect.SUSPEND_SCORE, "m")
        with pytest.raises(ValidationError, match="must carry a message"):
            Gate("g", GateCondition.SIGNAL_PRESENT, "x", GateEffect.SUSPEND_SCORE, " ")


class TestRubric:
    def test_rejects_an_out_of_range_base_score(self) -> None:
        with pytest.raises(ValidationError, match="base_score"):
            rubric(base_score=140)

    def test_rejects_a_negative_positive_offset(self) -> None:
        with pytest.raises(ValidationError, match="max_positive_offset"):
            rubric(max_positive_offset=-1)

    def test_requires_at_least_one_dimension(self) -> None:
        with pytest.raises(ValidationError, match="at least one dimension"):
            Rubric(
                version="1.0.0",
                base_score=100,
                max_positive_offset=15,
                dimensions={},
                tiers=TierThresholds(good=86, average=60),
                min_calls_for_tier_rating=5,
            )

    def test_requires_a_version(self) -> None:
        with pytest.raises(ValidationError, match="must declare a version"):
            Rubric(
                version="  ",
                base_score=100,
                max_positive_offset=15,
                dimensions={"empathy": dimension("empathy")},
                tiers=TierThresholds(good=86, average=60),
                min_calls_for_tier_rating=5,
            )

    def test_rejects_a_dimension_indexed_under_the_wrong_code(self) -> None:
        # A mismatch here would mean markers naming one code are scored with
        # another's weights.
        with pytest.raises(ValidationError, match="indexed as"):
            Rubric(
                version="1.0.0",
                base_score=100,
                max_positive_offset=15,
                dimensions={"empathy": dimension("accuracy")},
                tiers=TierThresholds(good=86, average=60),
                min_calls_for_tier_rating=5,
            )

    def test_rejects_an_unusable_significance_threshold(self) -> None:
        with pytest.raises(ValidationError, match="min_calls_for_tier_rating"):
            rubric(min_calls_for_tier_rating=0)

    def test_rejects_duplicate_gate_ids(self) -> None:
        with pytest.raises(ValidationError, match="Duplicate gate id"):
            rubric(gates=(CLINICAL_GATE, CLINICAL_GATE))

    def test_looks_up_dimensions_and_names_the_alternatives(self) -> None:
        subject = rubric(dimension("empathy"), dimension("accuracy"))

        assert subject.dimension("empathy").code == "empathy"
        assert subject.has_dimension("accuracy")
        assert not subject.has_dimension("nope")

        with pytest.raises(NotFoundError) as exc_info:
            subject.dimension("nope")
        assert exc_info.value.detail is not None
        assert "empathy" in exc_info.value.detail
