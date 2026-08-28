"""Clock port.

Time is injected rather than read from the ambient system so that use cases stay
deterministic under test. Nothing in the application layer calls
``datetime.now()`` directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class Clock(ABC):
    """Supplies the current time as a timezone-aware UTC datetime."""

    @abstractmethod
    def now(self) -> datetime:
        """Return the current time in UTC, timezone-aware."""
