"""Persistence port for corpus runs.

Every method here writes or reads the run record that makes a run resumable, so
each is a small, immediately-committed change rather than part of a long
transaction. A run that held its progress open until the end would lose all of it
in exactly the situation the record exists for.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime

from domain.entities.corpus_call import CorpusCall
from domain.entities.corpus_run import CorpusRun
from domain.value_objects.run_status import RunItemStatus, RunStatus


class RunRepository(ABC):
    """Stores corpus runs and their per-call items."""

    @abstractmethod
    async def create(
        self,
        *,
        provider: str,
        model: str,
        force: bool,
        calls: Sequence[CorpusCall],
        now: datetime,
    ) -> CorpusRun:
        """Record a new run with one pending item per corpus call."""

    @abstractmethod
    async def get(self, run_id: int) -> CorpusRun | None:
        """Load a run with its items, or ``None`` if there is no such run."""

    @abstractmethod
    async def status_of(self, run_id: int) -> RunStatus | None:
        """Just the run's status.

        The worker checks this between calls to notice a cancellation, so it must
        not cost a full load of the run and its hundred items — and it must read
        the database rather than any in-memory flag, so a cancel issued by a
        different request is seen.
        """

    @abstractmethod
    async def recent(self, limit: int) -> tuple[CorpusRun, ...]:
        """Load recent runs, newest first."""

    @abstractmethod
    async def active(self) -> CorpusRun | None:
        """The run currently working, if any.

        Used to refuse a second concurrent run: two workers over one corpus would
        race for the same references and double the model spend.
        """

    @abstractmethod
    async def set_status(
        self,
        run_id: int,
        status: RunStatus,
        *,
        now: datetime,
        message: str = "",
    ) -> None:
        """Move a run to a new status, stamping the matching timestamp."""

    @abstractmethod
    async def set_item_status(
        self,
        run_id: int,
        source_id: str,
        status: RunItemStatus,
        *,
        now: datetime,
        call_id: int | None = None,
        message: str = "",
        duration_ms: float | None = None,
    ) -> None:
        """Record an item's outcome."""

    @abstractmethod
    async def requeue_unfinished(self, run_id: int, *, now: datetime) -> int:
        """Return unfinished items to pending for a resume, and report how many."""

    @abstractmethod
    async def delete_all(self) -> int:
        """Remove every run and its items, returning how many runs went."""

    @abstractmethod
    async def abandon_active(self, *, now: datetime, reason: str) -> int:
        """Mark runs left active by a dead process as interrupted.

        Called at startup. An in-process worker cannot survive a restart, so a run
        still marked ``RUNNING`` is describing a worker that no longer exists —
        and the UI would show it as live forever.
        """
