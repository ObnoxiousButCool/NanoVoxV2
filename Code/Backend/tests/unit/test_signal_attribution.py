"""Which team owns a call whose findings belong to several."""

from __future__ import annotations

from domain.aggregation.signal_attribution import L4Finding, primary_category_by_call
from domain.taxonomy import L4Category, Owner
from domain.value_objects.severity import Severity


def category(code: str, default: Severity) -> L4Category:
    return L4Category(
        code=code,
        label=code.replace("_", " ").title(),
        owner=Owner(code=f"{code}_team", name=f"{code} team"),
        default_severity=default,
    )


# Declaration order matters to the last tie-break, so it is fixed here.
CATEGORIES = (
    category("process", Severity.HIGH),
    category("compliance", Severity.CRITICAL),
    category("comms", Severity.MEDIUM),
)


class TestPrimaryCategory:
    def test_a_call_with_one_finding_is_attributed_to_it(self) -> None:
        findings = (L4Finding(1, "process", Severity.LOW),)

        assert primary_category_by_call(findings, CATEGORIES) == {1: "process"}

    def test_the_more_serious_finding_on_the_call_wins(self) -> None:
        # The judgement a human makes reading the two side by side: a HIGH
        # compliance problem outranks a MEDIUM process one on the same call.
        findings = (
            L4Finding(1, "process", Severity.MEDIUM),
            L4Finding(1, "compliance", Severity.HIGH),
        )

        assert primary_category_by_call(findings, CATEGORIES) == {1: "compliance"}

    def test_order_of_findings_does_not_change_the_answer(self) -> None:
        # Same two findings, opposite row order. SQL makes no promise about
        # which comes back first, so the result must not depend on it.
        one = (
            L4Finding(1, "compliance", Severity.HIGH),
            L4Finding(1, "process", Severity.MEDIUM),
        )
        other = tuple(reversed(one))

        assert primary_category_by_call(one, CATEGORIES) == primary_category_by_call(
            other, CATEGORIES
        )

    def test_equal_severities_defer_to_the_configured_default(self) -> None:
        # Both scored HIGH on this call, so the standing policy in taxonomy.yaml
        # decides: compliance's default is CRITICAL, process's is HIGH.
        findings = (
            L4Finding(1, "process", Severity.HIGH),
            L4Finding(1, "compliance", Severity.HIGH),
        )

        assert primary_category_by_call(findings, CATEGORIES) == {1: "compliance"}

    def test_a_full_tie_falls_back_to_declaration_order(self) -> None:
        # "process" and "tied" share a default severity, so only the taxonomy's
        # order separates them. Something has to, or the chart would move between
        # runs with no change in the data.
        categories = (*CATEGORIES, category("tied", Severity.HIGH))
        findings = (
            L4Finding(1, "tied", Severity.MEDIUM),
            L4Finding(1, "process", Severity.MEDIUM),
        )

        assert primary_category_by_call(findings, categories) == {1: "process"}

    def test_each_call_is_attributed_independently(self) -> None:
        findings = (
            L4Finding(1, "process", Severity.HIGH),
            L4Finding(2, "comms", Severity.LOW),
            L4Finding(2, "compliance", Severity.CRITICAL),
        )

        assert primary_category_by_call(findings, CATEGORIES) == {
            1: "process",
            2: "compliance",
        }

    def test_a_finding_in_an_undefined_category_is_ignored(self) -> None:
        # An undefined category has no owner, so there is nobody to attribute
        # the call to. Ignored rather than guessed at.
        findings = (
            L4Finding(1, "retired_category", Severity.CRITICAL),
            L4Finding(1, "comms", Severity.LOW),
        )

        assert primary_category_by_call(findings, CATEGORIES) == {1: "comms"}

    def test_a_call_with_only_undefined_findings_is_left_out(self) -> None:
        findings = (L4Finding(1, "retired_category", Severity.CRITICAL),)

        assert primary_category_by_call(findings, CATEGORIES) == {}

    def test_no_findings_attributes_nothing(self) -> None:
        assert primary_category_by_call((), CATEGORIES) == {}
