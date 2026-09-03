"""What the time on calls bought."""

from __future__ import annotations

from domain.aggregation.time_value import CallTime, time_value

LABELS = {"pharmacy": "Pharmacy", "claims": "Claims", "empty": "Nothing here"}


def call(category: str, resolution: str, minutes: int, score: int = 80) -> CallTime:
    return CallTime(
        category_code=category, resolution=resolution, duration_minutes=minutes, score=score
    )


class TestTheMinuteLedger:
    def test_minutes_are_split_by_what_they_bought(self) -> None:
        result = time_value(
            [
                call("pharmacy", "RESOLVED", 10),
                call("pharmacy", "UNRESOLVED", 30),
            ],
            labels=LABELS,
        )

        assert result.total_minutes == 40
        assert result.resolved_minutes == 10
        assert result.unproductive_minutes == 30
        # A quarter of the time bought an answer, even though half the calls did.
        # Counting minutes is the whole point: the calls figure would say 50%.
        assert result.productive_share == 25.0

    def test_categories_are_ordered_by_the_time_they_claim(self) -> None:
        result = time_value(
            [
                call("pharmacy", "RESOLVED", 5),
                call("claims", "RESOLVED", 40),
            ],
            labels=LABELS,
        )

        assert [entry.label for entry in result.categories] == ["Claims", "Pharmacy"]

    def test_a_category_with_no_timed_calls_is_left_out(self) -> None:
        # Unlike the per-category charts, an empty row here would claim a share
        # of the centre's hours that does not exist.
        result = time_value([call("pharmacy", "RESOLVED", 10)], labels=LABELS)

        assert [entry.code for entry in result.categories] == ["pharmacy"]

    def test_every_outcome_keeps_a_segment_even_at_zero(self) -> None:
        result = time_value([call("pharmacy", "RESOLVED", 10)], labels=LABELS)
        segments = result.categories[0].by_outcome

        assert [segment.resolution for segment in segments] == [
            "RESOLVED",
            "PARTIALLY RESOLVED",
            "ESCALATED",
            "UNRESOLVED",
        ]
        assert [segment.minutes for segment in segments] == [10, 0, 0, 0]

    def test_segments_sum_to_the_total_beside_them(self) -> None:
        # Including an outcome the taxonomy does not list, which still has to be
        # counted somewhere or the bar would not match its own label.
        result = time_value(
            [
                call("pharmacy", "RESOLVED", 10),
                call("pharmacy", "SOMETHING NEW", 7),
            ],
            labels=LABELS,
        )
        entry = result.categories[0]

        assert sum(segment.minutes for segment in entry.by_outcome) + 7 == entry.total_minutes


class TestTheTwoFailureModes:
    def test_the_line_is_the_median_resolved_call(self) -> None:
        result = time_value(
            [
                call("pharmacy", "RESOLVED", 8),
                call("pharmacy", "RESOLVED", 10),
                call("pharmacy", "RESOLVED", 12),
            ],
            labels=LABELS,
        )

        assert result.resolved_median_minutes == 10

    def test_a_short_failure_is_a_coaching_signal(self) -> None:
        # Ended without an answer faster than a call that works: the member was
        # brushed off, and the score reflects it.
        result = time_value(
            [
                call("pharmacy", "RESOLVED", 10),
                call("pharmacy", "UNRESOLVED", 4, score=40),
            ],
            labels=LABELS,
        )

        assert result.fast_fail.calls == 1
        assert result.fast_fail.minutes == 4
        assert result.fast_fail.average_score == 40
        assert result.slow_fail.calls == 0

    def test_a_long_failure_is_a_process_signal(self) -> None:
        # The agent did the work and no answer existed. Same "unresolved"
        # bucket, opposite response — which is why they are counted apart.
        result = time_value(
            [
                call("pharmacy", "RESOLVED", 10),
                call("pharmacy", "PARTIALLY RESOLVED", 20, score=85),
            ],
            labels=LABELS,
        )

        assert result.slow_fail.calls == 1
        assert result.slow_fail.minutes == 20
        assert result.slow_fail.average_score == 85
        assert result.fast_fail.calls == 0

    def test_a_failure_exactly_on_the_line_counts_as_slow(self) -> None:
        # The boundary has to fall one way. A call that took as long as a
        # successful one did not cut the member short.
        result = time_value(
            [call("pharmacy", "RESOLVED", 10), call("pharmacy", "ESCALATED", 10)],
            labels=LABELS,
        )

        assert (result.fast_fail.calls, result.slow_fail.calls) == (0, 1)

    def test_the_two_modes_account_for_every_failure(self) -> None:
        calls = [
            call("pharmacy", "RESOLVED", 10),
            call("pharmacy", "UNRESOLVED", 3),
            call("claims", "PARTIALLY RESOLVED", 18),
            call("claims", "ESCALATED", 25),
        ]
        result = time_value(calls, labels=LABELS)

        assert result.fast_fail.calls + result.slow_fail.calls == 3
        assert result.fast_fail.minutes + result.slow_fail.minutes == result.unproductive_minutes

    def test_with_nothing_resolved_there_is_no_line_to_split_on(self) -> None:
        # Rather than invent a threshold, every failure counts as slow.
        result = time_value(
            [call("pharmacy", "UNRESOLVED", 5), call("pharmacy", "UNRESOLVED", 30)],
            labels=LABELS,
        )

        assert result.resolved_median_minutes == 0.0
        assert result.fast_fail.calls == 0
        assert result.slow_fail.calls == 2

    def test_an_empty_corpus_reports_zeroes_rather_than_failing(self) -> None:
        result = time_value([], labels=LABELS)

        assert result.total_minutes == 0
        assert result.productive_share == 0.0
        assert result.categories == ()
        assert result.fast_fail.average_score == 0.0
