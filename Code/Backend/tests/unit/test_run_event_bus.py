"""The progress channel.

The rule that matters most is that publishing never blocks. The worker publishes
from inside the analysis loop, so a browser that stopped reading its socket must
not be able to stall a run with hours of work left.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import pytest

from application.ports.run_events import RunEvent, RunEventKind
from domain.aggregation.run_progress import RunProgress
from domain.entities.corpus_run import CorpusRunItem
from domain.value_objects.run_status import RunItemStatus, RunStatus
from frameworks_drivers.api.v1.corpus import HEARTBEAT_FRAME, _frame, sse_frames
from infrastructure.runner.event_bus import InMemoryRunEventBus

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
PROGRESS = RunProgress(
    total=3, completed=1, failed=0, skipped=0, cancelled=0, running=1, pending=1
)


def event(run_id: int = 1, kind: RunEventKind = RunEventKind.ITEM_FINISHED) -> RunEvent:
    return RunEvent(
        run_id=run_id,
        kind=kind,
        at=NOW,
        run_status=RunStatus.RUNNING,
        progress=PROGRESS,
    )


async def anext_frame(frames: AsyncIterator[str], timeout: float = 2.0) -> str:
    """The next SSE frame, with a timeout so a hang fails rather than blocks."""
    return await asyncio.wait_for(frames.__anext__(), timeout)


async def next_event(stream: object, timeout: float = 1.0) -> RunEvent:
    received = await asyncio.wait_for(stream.__anext__(), timeout)  # type: ignore[attr-defined]
    assert isinstance(received, RunEvent)
    return received


class TestDelivery:
    async def test_a_subscriber_receives_what_is_published(self) -> None:
        bus = InMemoryRunEventBus()

        async with bus.subscribe(1) as stream:
            await bus.publish(event())

            assert (await next_event(stream)).kind is RunEventKind.ITEM_FINISHED

    async def test_two_watchers_of_one_run_both_receive_it(self) -> None:
        bus = InMemoryRunEventBus()

        async with bus.subscribe(1) as first, bus.subscribe(1) as second:
            await bus.publish(event())

            assert (await next_event(first)).run_id == 1
            assert (await next_event(second)).run_id == 1

    async def test_events_do_not_cross_between_runs(self) -> None:
        bus = InMemoryRunEventBus()

        async with bus.subscribe(1) as first, bus.subscribe(2) as second:
            await bus.publish(event(run_id=2))

            assert (await next_event(second)).run_id == 2
            with pytest.raises(asyncio.TimeoutError):
                await next_event(first, timeout=0.05)

    async def test_publishing_with_nobody_watching_is_harmless(self) -> None:
        # A run with no browser attached is the normal case, not an error.
        await InMemoryRunEventBus().publish(event())


class TestBackPressure:
    async def test_a_subscriber_that_stops_reading_cannot_stall_the_worker(self) -> None:
        bus = InMemoryRunEventBus(buffer_size=2)

        async with bus.subscribe(1):
            for _ in range(50):
                # Would deadlock the run if publish ever waited for capacity.
                await asyncio.wait_for(bus.publish(event()), timeout=1.0)

    async def test_a_slow_subscriber_loses_the_oldest_events_not_the_newest(self) -> None:
        # Every event carries a full progress snapshot, so the newest one brings
        # the client back to the truth. The stale ones are what to drop.
        bus = InMemoryRunEventBus(buffer_size=1)

        async with bus.subscribe(1) as stream:
            await bus.publish(event(kind=RunEventKind.ITEM_STARTED))
            await bus.publish(event(kind=RunEventKind.RUN_FINISHED))

            assert (await next_event(stream)).kind is RunEventKind.RUN_FINISHED


class TestSubscriptionLifetime:
    async def test_leaving_the_context_stops_the_subscription(self) -> None:
        bus = InMemoryRunEventBus()

        async with bus.subscribe(1):
            assert bus.subscriber_count == 1

        assert bus.subscriber_count == 0

    async def test_the_last_watcher_leaving_clears_the_run_entirely(self) -> None:
        # Otherwise the map grows by one empty set per run, forever.
        bus = InMemoryRunEventBus()

        async with bus.subscribe(1), bus.subscribe(1):
            pass

        assert bus.subscriber_count == 0
        await bus.publish(event())


class TestSseFrames:
    """The wire format the browser's EventSource parses.

    Checked here rather than through a client because the frame is the contract:
    a missing blank line or a renamed event type breaks every subscriber, and
    neither shows up as a failed request.
    """

    def test_a_frame_names_its_event_and_carries_json(self) -> None:
        frame = _frame(event(kind=RunEventKind.ITEM_FINISHED))

        assert frame.startswith("event: item_finished\ndata: ")
        # Two newlines terminate an SSE frame. One is a frame nobody receives.
        assert frame.endswith("\n\n")

    def test_the_payload_carries_the_progress_at_that_moment(self) -> None:
        # A client that missed an event catches up from the next one.
        payload = json.loads(_frame(event()).split("data: ", 1)[1])

        assert payload["progress"]["total"] == 3
        assert payload["progress"]["completed"] == 1
        assert payload["run_status"] == "RUNNING"

    def test_an_item_is_reported_with_the_call_it_produced(self) -> None:
        finished = RunEvent(
            run_id=1,
            kind=RunEventKind.ITEM_FINISHED,
            at=NOW,
            run_status=RunStatus.RUNNING,
            progress=PROGRESS,
            item=CorpusRunItem(
                source_id="call_089",
                reference="C0089",
                title="Fixture",
                status=RunItemStatus.COMPLETED,
                call_id=7,
                started_at=NOW,
                finished_at=NOW,
                duration_ms=1234.0,
            ),
        )

        payload = json.loads(_frame(finished).split("data: ", 1)[1])

        assert payload["item"]["reference"] == "C0089"
        assert payload["item"]["call_id"] == 7
        # Datetimes have to survive as strings, or json.dumps raises and the
        # stream dies mid-run.
        assert payload["item"]["finished_at"].startswith("2026-08-28")

    def test_an_event_with_no_item_says_so_rather_than_omitting_the_key(self) -> None:
        # The client reads `item` on every frame; a missing key is a crash.
        payload = json.loads(_frame(event(kind=RunEventKind.SNAPSHOT)).split("data: ", 1)[1])

        assert payload["item"] is None


class TestHeartbeats:
    """A keep-alive must not be the last thing a client ever receives.

    Analysing one call takes minutes, so an idle stream is the normal state and
    heartbeats are what keep the connection alive through it. The first version
    of this loop used ``asyncio.wait_for``, which cancels the awaited
    ``__anext__`` on timeout and closes the underlying async generator — every
    stream went silent after fifteen seconds while the run carried on working.
    """

    async def test_events_still_arrive_after_a_keep_alive(self) -> None:
        bus = InMemoryRunEventBus()

        async with bus.subscribe(1) as stream:
            frames = sse_frames(stream, event(kind=RunEventKind.SNAPSHOT), 0.01)

            assert "snapshot" in await anext_frame(frames)
            assert await anext_frame(frames) == HEARTBEAT_FRAME

            await bus.publish(event(kind=RunEventKind.RUN_FINISHED))

            frame = await anext_frame(frames)
            assert "run_finished" in frame

    async def test_the_stream_ends_when_the_run_does(self) -> None:
        bus = InMemoryRunEventBus()

        async with bus.subscribe(1) as stream:
            frames = sse_frames(stream, event(kind=RunEventKind.SNAPSHOT), 5.0)
            await anext_frame(frames)
            await bus.publish(event(kind=RunEventKind.RUN_FINISHED))
            await anext_frame(frames)

            with pytest.raises(StopAsyncIteration):
                await frames.__anext__()

    async def test_many_quiet_periods_do_not_end_the_stream(self) -> None:
        # A run of a hundred local-model calls is mostly silence.
        bus = InMemoryRunEventBus()

        async with bus.subscribe(1) as stream:
            frames = sse_frames(stream, event(kind=RunEventKind.SNAPSHOT), 0.01)
            await anext_frame(frames)

            for _ in range(5):
                assert await anext_frame(frames) == HEARTBEAT_FRAME

            await bus.publish(event(kind=RunEventKind.ITEM_FINISHED))
            assert "item_finished" in await anext_frame(frames)
