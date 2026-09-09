"""Turning a filter selection into the exact date range every other read-model
narrows its SQL by. ``month_range`` has to agree with ``trend.Bucket.MONTH``
about which calendar month a call belongs to — its own date's month, not the
week it falls in — since the month picker's options come from that same
bucketing (``available_months``) and a mismatch would let a card filter to a
different set of calls than the top strip shows for the same selection.
"""

from __future__ import annotations

from datetime import date

from domain.aggregation.period import month_range, resolve_period, week_range


class TestWeekRange:
    def test_returns_the_monday_to_monday_range_containing_the_anchor(self) -> None:
        # 2026-09-03 is a Thursday; its week runs 31 Aug (Mon) to 7 Sep (Mon).
        start, end = week_range(date(2026, 9, 3))

        assert start == date(2026, 8, 31)
        assert end == date(2026, 9, 7)

    def test_an_anchor_that_is_already_a_monday_is_its_own_start(self) -> None:
        start, end = week_range(date(2026, 8, 31))

        assert start == date(2026, 8, 31)
        assert end == date(2026, 9, 7)


class TestMonthRange:
    def test_covers_the_whole_calendar_month(self) -> None:
        start, end = month_range(date(2026, 9, 15))

        assert start == date(2026, 9, 1)
        assert end == date(2026, 10, 1)

    def test_rolls_over_the_year_at_december(self) -> None:
        start, end = month_range(date(2026, 12, 3))

        assert start == date(2026, 12, 1)
        assert end == date(2027, 1, 1)

    def test_agrees_with_bucket_month_about_which_calls_belong_to_the_month(self) -> None:
        # A call dated 2 Sep sits in the week starting 31 Aug, which trend's
        # weekly bucketing would put in the "31 Aug" point — but Bucket.MONTH
        # (what available_months is built from) counts it for September by
        # its own date, and this range has to agree or the month picker could
        # offer a month that filters to a different set of calls than the top
        # strip shows for the same selection.
        from datetime import datetime

        from domain.aggregation.trend import Bucket, TrendCall, trend

        calls = [
            TrendCall(
                started_at=datetime.fromisoformat("2026-09-02T09:00:00"),
                score=80,
                resolution="RESOLVED",
                duration_seconds=300,
            ),
        ]
        monthly = trend(calls, Bucket.MONTH)
        start, end = month_range(date(2026, 9, 1))

        assert monthly.points[0].label == "Sep 2026"
        assert start <= date(2026, 9, 2) < end
        assert not (start <= date(2026, 8, 31) < end)


class TestResolvePeriod:
    def test_a_month_takes_precedence_over_an_anchor(self) -> None:
        result = resolve_period(anchor=date(2026, 9, 3), month=date(2026, 7, 1))

        assert result == month_range(date(2026, 7, 1))

    def test_an_anchor_alone_resolves_to_its_week(self) -> None:
        result = resolve_period(anchor=date(2026, 9, 3), month=None)

        assert result == week_range(date(2026, 9, 3))

    def test_neither_given_is_all_time(self) -> None:
        assert resolve_period(anchor=None, month=None) is None
