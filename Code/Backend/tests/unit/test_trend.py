"""The weekly series, which is the only figure that says which way we are going.

The corpus that motivated it reports 54% resolution overall while the weeks
behind it run 88, 70, 43, 33, 57. Every test here is about not flattening that
back out again.
"""

from __future__ import annotations

from datetime import date, datetime

from domain.aggregation.trend import Bucket, TrendCall, centred_window, month_window, trend


def call(
    day: str, score: int = 80, resolution: str = "RESOLVED", seconds: int | None = 420
) -> TrendCall:
    return TrendCall(
        started_at=datetime.fromisoformat(day),
        score=score,
        resolution=resolution,
        duration_seconds=seconds,
    )


class TestBucketing:
    def test_a_week_starts_on_monday(self) -> None:
        # 2026-09-03 is a Thursday; its week starts on the 31st of August.
        result = trend([call("2026-09-03T10:00:00")])

        assert result.points[0].starting == date(2026, 8, 31)
        assert result.points[0].label == "31 Aug"

    def test_calls_in_the_same_week_land_in_one_point(self) -> None:
        result = trend([call("2026-08-31T09:00:00"), call("2026-09-06T23:00:00")])

        assert len(result.points) == 1
        assert result.points[0].calls == 2

    def test_sunday_belongs_to_the_week_that_began_on_monday(self) -> None:
        # The off-by-one that would split a working week across two points.
        result = trend([call("2026-09-06T23:59:00"), call("2026-09-07T00:01:00")])

        assert [point.starting for point in result.points] == [
            date(2026, 8, 31),
            date(2026, 9, 7),
        ]


class TestAWeekNobodyCalled:
    def test_it_is_kept_rather_than_closed_up(self) -> None:
        # Closing the gap would draw a line straight through a week that was
        # never measured, which reads as a measurement.
        result = trend([call("2026-08-31T09:00:00"), call("2026-09-14T09:00:00")])

        assert [point.label for point in result.points] == ["31 Aug", "7 Sep", "14 Sep"]
        assert result.points[1].calls == 0

    def test_its_metrics_are_absent_not_zero(self) -> None:
        # Zero is a score. No calls is not a score.
        result = trend([call("2026-08-31T09:00:00"), call("2026-09-14T09:00:00")])
        empty = result.points[1]

        assert empty.average_score is None
        assert empty.resolution_rate is None
        assert empty.average_handle_minutes is None

    def test_the_comparison_skips_it(self) -> None:
        # "Down on last week" has to mean the last week anybody called.
        result = trend([call("2026-08-31T09:00:00"), call("2026-09-14T09:00:00")])

        assert result.latest is not None
        assert result.previous is not None
        assert result.latest.label == "14 Sep"
        assert result.previous.label == "31 Aug"


class TestTheFigures:
    def test_resolution_counts_only_fully_resolved_calls(self) -> None:
        result = trend(
            [
                call("2026-08-31T09:00:00", resolution="RESOLVED"),
                call("2026-08-31T10:00:00", resolution="PARTIALLY RESOLVED"),
                call("2026-08-31T11:00:00", resolution="UNRESOLVED"),
                call("2026-08-31T12:00:00", resolution="RESOLVED"),
            ]
        )

        assert result.points[0].resolution_rate == 50.0

    def test_the_score_is_a_mean_not_a_median(self) -> None:
        # The card reading this is labelled "Average Call Score", so a weak call
        # has to pull the figure down. A median would report 90 here and hide
        # the 20 entirely.
        result = trend(
            [
                call("2026-08-31T09:00:00", score=20),
                call("2026-08-31T10:00:00", score=90),
                call("2026-08-31T11:00:00", score=95),
            ]
        )

        assert result.points[0].average_score == 68.3

    def test_handle_time_is_measured_over_the_calls_that_state_one(self) -> None:
        # A week half of whose calls are untimed still has a real average for
        # the half that are; reporting None would hide it.
        result = trend(
            [
                call("2026-08-31T09:00:00", seconds=300),
                call("2026-08-31T10:00:00", seconds=600),
                call("2026-08-31T11:00:00", seconds=None),
            ]
        )

        assert result.points[0].average_handle_minutes == 7.5
        assert result.points[0].calls == 3

    def test_a_week_with_no_timed_call_reports_no_handle_time(self) -> None:
        result = trend([call("2026-08-31T09:00:00", seconds=None)])

        assert result.points[0].average_handle_minutes is None
        assert result.points[0].average_score == 80.0


