"""Statistics and attention rules, tested without a database."""

from __future__ import annotations

import pytest

from domain.aggregation.attention import (
    AttentionInputs,
    AttentionRule,
    GroupCount,
    RuleKind,
    evaluate_rules,
)
from domain.aggregation.statistics import build_histogram, mean, median, percentage
from domain.errors import ValidationError
from domain.value_objects.severity import Severity

EDGES = (0, 20, 40, 60, 80, 90)


def rule(**overrides: object) -> AttentionRule:
    defaults: dict[str, object] = {
        "id": "test_rule",
        "kind": RuleKind.SIGNAL_PRESENT,
        "title": "Something is wrong with {subject}",
        "minimum": 2,
        "severity": Severity.HIGH,
        "owner": "Operations",
        "why": "{count} of {total} calls affected.",
    }
    defaults.update(overrides)
    return AttentionRule(**defaults)  # type: ignore[arg-type]


class TestStatistics:
    @pytest.mark.parametrize(
        ("values", "expected"), [((), 0.0), ((5,), 5.0), ((1, 2, 3), 2.0), ((1, 2, 3, 4), 2.5)]
    )
    def test_median(self, values: tuple[int, ...], expected: float) -> None:
        assert median(values) == expected

    def test_median_and_mean_diverge_on_a_bimodal_set(self) -> None:
        # The corpus's defining property: the mean sits in a gap where no call
        # falls, which is why both are reported.
        bimodal = (20, 22, 25, 90, 92, 95, 96)

        assert median(bimodal) == 90
        assert mean(bimodal) == 62.9

    @pytest.mark.parametrize(
        ("part", "whole", "expected"), [(0, 10, 0.0), (1, 3, 33.3), (5, 0, 0.0)]
    )
    def test_percentage(self, part: int, whole: int, expected: float) -> None:
        assert percentage(part, whole) == expected


class TestHistogram:
    def test_values_land_in_the_right_bins(self) -> None:
        histogram = build_histogram((0, 19, 20, 59, 60, 89, 90, 100), EDGES, coaching_threshold=60)
        counts = {item.label: item.count for item in histogram.bins}

        assert counts["0-20"] == 2  # 0, 19
        assert counts["20-40"] == 1  # 20
        assert counts["40-60"] == 1  # 59
        assert counts["60-80"] == 1  # 60
        assert counts["80-90"] == 1  # 89
        assert counts["90-100"] == 2  # 90, 100

    def test_the_top_bin_includes_a_perfect_score(self) -> None:
        # A call scoring 100 must appear somewhere.
        assert build_histogram((100,), EDGES, coaching_threshold=60).total == 1

    def test_bins_entirely_below_the_threshold_are_marked(self) -> None:
        histogram = build_histogram((), EDGES, coaching_threshold=60)
        marked = {item.label for item in histogram.bins if item.is_below_threshold}

        assert marked == {"0-20", "20-40", "40-60"}

    def test_a_bin_straddling_the_threshold_is_not_marked(self) -> None:
        # Marking it would overstate how many calls need coaching.
        histogram = build_histogram((), (0, 50, 70), coaching_threshold=60)
        straddling = next(item for item in histogram.bins if item.lower == 50)

        assert not straddling.is_below_threshold

    def test_peak_is_the_tallest_bar(self) -> None:
        histogram = build_histogram((90, 91, 92, 10), EDGES, coaching_threshold=60)

        assert histogram.peak == 3

    @pytest.mark.parametrize("edges", [(50,), (0, 40, 20), (0, 40, 40), (-1, 50), (0, 101)])
    def test_invalid_edges_are_rejected(self, edges: tuple[int, ...]) -> None:
        with pytest.raises(ValidationError):
            build_histogram((), edges, coaching_threshold=60)


