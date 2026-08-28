"""In-memory fan-out of run events to connected clients.

No broker, no Redis: a single-node POC with an in-process worker has nothing to
gain from one, and the port means a real queue later replaces this file alone.

The one rule this implementation must never break is that **publishing cannot
block**. It is called from inside the analysis loop, so a browser that has stopped
reading its socket must not be able to stall a run that has hours of work left.
Each subscriber therefore gets a bounded queue, and a subscriber that falls behind
loses its oldest events rather than applying back-pressure to the worker. Losing
them is safe: every event is written to the run record first, and each carries a
full progress snapshot, so the next one delivered brings the client back to the
truth.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from application.ports.run_events import RunEvent, RunEventBus

logger = logging.getLogger(__name__)

DEFAULT_BUFFER = 64


class InMemoryRunEventBus(RunEventBus):
    """Delivers run events to whoever is subscribed, in this process."""

    def __init__(self, buffer_size: int = DEFAULT_BUFFER) -> None:
        self._buffer_size = max(1, buffer_size)
        self._subscribers: dict[int, set[asyncio.Queue[RunEvent]]] = {}

    async def publish(self, event: RunEvent) -> None:
        for queue in list(self._subscribers.get(event.run_id, ())):
            _offer(queue, event)

    @asynccontextmanager
    async def subscribe(self, run_id: int) -> AsyncIterator[AsyncIterator[RunEvent]]:
        queue: asyncio.Queue[RunEvent] = asyncio.Queue(maxsize=self._buffer_size)
        self._subscribers.setdefault(run_id, set()).add(queue)
        try:
            yield _drain(queue)
        finally:
            watchers = self._subscribers.get(run_id)
            if watchers is not None:
                watchers.discard(queue)
                if not watchers:
                    # Otherwise the map grows by one empty set per run, forever.
                    del self._subscribers[run_id]

    @property
    def subscriber_count(self) -> int:
        """How many clients are watching, across all runs. Used by tests."""
        return sum(len(watchers) for watchers in self._subscribers.values())


def _offer(queue: asyncio.Queue[RunEvent], event: RunEvent) -> None:
    """Enqueue without ever waiting, dropping the oldest event if full."""
    try:
        queue.put_nowait(event)
        return
    except asyncio.QueueFull:
        pass

    # Drop the oldest event to make room. It was drained by the subscriber
    # between the two calls if this raises, which is the outcome we wanted anyway.
    with contextlib.suppress(asyncio.QueueEmpty):
        queue.get_nowait()

    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:  # pragma: no cover - refilled between the two calls
        logger.warning("Dropped a run event for a subscriber that is not keeping up.")


async def _drain(queue: asyncio.Queue[RunEvent]) -> AsyncIterator[RunEvent]:
    while True:
        yield await queue.get()