class TestWhatCannotBePlaced:
    def test_a_call_with_no_start_time_is_counted_and_excluded(self) -> None:
        # Silently dropping it would make the series claim to cover the corpus.
        result = trend(
            [
                call("2026-08-31T09:00:00"),
                TrendCall(started_at=None, score=50, resolution="RESOLVED", duration_seconds=300),
            ]
        )

        assert result.undated_calls == 1
        assert sum(point.calls for point in result.points) == 1

    def test_no_dated_call_is_an_empty_series_rather_than_an_error(self) -> None:
        result = trend(
            [TrendCall(started_at=None, score=50, resolution="RESOLVED", duration_seconds=None)]
        )

        assert result.points == ()
        assert result.undated_calls == 1
        assert result.latest is None
        assert result.previous is None

    def test_one_week_has_nothing_to_compare_against(self) -> None:
        result = trend([call("2026-08-31T09:00:00")])

        assert result.latest is not None
        assert result.previous is None


class TestMonthWindow:
    def test_keeps_only_weeks_whose_monday_falls_in_the_month(self) -> None:
        # 31 Aug's Monday is in August even though the week runs into
        # September; 7, 14, 21 and 28 Sep are the rest of September's weeks.
        full = trend(
            [
                call("2026-08-31T09:00:00"),
                call("2026-09-07T09:00:00"),
                call("2026-09-14T09:00:00"),
                call("2026-09-21T09:00:00"),
                call("2026-09-28T09:00:00"),
            ]
        )

        result = month_window(full, date(2026, 9, 15))

        assert [point.label for point in result.points] == ["7 Sep", "14 Sep", "21 Sep", "28 Sep"]

    def test_a_week_starting_in_the_target_month_but_running_into_the_next_is_kept(self) -> None:
        full = trend([call("2026-08-31T09:00:00")])

        result = month_window(full, date(2026, 8, 3))

        assert [point.label for point in result.points] == ["31 Aug"]

    def test_a_month_with_no_weeks_is_an_empty_series_not_an_error(self) -> None:
        full = trend([call("2026-08-31T09:00:00")])

        result = month_window(full, date(2027, 1, 1))

        assert result.points == ()

    def test_carries_the_undated_count_through_unchanged(self) -> None:
        full = trend(
            [
                call("2026-09-07T09:00:00"),
                TrendCall(started_at=None, score=50, resolution="RESOLVED", duration_seconds=None),
            ]
        )

        result = month_window(full, date(2026, 9, 1))

        assert result.undated_calls == 1


_FIVE_WEEKS = [
    "2026-08-31T09:00:00",
    "2026-09-07T09:00:00",
    "2026-09-14T09:00:00",
    "2026-09-21T09:00:00",
    "2026-09-28T09:00:00",
]


