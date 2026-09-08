"""The weekly series, which is the only figure that says which way we are going.

The corpus that motivated it reports 54% resolution overall while the weeks
behind it run 88, 70, 43, 33, 57. Every test here is about not flattening that
back out again.
"""

from __future__ import annotations

from datetime import date, datetime

from domain.aggregation.trend import TrendCall, centred_window, month_window, trend


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

        assert empty.median_score is None
        assert empty.resolution_rate is None
        assert empty.median_handle_minutes is None

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

    def test_the_score_is_a_median_not_a_mean(self) -> None:
        # The distribution is bimodal; a mean sits in a gap where no call falls.
        result = trend(
            [
                call("2026-08-31T09:00:00", score=20),
                call("2026-08-31T10:00:00", score=90),
                call("2026-08-31T11:00:00", score=95),
            ]
        )

        assert result.points[0].median_score == 90.0

    def test_handle_time_is_measured_over_the_calls_that_state_one(self) -> None:
        # A week half of whose calls are untimed still has a real median for the
        # half that are; reporting None would hide it.
        result = trend(
            [
                call("2026-08-31T09:00:00", seconds=300),
                call("2026-08-31T10:00:00", seconds=600),
                call("2026-08-31T11:00:00", seconds=None),
            ]
        )

        assert result.points[0].median_handle_minutes == 7.5
        assert result.points[0].calls == 3

    def test_a_week_with_no_timed_call_reports_no_handle_time(self) -> None:
        result = trend([call("2026-08-31T09:00:00", seconds=None)])

        assert result.points[0].median_handle_minutes is None
        assert result.points[0].median_score == 80.0


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
