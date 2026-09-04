"""What speed costs.

The statistic is deliberately measured over calls while the picture is drawn
over agents, and these tests are mostly about keeping those two apart: the
version that split agents produced a comparison of one agent against nobody on
the shipped corpus, because only one agent clears the tier threshold.
"""

from __future__ import annotations

from domain.aggregation.handle_time_quality import AgentSpeed, TimedCall, handle_time_quality


def agent(name: str, minutes: float, score: float, *, comparable: bool = True) -> AgentSpeed:
    return AgentSpeed(
        agent_name=name,
        calls=6 if comparable else 3,
        average_score=score,
        average_handle_minutes=minutes,
        is_comparable=comparable,
    )


def timed(minutes: float, score: int) -> TimedCall:
    return TimedCall(duration_seconds=round(minutes * 60), score=score)


SHORT_AND_POOR = [timed(4, 50), timed(5, 60)]
LONG_AND_GOOD = [timed(9, 85), timed(10, 90)]


class TestTheSplit:
    def test_it_is_measured_over_calls_not_over_agents(self) -> None:
        # One comparable agent used to mean no comparison at all. The calls are
        # what the number comes from, so a single agent still yields one.
        result = handle_time_quality([agent("Sarah", 10.0, 84.0)], SHORT_AND_POOR + LONG_AND_GOOD)

        assert result.faster is not None
        assert result.slower is not None
        assert result.faster.calls == 2
        assert result.slower.calls == 2

    def test_the_gap_is_positive_when_the_slower_half_scores_higher(self) -> None:
        # The direction that matters: it is the one an AHT target makes worse.
        result = handle_time_quality([], SHORT_AND_POOR + LONG_AND_GOOD)

        assert result.score_gap > 0
        assert result.slower is not None
        assert result.slower.average_score == 87.5

    def test_the_gap_is_negative_when_the_faster_half_scores_higher(self) -> None:
        result = handle_time_quality([], [timed(4, 90), timed(5, 88), timed(9, 50), timed(10, 55)])

        assert result.score_gap < 0

    def test_the_median_call_is_the_boundary_not_a_target(self) -> None:
        result = handle_time_quality([], [timed(2, 70), timed(4, 70), timed(6, 70), timed(8, 70)])

        assert result.split_minutes == 5.0

    def test_a_call_exactly_at_the_median_counts_as_slower(self) -> None:
        # Half-open, matching the score histogram: a boundary value belongs to
        # one side, never to both.
        result = handle_time_quality([], [timed(5, 70), timed(5, 70), timed(9, 70)])

        assert result.split_minutes == 5.0
        assert result.faster is None
        assert result.slower is not None
        assert result.slower.calls == 3


class TestTooLittleToCompare:
    def test_one_timed_call_yields_no_split(self) -> None:
        result = handle_time_quality([agent("Sarah", 10.0, 84.0)], [timed(7, 80)])

        assert result.faster is None
        assert result.slower is None
        assert result.score_gap == 0.0

    def test_the_agents_are_still_returned(self) -> None:
        # The chart is worth drawing even when the sentence beneath it is not.
        result = handle_time_quality([agent("Sarah", 10.0, 84.0)], [])

        assert [row.agent_name for row in result.agents] == ["Sarah"]

    def test_a_call_with_no_duration_is_not_a_zero_minute_call(self) -> None:
        result = handle_time_quality([], [timed(9, 85), TimedCall(duration_seconds=0, score=10)])

        assert result.faster is None
        assert result.slower is None


class TestTheAgents:
    def test_they_are_ordered_slowest_first(self) -> None:
        result = handle_time_quality(
            [agent("Brad", 4.7, 57.0), agent("Sarah", 10.0, 84.2), agent("Tony", 6.9, 79.0)],
            LONG_AND_GOOD + SHORT_AND_POOR,
        )

        assert [row.agent_name for row in result.agents] == ["Sarah", "Tony", "Brad"]

    def test_an_agent_below_the_threshold_is_flagged_not_dropped(self) -> None:
        # Their volume is real. A four-call average is not, so it is marked.
        result = handle_time_quality(
            [agent("Sarah", 10.0, 84.0), agent("Priya", 9.0, 75.0, comparable=False)],
            LONG_AND_GOOD + SHORT_AND_POOR,
        )

        assert len(result.agents) == 2
        assert result.flagged_agents == 1
