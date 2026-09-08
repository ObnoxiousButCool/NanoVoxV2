"""Progress of a corpus run, computed from its items.

Progress is derived, never stored. A stored counter and a table of items are two
sources of truth that drift the moment a process dies between the two writes, and
the run record is precisely the thing that has to survive a crash.

The four outcomes are reported separately rather than as "done / not done". A run
that skipped ninety calls and analyzed ten is not the same event as one that
analyzed a hundred, and a progress bar that showed both as full would say it was.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from domain.value_objects.run_status import RunItemStatus


@dataclass(frozen=True)
class RunProgress:
    """How far a run has got, and what it produced on the way."""

    total: int
    completed: int
    failed: int
    skipped: int
    cancelled: int
    running: int
    pending: int

    @property
    def finished(self) -> int:
        """Items that will not be worked on again in this run."""
        return self.completed + self.failed + self.skipped + self.cancelled

    @property
    def remaining(self) -> int:
        return self.running + self.pending

    @property
    def percent_complete(self) -> float:
        """Share of items finished, to one decimal place.

        A run with no items is 100% finished rather than 0%: there is nothing
        left to do, and showing an empty run as stalled at zero would be wrong.
        """
        if self.total <= 0:
            return 100.0
        return round((self.finished * 100) / self.total, 1)

    @property
    def is_exhausted(self) -> bool:
        """Whether every item has reached a resting state."""
        return self.remaining == 0


def summarise(statuses: Iterable[RunItemStatus]) -> RunProgress:
    """Count item statuses into a progress record."""
    counts = dict.fromkeys(RunItemStatus, 0)
    total = 0
    for status in statuses:
        counts[status] += 1
        total += 1

    return RunProgress(
        total=total,
        completed=counts[RunItemStatus.COMPLETED],
        failed=counts[RunItemStatus.FAILED],
        skipped=counts[RunItemStatus.SKIPPED],
        cancelled=counts[RunItemStatus.CANCELLED],
        running=counts[RunItemStatus.RUNNING],
        pending=counts[RunItemStatus.PENDING],
    )
