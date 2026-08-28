"""System clock adapter for the :class:`~application.ports.clock.Clock` port."""

from __future__ import annotations

from datetime import datetime, timezone

from application.ports.clock import Clock


class SystemClock(Clock):
    """Reads the real wall clock, always in UTC."""

    def now(self) -> datetime:
        return datetime.now(tz=timezone.utc)
