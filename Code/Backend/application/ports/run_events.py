"""Port for live progress from a corpus run.

Progress is broadcast, not polled, because a hundred calls at several minutes each
is a long time to watch a spinner that says nothing. The bus is deliberately
*advisory*: every event it carries is also written to the run record first, so a
dropped subscriber, a slow client or a restarted process loses nothing but
immediacy. Nothing in the system reads its state back from this channel.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from domain.aggregation.run_progress import RunProgress
from domain.entities.corpus_run import CorpusRunItem
from domain.value_objects.run_status import RunStatus


class RunEventKind(str, Enum):
    """What happened.

    ``SNAPSHOT`` is sent to every new subscriber before any live event. A client
    that attaches halfway through a run would otherwise see an empty screen until
    the next call finished — which, at several minutes per call, reads as broken.
    """

    SNAPSHOT = "snapshot"
    ITEM_STARTED = "item_started"
    ITEM_FINISHED = "item_finished"
    RUN_FINISHED = "run_finished"


@dataclass(frozen=True)
class RunEvent:
    """One thing that happened in a run, with the state it left behind."""

    run_id: int
    kind: RunEventKind
    at: datetime
    run_status: RunStatus
    progress: RunProgress
    item: CorpusRunItem | None = None
    message: str = ""


class RunEventBus(ABC):
    """Fan-out of run events to whoever is currently watching."""

    @abstractmethod
    async def publish(self, event: RunEvent) -> None:
        """Deliver an event to every current subscriber.

        Must never raise or block on a slow subscriber: the worker publishes from
        inside the analysis loop, and a stalled browser must not stall the run.
        """

    @abstractmethod
    def subscribe(self, run_id: int) -> AbstractAsyncContextManager[AsyncIterator[RunEvent]]:
        """Watch one run until the context exits."""
