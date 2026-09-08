"""When the calls come, and when they go badly.

The lever this figure implicates is the roster, so the tests are mostly about
not handing anyone a rota change built on two calls.
"""

from __future__ import annotations

from datetime import datetime

from domain.aggregation.hourly import THIN_EVIDENCE_BELOW, HourCall, hourly_load


def call(hour: int, score: int = 80, resolution: str = "RESOLVED") -> HourCall:
    return HourCall(
        # Naive on purpose: the corpus states local wall-clock times, and the
        # aggregation reads the hour exactly as the source gave it.
        started_at=datetime(2026, 9, 1, hour, 30),  # noqa: DTZ001
        score=score,
        resolution=resolution,
    )


def hours(counts: dict[int, int], score: int = 80) -> list[HourCall]:
    return [call(hour, score=score) for hour, count in counts.items() for _ in range(count)]


class TestTheAxis:
    def test_only_hours_the_centre_worked_are_returned(self) -> None:
        # Padding to twenty-four hours spends most of the chart drawing the night.
        result = hourly_load(hours({9: 1, 16: 1}))

        assert result.hours[0].hour == 9
        assert result.hours[-1].hour == 16

    def test_a_quiet_hour_inside_the_day_is_kept(self) -> None:
        # A gap in the middle of the working day is something to see, not to
        # close up.
        result = hourly_load(hours({9: 1, 11: 1}))

        assert [point.hour for point in result.hours] == [9, 10, 11]
        assert result.hours[1].calls == 0
        assert result.hours[1].average_score is None

    def test_a_call_with_no_start_time_is_counted_and_excluded(self) -> None:
        result = hourly_load([call(9), HourCall(started_at=None, score=50, resolution="RESOLVED")])

        assert result.undated_calls == 1
        assert sum(point.calls for point in result.hours) == 1

    def test_no_dated_call_is_an_empty_chart(self) -> None:
        result = hourly_load([HourCall(started_at=None, score=50, resolution="RESOLVED")])

        assert result.hours == ()
        assert result.busiest is None
        assert result.weakest is None


class TestThinEvidence:
    def test_an_hour_below_the_floor_is_marked(self) -> None:
        result = hourly_load(hours({9: THIN_EVIDENCE_BELOW - 1}))

        assert result.hours[0].is_thin

    def test_an_hour_at_the_floor_is_not(self) -> None:
        result = hourly_load(hours({9: THIN_EVIDENCE_BELOW}))

        assert not result.hours[0].is_thin

    def test_an_empty_hour_is_not_thin_it_is_empty(self) -> None:
        result = hourly_load(hours({9: 5, 11: 5}))

        assert result.hours[1].calls == 0
        assert not result.hours[1].is_thin

    def test_the_weakest_hour_ignores_the_thin_ones(self) -> None:
        # The whole point of the floor: a two-call hour scoring 10 must not
        # become the hour somebody re-staffs.
        result = hourly_load(
            [
                *[call(9, score=20) for _ in range(THIN_EVIDENCE_BELOW - 1)],
                *[call(10, score=60) for _ in range(THIN_EVIDENCE_BELOW)],
                *[call(11, score=90) for _ in range(THIN_EVIDENCE_BELOW)],
            ]
        )

        assert result.weakest is not None
        assert result.weakest.hour == 10

    def test_no_hour_with_enough_calls_yields_no_finding(self) -> None:
        result = hourly_load(hours({9: 1, 10: 1}))

        assert result.weakest is None


class TestTheFigures:
    def test_the_busiest_hour_is_the_one_with_most_calls(self) -> None:
        result = hourly_load(hours({9: 2, 10: 7, 11: 3}))

        assert result.busiest is not None
        assert result.busiest.hour == 10

    def test_resolution_is_reported_per_hour(self) -> None:
        result = hourly_load([call(9, resolution="RESOLVED"), call(9, resolution="UNRESOLVED")])

        assert result.hours[0].resolution_rate == 50.0