class TestCentredWindow:
    """The bug this exists to fix: a trailing count has no way to say a
    requested week is nowhere near the data — "the last 3 weeks at or
    before November" is always answerable if any week exists at all, and
    answers with whichever weeks that happen to be, mislabelled as if they
    were November's."""

    def test_a_week_the_corpus_has_returns_it_with_a_neighbour_either_side(self) -> None:
        full = trend([call(day) for day in _FIVE_WEEKS])

        result = centred_window(full, date(2026, 9, 9))  # inside the 7 Sep week

        assert [point.label for point in result.points] == ["31 Aug", "7 Sep", "14 Sep"]

    def test_a_date_long_after_every_week_the_corpus_has_is_empty_not_the_latest(self) -> None:
        # The exact regression: picking a date past the data used to fall
        # back to the trailing 3 weeks (14/21/28 Sep) instead of admitting
        # there is nothing there.
        full = trend([call(day) for day in _FIVE_WEEKS])

        result = centred_window(full, date(2026, 11, 9))

        assert result.points == ()

    def test_a_date_long_before_every_week_the_corpus_has_is_empty(self) -> None:
        full = trend([call(day) for day in _FIVE_WEEKS])

        result = centred_window(full, date(2026, 8, 12))

        assert result.points == ()

    def test_a_date_the_day_after_the_last_weeks_range_is_still_empty(self) -> None:
        # 28 Sep's own week runs 28 Sep - 4 Oct inclusive; 5 Oct is the first
        # date that is genuinely outside every week the corpus has.
        full = trend([call(day) for day in _FIVE_WEEKS])

        result = centred_window(full, date(2026, 10, 5))

        assert result.points == ()

    def test_the_first_week_has_no_week_before_it_to_include(self) -> None:
        full = trend([call(day) for day in _FIVE_WEEKS])

        result = centred_window(full, date(2026, 9, 2))  # inside the 31 Aug week

        assert [point.label for point in result.points] == ["31 Aug", "7 Sep"]

    def test_the_last_week_has_no_week_after_it_to_include(self) -> None:
        full = trend([call(day) for day in _FIVE_WEEKS])

        result = centred_window(full, date(2026, 9, 30))  # inside the 28 Sep week

        assert [point.label for point in result.points] == ["21 Sep", "28 Sep"]


class TestMonthBuckets:
    """Months are re-bucketed from the calls, never folded from the weeks.

    The dashboard's period filter used to resolve "September" to September's
    last week and leave the series weekly, so the strip reported 11 of the
    month's 89 calls. Folding the weekly points together instead would fix the
    count and leave the averages wrong: the average of four weekly averages is
    not the average of the calls, and it is not a number the corpus contains.
    """

    def test_a_month_starts_on_the_first(self) -> None:
        result = trend([call("2026-09-17T10:00:00")], Bucket.MONTH)

        assert result.points[0].starting == date(2026, 9, 1)
        assert result.points[0].label == "Sep 2026"

    def test_a_week_spanning_two_months_splits_between_them(self) -> None:
        # The week of 31 August holds one August call and one September call.
        # Weekly, both land in August's "31 Aug" bucket; by month they do not.
        calls = [call("2026-08-31T09:00:00"), call("2026-09-01T09:00:00")]

        weekly = trend(calls)
        monthly = trend(calls, Bucket.MONTH)

        assert [(p.label, p.calls) for p in weekly.points] == [("31 Aug", 2)]
        assert [(p.label, p.calls) for p in monthly.points] == [
            ("Aug 2026", 1),
            ("Sep 2026", 1),
        ]

    def test_the_average_is_taken_over_the_month_own_calls(self) -> None:
        # Weekly averages of 10 and 100 either side of a month boundary would
        # themselves average to 55. The month's own average is 32.5, because
        # three of its four calls are in the weak week -- weighting the weeks
        # equally would report a month the corpus does not contain.
        calls = [
            call("2026-09-07T09:00:00", score=10),
            call("2026-09-08T09:00:00", score=10),
            call("2026-09-09T09:00:00", score=10),
            call("2026-09-21T09:00:00", score=100),
        ]

        month = trend(calls, Bucket.MONTH).points[0]

        assert month.calls == 4
        assert month.average_score == 32.5

    def test_the_resolution_rate_is_counted_over_the_month(self) -> None:
        calls = [
            call("2026-09-02T09:00:00", resolution="RESOLVED"),
            call("2026-09-09T09:00:00", resolution="UNRESOLVED"),
            call("2026-09-16T09:00:00", resolution="RESOLVED"),
            call("2026-09-23T09:00:00", resolution="RESOLVED"),
        ]

        month = trend(calls, Bucket.MONTH).points[0]

        assert month.resolution_rate == 75.0

    def test_a_month_nobody_called_in_is_kept_and_carries_nothing(self) -> None:
        # Same rule as an empty week: a gap is a fact about the year, and
        # closing it would draw a line through a month that was never measured.
        result = trend([call("2026-09-15T09:00:00"), call("2026-11-15T09:00:00")], Bucket.MONTH)

        assert [(p.label, p.calls) for p in result.points] == [
            ("Sep 2026", 1),
            ("Oct 2026", 0),
            ("Nov 2026", 1),
        ]
        assert result.points[1].average_score is None

    def test_the_series_crosses_a_year_end(self) -> None:
        result = trend([call("2025-12-10T09:00:00"), call("2026-01-10T09:00:00")], Bucket.MONTH)

        assert [p.label for p in result.points] == ["Dec 2025", "Jan 2026"]

    def test_a_month_is_not_stepped_by_a_fixed_number_of_days(self) -> None:
        # Stepping 31 days from 31 January lands in March and drops February
        # out of the series entirely.
        result = trend([call("2026-01-31T09:00:00"), call("2026-03-02T09:00:00")], Bucket.MONTH)

        assert [p.label for p in result.points] == ["Jan 2026", "Feb 2026", "Mar 2026"]

    def test_the_previous_point_is_the_month_before(self) -> None:
        # What the strip's delta compares against, once a month is picked.
        result = trend([call("2026-08-10T09:00:00"), call("2026-09-10T09:00:00")], Bucket.MONTH)

        assert result.latest is not None
        assert result.previous is not None
        assert result.latest.label == "Sep 2026"
        assert result.previous.label == "Aug 2026"


