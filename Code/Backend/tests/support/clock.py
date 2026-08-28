"""A clock that does not move, so timings are assertable."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from application.ports.clock import Clock

FIXED_NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


class FixedClock(Clock):
    """Returns a fixed time, advancing by a set step on each call if asked."""

    def __init__(self, start: datetime = FIXED_NOW, step: timedelta = timedelta(0)) -> None:
        self._now = start
        self._step = step

    def now(self) -> datetime:
        current = self._now
        self._now = self._now + self._step
        return current
