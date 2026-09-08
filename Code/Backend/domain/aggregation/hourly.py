"""When the calls come, and when they go badly.

Load and quality by hour of the working day. This is the one figure on the
dashboard a leader can act on the same week they read it, because the lever is
the roster: if quality falls at a particular hour, that hour is understaffed, or
staffed by the people who are also at lunch.

On the shipped corpus the 13:00 hour averages 63 against 90 at 08:00, on six
calls — which is why the hour a reader is drawn to is reported *with its call
count beside it* and marked as thin evidence below a floor. A single bad hour
built from two calls is a rota change made on noise.

Hours are read from the call's stated start time in local wall-clock, as the
source gives it. No zone is attached, because the source never gave one and a
zone invented here would silently shift every bar.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from domain.aggregation.statistics import mean, percentage

__all__ = [
    "HourCall",
    "HourlyLoad",
    "HourlyPoint",
    "hourly_load",
]

# Below this, an hour's average is not evidence of anything about that hour.
# Named rather than inlined because it is the difference between a finding and
# a rota change made on noise.
THIN_EVIDENCE_BELOW = 4

_RESOLVED = "RESOLVED"


@dataclass(frozen=True)
class HourCall:
    """One call, reduced to when it started, how long it took and how it went."""

    started_at: datetime | None
    score: int
    resolution: str
    # Optional because the corpus does not state a handle time for every call.
    # Defaulted so the three existing construction sites stay valid, and so an
    # hour whose calls are all untimed reports no average rather than zero.
    handle_seconds: int | None = None


@dataclass(frozen=True)
class HourlyPoint:
    """One hour of the day."""

    hour: int
    label: str
    calls: int
    average_score: float | None
    resolution_rate: float | None
    # Mean handle time in minutes, over the calls in this hour that stated one.
    # None rather than 0.0 where none did: read on a staffing chart, a zero says
    # "this hour is instant" where the truth is "this hour is unmeasured", and
    # those argue for opposite rosters.
    average_handle_minutes: float | None = None

    @property
    def is_thin(self) -> bool:
        """Whether this hour has too few calls to read anything into."""
        return 0 < self.calls < THIN_EVIDENCE_BELOW


@dataclass(frozen=True)
class HourlyLoad:
    """Every hour the centre took a call in, earliest first."""

    hours: tuple[HourlyPoint, ...]
    undated_calls: int

    @property
    def busiest(self) -> HourlyPoint | None:
        return max(self.hours, key=lambda point: point.calls, default=None)

    @property
    def weakest(self) -> HourlyPoint | None:
        """The worst-scoring hour that has enough calls to mean something."""
        solid = [
            point
            for point in self.hours
            if point.calls >= THIN_EVIDENCE_BELOW and point.average_score is not None
        ]
        if not solid:
            return None
        return min(solid, key=lambda point: point.average_score or 0.0)


def _label(hour: int) -> str:
    return f"{hour:02d}:00"


def _average_minutes(rows: Sequence[HourCall]) -> float | None:
    """Mean handle time for an hour, in minutes, over the calls that stated one.

    Averaged over the timed calls rather than over all of them: dividing by the
    whole hour would drag every average toward zero in proportion to how much
    of the hour is unmeasured, which is a staffing figure that gets quieter the
    less you know.
    """
    timed = [row.handle_seconds for row in rows if row.handle_seconds is not None]
    if not timed:
        return None
    return round(mean(timed) / 60, 1)


def hourly_load(calls: Iterable[HourCall]) -> HourlyLoad:
    """Group calls by the hour they started, over the hours actually worked.

    Only hours the centre took a call in are returned. Padding out to a
    twenty-four hour axis would spend most of the chart drawing the night.
    """
    every = list(calls)
    dated = [call for call in every if call.started_at is not None]
    if not dated:
        return HourlyLoad(hours=(), undated_calls=len(every))

    by_hour: dict[int, list[HourCall]] = {}
    for call in dated:
        assert call.started_at is not None  # noqa: S101 - narrowed by the filter above
        by_hour.setdefault(call.started_at.hour, []).append(call)

    first, last = min(by_hour), max(by_hour)
    return HourlyLoad(
        hours=tuple(
            HourlyPoint(
                hour=hour,
                label=_label(hour),
                calls=len(rows),
                average_score=mean([row.score for row in rows]) if rows else None,
                resolution_rate=(
                    percentage(sum(1 for row in rows if row.resolution == _RESOLVED), len(rows))
                    if rows
                    else None
                ),
                average_handle_minutes=_average_minutes(rows),
            )
            # Every hour between the first and last worked, so a quiet hour in
            # the middle of the day is a gap a reader can see.
            for hour, rows in ((hour, by_hour.get(hour, [])) for hour in range(first, last + 1))
        ),
        undated_calls=len(every) - len(dated),
    )
