"""Which members show signs of leaving.

The rule this module has to keep is honesty: it reports what was observed and
never invents a probability. Every test here is either about naming the right
signs, or about not claiming more than the evidence supports.
"""

from __future__ import annotations

from domain.aggregation.member_risk import (
    MemberCalls,
    RiskFactor,
    assess,
    members_at_risk,
)

THRESHOLD = 60


def member(member_id: str = "CHM0000001", **overrides: object) -> MemberCalls:
    defaults: dict[str, object] = {
        "member_id": member_id,
        "member_name": None,
        "call_count": 1,
        "total_minutes": 10,
        "resolved": 0,
        "unresolved": 0,
        "escalated": 0,
        "ended_unhappy": 0,
        "lowest_score": 90,
        "latest_reference": "C0001",
        "references": ("C0001",),
    }
    defaults.update(overrides)
    return MemberCalls(**defaults)  # type: ignore[arg-type]


class TestNamingTheSigns:
    def test_an_unresolved_call_is_a_sign(self) -> None:
        assessed = assess(member(unresolved=1), coaching_threshold=THRESHOLD)

        assert RiskFactor.UNRESOLVED in assessed.factors

    def test_ending_the_call_unhappy_is_a_sign(self) -> None:
        assessed = assess(member(ended_unhappy=1), coaching_threshold=THRESHOLD)

        assert RiskFactor.ENDED_UNHAPPY in assessed.factors

    def test_calling_twice_is_a_sign(self) -> None:
        # Effort: a second call about one problem has already cost the member
        # double what the first promised.
        assessed = assess(member(call_count=2), coaching_threshold=THRESHOLD)

        assert RiskFactor.REPEAT_CONTACT in assessed.factors

    def test_one_call_is_not_repeat_contact(self) -> None:
        assessed = assess(member(call_count=1), coaching_threshold=THRESHOLD)

        assert RiskFactor.REPEAT_CONTACT not in assessed.factors

    def test_a_score_below_the_coaching_threshold_is_a_sign(self) -> None:
        assessed = assess(member(lowest_score=THRESHOLD - 1), coaching_threshold=THRESHOLD)

        assert RiskFactor.LOW_SCORE in assessed.factors

    def test_the_threshold_itself_is_not_below_it(self) -> None:
        assessed = assess(member(lowest_score=THRESHOLD), coaching_threshold=THRESHOLD)

        assert RiskFactor.LOW_SCORE not in assessed.factors

    def test_the_threshold_comes_from_configuration(self) -> None:
        # What counts as poorly handled is a business judgement, not a constant.
        strict = assess(member(lowest_score=80), coaching_threshold=85)
        lenient = assess(member(lowest_score=80), coaching_threshold=60)

        assert RiskFactor.LOW_SCORE in strict.factors
        assert RiskFactor.LOW_SCORE not in lenient.factors

    def test_every_sign_is_reported_not_just_the_first(self) -> None:
        assessed = assess(
            member(call_count=3, unresolved=1, ended_unhappy=1, escalated=1, lowest_score=29),
            coaching_threshold=THRESHOLD,
        )

        assert len(assessed.factors) == 5

    def test_each_factor_carries_a_readable_label(self) -> None:
        # The card shows these words; an enum value would read as a code.
        for factor in RiskFactor:
            assert factor.label
            assert factor.label != factor.value


class TestTheQueue:
    def test_a_member_showing_nothing_is_left_off(self) -> None:
        # A work queue listing everybody is not a queue.
        ranked = members_at_risk((member(),), coaching_threshold=THRESHOLD)

        assert ranked == ()

    def test_more_signs_ranks_higher(self) -> None:
        """The one ordering claim that holds without outcome data.

        A member carrying three independent signs is more clearly in trouble
        than one carrying a single sign. Anything finer would be invented.
        """
        one = member("CHM1", unresolved=1)
        three = member("CHM3", unresolved=1, ended_unhappy=1, call_count=2)

        ranked = members_at_risk((one, three), coaching_threshold=THRESHOLD)

        assert [item.member_id for item in ranked] == ["CHM3", "CHM1"]

    def test_equal_signs_break_on_contact_then_handling(self) -> None:
        quiet = member("CHM-QUIET", unresolved=1, call_count=1, lowest_score=55)
        persistent = member("CHM-PERSISTENT", unresolved=1, call_count=4, lowest_score=55)

        ranked = members_at_risk((quiet, persistent), coaching_threshold=THRESHOLD)

        assert ranked[0].member_id == "CHM-PERSISTENT"

    def test_the_calls_behind_a_member_are_carried_through(self) -> None:
        # The list is only actionable if it can be opened.
        ranked = members_at_risk(
            (member(unresolved=1, references=("C0001", "C0042")),), coaching_threshold=THRESHOLD
        )

        assert ranked[0].references == ("C0001", "C0042")