class TestAttentionRules:
    def test_a_rule_fires_at_its_threshold(self) -> None:
        inputs = AttentionInputs(
            total_calls=10,
            signal_counts=(GroupCount(key="a", label="Signal A", count=2),),
        )

        items = evaluate_rules([rule(minimum=2)], inputs)

        assert len(items) == 1
        assert items[0].count == 2

    def test_a_rule_below_its_threshold_produces_nothing(self) -> None:
        inputs = AttentionInputs(
            total_calls=10, signal_counts=(GroupCount(key="a", label="A", count=1),)
        )

        assert evaluate_rules([rule(minimum=2)], inputs) == ()

    def test_a_rule_watching_one_signal_ignores_the_others(self) -> None:
        # The defect this guards: without applies_to, a rule written for clinical
        # risk fired on an unrelated signal and headlined it as a clinical
        # escalation failure.
        inputs = AttentionInputs(
            total_calls=10,
            signal_counts=(
                GroupCount(key="clinical_risk", label="Clinical risk", count=1),
                GroupCount(key="repeat_contact", label="Repeat contact", count=9),
            ),
        )

        items = evaluate_rules(
            [rule(applies_to="clinical_risk", minimum=1, title="Clinical urgency missed")], inputs
        )

        assert len(items) == 1
        assert items[0].subject == "Clinical risk"
        assert items[0].count == 1

    def test_a_rule_without_a_subject_watches_every_group(self) -> None:
        # Correct for the volume rules, which are about any category crossing a
        # threshold rather than one named one.
        inputs = AttentionInputs(
            total_calls=10,
            l4_category_counts=(
                GroupCount(key="a", label="A", count=5),
                GroupCount(key="b", label="B", count=4),
            ),
        )

        items = evaluate_rules([rule(kind=RuleKind.L4_CATEGORY_VOLUME, minimum=3)], inputs)

        assert {item.subject for item in items} == {"A", "B"}

    def test_unresolved_rules_count_unresolved_not_total(self) -> None:
        inputs = AttentionInputs(
            total_calls=20,
            category_unresolved_counts=(GroupCount(key="a", label="A", count=10, unresolved=2),),
        )

        assert evaluate_rules([rule(kind=RuleKind.UNRESOLVED_IN_CATEGORY, minimum=5)], inputs) == ()
        fired = evaluate_rules([rule(kind=RuleKind.UNRESOLVED_IN_CATEGORY, minimum=2)], inputs)
        assert fired[0].count == 2

    def test_items_are_ranked_by_severity_then_volume(self) -> None:
        inputs = AttentionInputs(
            total_calls=100,
            signal_counts=(
                GroupCount(key="small", label="Small", count=2),
                GroupCount(key="big", label="Big", count=50),
            ),
            l4_category_counts=(GroupCount(key="crit", label="Critical", count=1),),
        )

        items = evaluate_rules(
            [
                rule(id="high", minimum=1, severity=Severity.HIGH),
                rule(
                    id="critical",
                    kind=RuleKind.L4_CATEGORY_VOLUME,
                    minimum=1,
                    severity=Severity.CRITICAL,
                ),
            ],
            inputs,
        )

        assert items[0].subject == "Critical"  # severity beats volume
        assert items[1].subject == "Big"  # then the larger count
        assert items[2].subject == "Small"

    def test_narrative_placeholders_are_filled_from_counts(self) -> None:
        inputs = AttentionInputs(
            total_calls=40, signal_counts=(GroupCount(key="a", label="Alpha", count=7),)
        )

        item = evaluate_rules([rule(minimum=1)], inputs)[0]

        assert item.title == "Something is wrong with Alpha"
        assert item.why == "7 of 40 calls affected."

    def test_references_travel_with_the_item(self) -> None:
        # Every claim links back to the calls behind it.
        inputs = AttentionInputs(
            total_calls=5,
            signal_counts=(GroupCount(key="a", label="A", count=2, references=("C0001", "C0002")),),
        )

        assert evaluate_rules([rule(minimum=1)], inputs)[0].references == ("C0001", "C0002")

    def test_a_rule_without_an_owner_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must name an owner"):
            rule(owner="  ")

    def test_a_rule_with_an_unusable_threshold_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least 1"):
            rule(minimum=0)
