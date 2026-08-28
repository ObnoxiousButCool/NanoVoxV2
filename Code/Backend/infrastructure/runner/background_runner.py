"""Runs corpus work in the background of the API process.

Two details here are the difference between working and appearing to work.

**Task references are held.** ``asyncio`` keeps only a weak reference to a task,
so a fire-and-forget ``create_task`` can be garbage collected mid-run — the
classic way a background job silently stops existing.

**Failures are logged.** A task that raises with nobody awaiting it produces
nothing but a "Task exception was never retrieved" warning at interpreter exit,
long after anyone could act on it. Every task gets a done-callback that records
what happened.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)


class BackgroundRunner:
    """Owns the in-process tasks working corpus runs."""

    def __init__(self) -> None:
        self._tasks: dict[int, asyncio.Task[None]] = {}

    def start(self, run_id: int, work: Coroutine[Any, Any, None]) -> bool:
        """Begin working a run. Returns False if one is already in flight here.

        The coroutine is closed rather than left unawaited when the start is
        refused: an un-awaited coroutine is a resource leak and a warning at exit.
        """
        if self.is_working(run_id):
            work.close()
            return False

        task = asyncio.create_task(work, name=f"corpus-run-{run_id}")
        self._tasks[run_id] = task
        task.add_done_callback(lambda finished: self._finished(run_id, finished))
        return True

    def is_working(self, run_id: int) -> bool:
        task = self._tasks.get(run_id)
        return task is not None and not task.done()

    @property
    def active_run_ids(self) -> tuple[int, ...]:
        return tuple(run_id for run_id in self._tasks if self.is_working(run_id))

    async def shutdown(self) -> None:
        """Stop every task, waiting for each to unwind.

        Called at application shutdown. The run record is left as the database has
        it; startup marks anything still active as interrupted, which is exactly
        what happened.
        """
        tasks = [task for task in self._tasks.values() if not task.done()]
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                logger.info("Corpus run task cancelled at shutdown: %s", task.get_name())
            except Exception:  # pragma: no cover - defensive, already logged
                logger.exception("Corpus run task failed while shutting down.")
        self._tasks.clear()

    def _finished(self, run_id: int, task: asyncio.Task[None]) -> None:
        self._tasks.pop(run_id, None)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error("Corpus run %s stopped with an error.", run_id, exc_info=error)
