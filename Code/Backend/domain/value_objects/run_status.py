"""States a corpus run and its items move through.

Two enums rather than one: a run and a single call fail for different reasons and
recover differently. An item that fails leaves the run healthy — one unparseable
call out of a hundred is not a failed run — so the run's own status must not be
derivable from any single item's.

``INTERRUPTED`` is deliberately distinct from ``FAILED``. A run whose process died
was not rejected by anything; it stopped mid-flight and its remaining work is
still valid. Collapsing the two would hide the one case that is resumable.
"""

from __future__ import annotations

from enum import Enum


class RunStatus(str, Enum):
    """Lifecycle of a whole corpus run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"

    @property
    def is_terminal(self) -> bool:
        """Whether no further work will happen without a new instruction."""
        return self in _TERMINAL

    @property
    def is_active(self) -> bool:
        """Whether a worker is, or should be, processing this run."""
        return self in _ACTIVE

    @property
    def is_resumable(self) -> bool:
        """Whether unfinished items may be picked up again.

        A cancelled run is resumable: cancelling is a pause the operator chose,
        and refusing to continue it would make cancel a destructive act.
        """
        return self in _RESUMABLE


class RunItemStatus(str, Enum):
    """Lifecycle of one call within a run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"

    @property
    def is_finished(self) -> bool:
        return self in _FINISHED_ITEMS

    @property
    def needs_work(self) -> bool:
        """Whether a resume should pick this item up again.

        A failed item is retried, a skipped one is not: skipping was a decision
        about the item ("already analysed"), while failing was an accident.
        """
        return self in _UNFINISHED_ITEMS


_TERMINAL = frozenset(
    {RunStatus.CANCELLED, RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.INTERRUPTED}
)
_ACTIVE = frozenset({RunStatus.PENDING, RunStatus.RUNNING, RunStatus.CANCELLING})
_RESUMABLE = frozenset({RunStatus.CANCELLED, RunStatus.FAILED, RunStatus.INTERRUPTED})
_FINISHED_ITEMS = frozenset(
    {
        RunItemStatus.COMPLETED,
        RunItemStatus.FAILED,
        RunItemStatus.SKIPPED,
        RunItemStatus.CANCELLED,
    }
)
_UNFINISHED_ITEMS = frozenset(
    {RunItemStatus.PENDING, RunItemStatus.RUNNING, RunItemStatus.FAILED, RunItemStatus.CANCELLED}
)
