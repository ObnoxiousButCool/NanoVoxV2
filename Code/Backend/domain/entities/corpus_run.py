"""A corpus run and the per-call record that makes it resumable.

The run is a *record*, not a job handle. Everything needed to continue the work
lives in these rows, so a browser refresh reattaches to a live run and a crashed
process leaves something a later one can pick up (plan §7.4). Holding progress
only in the worker's memory would make both impossible.

Each item names the call it came from and, once analysed, the call it produced.
That link is what lets a reader go from "item 89 failed" to the transcript that
failed, without matching on text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from domain.aggregation.run_progress import RunProgress, summarise
from domain.value_objects.run_status import RunItemStatus, RunStatus


@dataclass(frozen=True)
class CorpusRunItem:
    """One corpus call's place in a run."""

    source_id: str
    reference: str
    title: str
    status: RunItemStatus = RunItemStatus.PENDING
    call_id: int | None = None
    message: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: float | None = None

    def __post_init__(self) -> None:
        if self.status is RunItemStatus.COMPLETED and self.call_id is None:
            # A completed item with no call is a claim with nothing behind it;
            # the dashboard would count a call that cannot be opened.
            raise ValueError(f"Item {self.source_id!r} completed without a stored call.")
        if self.status in (RunItemStatus.FAILED, RunItemStatus.SKIPPED) and not self.message:
            raise ValueError(f"Item {self.source_id!r} is {self.status.value} without a reason.")


@dataclass(frozen=True)
class CorpusRun:
    """One pass over the corpus with a chosen provider and model."""

    id: int
    provider: str
    model: str
    force: bool
    status: RunStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    message: str = ""
    items: tuple[CorpusRunItem, ...] = field(default_factory=tuple)

    @property
    def progress(self) -> RunProgress:
        return summarise(item.status for item in self.items)

    @property
    def analysed_call_ids(self) -> tuple[int, ...]:
        return tuple(item.call_id for item in self.items if item.call_id is not None)

    @property
    def can_resume(self) -> bool:
        """Whether resuming this run would actually do anything.

        A run that ended with every item finished is not resumable even though it
        stopped early — offering "resume" there would produce a no-op that looks
        like a failure to the person who clicked it.
        """
        return self.status.is_resumable and any(item.status.needs_work for item in self.items)
