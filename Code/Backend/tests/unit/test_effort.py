"""What getting an answer costs a member."""

from __future__ import annotations

from domain.aggregation.effort import EffortMetrics, effort_metrics, long_call_threshold


def metrics(durations: tuple[int, ...], **counts: object) -> EffortMetrics:
    defaults: dict[str, object] = {
        "identified_members": 0,
        "repeat_members": 0,
        "calls_by_repeat_members": 0,
    }
    defaults.update(counts)
    return effort_metrics(durations, **defaults)  # type: ignore[arg-type]


class TestDuration:
    def test_the_median_and_mean_are_both_reported(self) -> None:
        # Same reason the score histogram shows both: one long call drags the
        # mean somewhere no actual call sits.
        result = metrics((5, 5, 5, 5, 60))

        assert result.median_minutes == 5.0
        assert result.mean_minutes == 16.0

    def test_long_is_derived_from_this_corpus_not_configured(self) -> None:
        """Twice the median.

        A fixed number of minutes means something different for a pharmacy query
        than for an appeal, and drifts as the mix of calls changes.
        """
        assert long_call_threshold((10, 10, 10)) == 20
        assert long_call_threshold((4, 4, 4)) == 8

    def test_long_calls_are_counted_at_the_threshold(self) -> None:
        result = metrics((10, 10, 10, 20, 30))

        assert result.long_call_threshold == 20
        assert result.long_call_count == 2

    def test_no_durations_reports_zero_rather_than_failing(self) -> None:
        # A corpus mid-analysis has none; a divide-by-zero is not the answer.
        result = metrics(())

        assert result.calls_with_duration == 0
        assert result.median_minutes == 0.0
        assert result.long_call_threshold == 0


class TestRepeatContact:
    def test_the_rate_is_a_share_of_identified_members(self) -> None:
        result = metrics((10,), identified_members=50, repeat_members=5)

        assert result.repeat_contact_rate == 10.0

    def test_no_identified_members_is_zero_not_an_error(self) -> None:
        """Every call anonymous — the state before member IDs were extracted.

        Zero is honest here: nothing is known about repeat contact. It must not
        raise, because the dashboard would go blank rather than degrade.
        """
        result = metrics((10,), identified_members=0, repeat_members=0)

        assert result.repeat_contact_rate == 0.0

    def test_calls_by_repeat_members_is_carried_separately(self) -> None:
        # Two members accounting for five calls is a different story from two
        # members accounting for four.
        result = metrics(
            (10,), identified_members=10, repeat_members=2, calls_by_repeat_members=5
        )

        assert result.repeat_members == 2
        assert result.calls_by_repeat_members == 5


class TestTimeToAnAnswer:
    def test_the_median_is_taken_over_members_not_calls(self) -> None:
        # A member who rang three times spent 30 minutes getting their answer,
        # even though no single call was long. Per call this would read 10.
        result = metrics((10, 10, 10, 30), minutes_to_answer=(30, 30))

        assert result.median_minutes_to_answer == 30
        assert result.members_with_answer == 2

    def test_members_still_waiting_are_counted_but_not_averaged_in(self) -> None:
        # The trap this avoids: treat an unfinished wait as a finished one and
        # the reported time to an answer *falls* the longer people are left.
        answered = metrics((10,), minutes_to_answer=(20, 40))
        with_waiting = metrics((10,), minutes_to_answer=(20, 40), members_without_answer=7)

        assert with_waiting.median_minutes_to_answer == answered.median_minutes_to_answer == 30
        assert with_waiting.members_without_answer == 7
        assert with_waiting.members_with_answer == 2

    def test_nobody_answered_yet_reports_zero_rather_than_failing(self) -> None:
        result = metrics((10,), members_without_answer=4)

        assert result.median_minutes_to_answer == 0.0
        assert result.members_with_answer == 0
        assert result.members_without_answer == 4

    def test_an_empty_corpus_still_reports_the_field(self) -> None:
        assert metrics(()).median_minutes_to_answer == 0.0
