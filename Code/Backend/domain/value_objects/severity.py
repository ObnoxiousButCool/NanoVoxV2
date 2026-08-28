"""Signal severity, ordered so findings can be ranked."""

from __future__ import annotations

from enum import Enum
from typing import Any

_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


class Severity(str, Enum):
    """How serious a signal is. Ordered: ``LOW < MEDIUM < HIGH < CRITICAL``.

    All four comparisons are defined explicitly. Inheriting ``str`` means the
    string comparisons already exist, so ``functools.total_ordering`` would fill
    in nothing and ``max()`` would silently rank alphabetically — putting MEDIUM
    above CRITICAL.
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        return _RANK[self.value]

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank < other.rank

    def __le__(self, other: Any) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank <= other.rank

    def __gt__(self, other: Any) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank > other.rank

    def __ge__(self, other: Any) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank >= other.rank
