"""Value objects refuse to hold invalid state, so mistakes fail where they happen."""

from __future__ import annotations

import pytest

from domain.errors import ValidationError
from domain.value_objects.category import Category
from domain.value_objects.polarity import Polarity
from domain.value_objects.resolution import Resolution
from domain.value_objects.score import MAX_SCORE, MIN_SCORE, Score, ScoreStatus
from domain.value_objects.sentiment_arc import SentimentArc
from domain.value_objects.severity import Severity
from domain.value_objects.tier import Tier, TierThresholds


class TestScore:
    @pytest.mark.parametrize("value", [MIN_SCORE, 42, MAX_SCORE])
    def test_accepts_values_in_range(self, value: int) -> None:
        assert Score(value).value == value

    @pytest.mark.parametrize("value", [-1, 101, 1000])
    def test_rejects_values_out_of_range(self, value: int) -> None:
        with pytest.raises(ValidationError, match="between 0 and 100"):
            Score(value)

    def test_rejects_a_non_integer(self) -> None:
        with pytest.raises(ValidationError, match="whole number"):
            Score(87.5)  # type: ignore[arg-type]

    def test_rejects_a_boolean_masquerading_as_an_integer(self) -> None:
        # bool subclasses int, so mypy accepts True here and the runtime guard
        # is the only thing standing between it and a score of 1.
        with pytest.raises(ValidationError, match="whole number"):
            Score(True)

    @pytest.mark.parametrize(
        ("raw", "expected"), [(-20, 0), (0, 0), (57, 57), (100, 100), (140, 100)]
    )
    def test_clamped_brings_a_raw_total_into_range(self, raw: int, expected: int) -> None:
        assert Score.clamped(raw).value == expected

    def test_scores_compare_and_render_by_value(self) -> None:
        assert Score(90) > Score(40)
        assert str(Score(90)) == "90"


class TestTierThresholds:
    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (100, Tier.GOOD),
            (86, Tier.GOOD),
            (85, Tier.AVERAGE),
            (60, Tier.AVERAGE),
            (59, Tier.POOR),
            (0, Tier.POOR),
        ],
    )
    def test_boundaries_are_inclusive_lower_bounds(self, score: int, expected: Tier) -> None:
        assert TierThresholds(good=86, average=60).tier_for(Score(score)) is expected

    @pytest.mark.parametrize(
        ("good", "average"),
        [(60, 86), (86, 86), (86, 0), (101, 60)],
    )
    def test_rejects_incoherent_thresholds(self, good: int, average: int) -> None:
        with pytest.raises(ValidationError, match="Tier thresholds"):
            TierThresholds(good=good, average=average)


class TestResolution:
    def test_only_a_full_resolution_counts_toward_first_contact_resolution(self) -> None:
        # Counting partial resolutions would inflate FCR against the industry
        # benchmark the dashboard compares it with.
        assert Resolution.RESOLVED.is_first_contact_resolution
        assert not Resolution.PARTIALLY_RESOLVED.is_first_contact_resolution
        assert not Resolution.ESCALATED.is_first_contact_resolution
        assert not Resolution.UNRESOLVED.is_first_contact_resolution

    def test_anything_short_of_resolved_needs_follow_up(self) -> None:
        assert not Resolution.RESOLVED.needs_follow_up
        assert Resolution.PARTIALLY_RESOLVED.needs_follow_up

    def test_values_match_the_corpus_index_vocabulary(self) -> None:
        assert Resolution.PARTIALLY_RESOLVED.value == "PARTIALLY RESOLVED"


class TestSeverity:
    def test_severities_are_ordered_so_findings_can_be_ranked(self) -> None:
        assert Severity.LOW < Severity.MEDIUM < Severity.HIGH < Severity.CRITICAL
        assert max([Severity.MEDIUM, Severity.CRITICAL, Severity.LOW]) is Severity.CRITICAL

    def test_sorting_uses_rank_not_alphabet(self) -> None:
        # Severity inherits str, whose comparisons would sort MEDIUM above
        # CRITICAL. All four operators are overridden for exactly this reason.
        assert sorted([Severity.CRITICAL, Severity.LOW, Severity.HIGH, Severity.MEDIUM]) == [
            Severity.LOW,
            Severity.MEDIUM,
            Severity.HIGH,
            Severity.CRITICAL,
        ]

    def test_the_other_operators_agree_with_rank(self) -> None:
        assert Severity.HIGH <= Severity.HIGH
        assert Severity.HIGH >= Severity.MEDIUM
        assert not Severity.LOW > Severity.CRITICAL

    def test_comparison_with_another_type_is_not_claimed(self) -> None:
        assert Severity.LOW.__lt__("HIGH") is NotImplemented
        assert Severity.LOW.__le__("HIGH") is NotImplemented
        assert Severity.LOW.__gt__("HIGH") is NotImplemented
        assert Severity.LOW.__ge__("HIGH") is NotImplemented


class TestSentimentArc:
    def test_renders_as_the_corpus_writes_it(self) -> None:
        assert str(SentimentArc("WORRIED", "DISMISSED")) == "WORRIED → DISMISSED"

    def test_an_arc_that_does_not_move_is_flagged(self) -> None:
        assert not SentimentArc("NEUTRAL", "NEUTRAL").improved
        assert SentimentArc("ANXIOUS", "REASSURED").improved

    @pytest.mark.parametrize(("start", "end"), [("", "X"), ("X", "  ")])
    def test_rejects_an_empty_end(self, start: str, end: str) -> None:
        with pytest.raises(ValidationError, match="must not be empty"):
            SentimentArc(start, end)


class TestCategory:
    def test_rejects_an_empty_code_or_label(self) -> None:
        with pytest.raises(ValidationError, match="code must not be empty"):
            Category(code="  ", label="Coverage")
        with pytest.raises(ValidationError, match="must have a label"):
            Category(code="coverage", label="")


def test_polarity_and_score_status_expose_readable_values() -> None:
    assert Polarity.POSITIVE.is_positive
    assert not Polarity.NEGATIVE.is_positive
    assert ScoreStatus.PROVISIONAL.value == "provisional"
