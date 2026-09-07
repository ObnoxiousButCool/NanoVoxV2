"""How the centre is moving, week by week.

Every other figure on this dashboard is an all-time total. That answers "how are
we doing" and not "are we getting better or worse", which is the question a
leader actually manages against — and the two can point in opposite directions.
On the shipped corpus they do: resolution reads 54% overall, and the weekly
series behind it runs 80, 52, 43, 50, 62. A single number reported the centre as
mildly below benchmark through a month in which resolution first fell by nearly
half and then recovered — two movements a manager would act on, and the average
of the two is the one thing that describes neither.

**Weekly, not daily.** A hundred calls over a month is three to five a day, and a
median over three calls moves on noise. A week is the shortest bucket in which a
change here is a change rather than a coin flip. Buckets start on Monday, so a
week is the working week a manager already thinks in.

**Empty weeks are kept and carry no metrics.** A week nobody called is a fact
about the month, and closing the gap would draw a line straight through it —
implying a measurement that was never taken. The metrics are ``None`` there
rather than zero, because zero is a score and no calls is not.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from domain.aggregation.statistics import median, percentage

__all__ = [
    "Trend",
    "TrendCall",
    "TrendPoint",
    "trend",
]

_RESOLVED = "RESOLVED"


@dataclass(frozen=True)
class TrendCall:
    """One call, reduced to what a trend needs."""

    started_at: datetime | None
    score: int
    resolution: str
    duration_seconds: int | None


@dataclass(frozen=True)
class TrendPoint:
    """One week."""

    starting: date
    label: str
    calls: int
    # None where the week has no calls: the series has a gap, not a zero.
    median_score: float | None
    resolution_rate: float | None
    median_handle_minutes: float | None


@dataclass(frozen=True)
class Trend:
    """The weekly series, and what the last complete move was."""

    points: tuple[TrendPoint, ...]
    # Calls with no start time, which cannot be placed in any week. Reported so
    # a reader can see the series covers less than the corpus does.
    undated_calls: int

    @property
    def latest(self) -> TrendPoint | None:
        """The most recent week that has calls in it."""
        return next((point for point in reversed(self.points) if point.calls), None)

    @property
    def previous(self) -> TrendPoint | None:
        """The week with calls before ``latest`` — the thing it is compared to.

        Skips empty weeks rather than comparing against a gap: "down 33 points
        on last week" must mean the last week anybody called, not silence.
        """
        with_calls = [point for point in self.points if point.calls]
        return with_calls[-2] if len(with_calls) >= 2 else None


def _monday(moment: datetime) -> date:
    day = moment.date()
    return day - timedelta(days=day.weekday())


def _label(starting: date) -> str:
    # "1 Sep" rather than a week number: nobody knows what week 38 is.
    return f"{starting.day} {starting.strftime('%b')}"


def _point(starting: date, calls: Sequence[TrendCall]) -> TrendPoint:
    if not calls:
        return TrendPoint(
            starting=starting,
            label=_label(starting),
            calls=0,
            median_score=None,
            resolution_rate=None,
            median_handle_minutes=None,
        )

    timed = [call.duration_seconds for call in calls if call.duration_seconds]
    return TrendPoint(
        starting=starting,
        label=_label(starting),
        calls=len(calls),
        median_score=median([call.score for call in calls]),
        resolution_rate=percentage(
            sum(1 for call in calls if call.resolution == _RESOLVED), len(calls)
        ),
        # Handle time is measured over the calls that state one, not over the
        # week: a week where half the calls are untimed still has a real median
        # for the half that are, and reporting None there would hide it.
        median_handle_minutes=round(median(timed) / 60, 1) if timed else None,
    )


def trend(calls: Iterable[TrendCall]) -> Trend:
    """Bucket calls into weeks, first to last, leaving empty weeks empty."""
    every = list(calls)
    dated = [call for call in every if call.started_at is not None]
    if not dated:
        return Trend(points=(), undated_calls=len(every))

    by_week: dict[date, list[TrendCall]] = {}
    for call in dated:
        assert call.started_at is not None  # noqa: S101 - narrowed by the filter above
        by_week.setdefault(_monday(call.started_at), []).append(call)

    first, last = min(by_week), max(by_week)
    weeks: list[date] = []
    cursor = first
    while cursor <= last:
        weeks.append(cursor)
        cursor += timedelta(days=7)

    return Trend(
        points=tuple(_point(week, by_week.get(week, [])) for week in weeks),
        undated_calls=len(every) - len(dated),
    )