class TestEscalationRate:
    """Counted per period, for the same reason the resolution rate is.

    One call escalating in a quiet week is a different fact from one escalating
    across a hundred, and the all-time card reported the second while a reader
    asking "how are we doing this week" wanted the first. On the shipped corpus
    four weeks in five escalate nothing while the corpus reads 1%.
    """

    def test_the_rate_is_counted_over_the_period(self) -> None:
        calls = [
            call("2026-09-07T09:00:00", resolution="ESCALATED"),
            call("2026-09-08T09:00:00", resolution="RESOLVED"),
            call("2026-09-09T09:00:00", resolution="RESOLVED"),
            call("2026-09-10T09:00:00", resolution="UNRESOLVED"),
        ]

        assert trend(calls).points[0].escalation_rate == 25.0

    def test_a_period_nobody_escalated_in_reads_zero_not_absent(self) -> None:
        # Distinct from a period with no calls: this one was measured, and the
        # answer was none.
        result = trend([call("2026-09-07T09:00:00", resolution="RESOLVED")])

        assert result.points[0].escalation_rate == 0.0

    def test_a_period_with_no_calls_carries_nothing(self) -> None:
        result = trend([call("2026-09-07T09:00:00"), call("2026-09-21T09:00:00")])

        assert result.points[1].calls == 0
        assert result.points[1].escalation_rate is None

    def test_a_month_counts_escalations_over_the_month(self) -> None:
        # Not the average of its weeks: two escalations in a 20-call month is
        # 10%, whatever the weekly rates either side of it were.
        calls = [call(f"2026-09-{day:02d}T09:00:00") for day in range(1, 21)]
        calls[0] = call("2026-09-01T09:00:00", resolution="ESCALATED")
        calls[15] = call("2026-09-16T09:00:00", resolution="ESCALATED")

        month = trend(calls, Bucket.MONTH).points[0]

        assert month.calls == 20
        assert month.escalation_rate == 10.0
