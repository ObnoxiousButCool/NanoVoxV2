"""Run state and the progress derived from it.

The rules here decide what a progress bar claims, so each one is a statement
about honesty rather than arithmetic: a skipped call is not an analysed one, a
cancelled run is not a failed one, and a run nobody can resume must not offer to.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from domain.aggregation.run_progress import summarise
from domain.entities.corpus_run import CorpusRun, CorpusRunItem
from domain.value_objects.run_status import RunItemStatus, RunStatus

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)

COMPLETED = RunItemStatus.COMPLETED
FAILED = RunItemStatus.FAILED
SKIPPED = RunItemStatus.SKIPPED
PENDING = RunItemStatus.PENDING
RUNNING = RunItemStatus.RUNNING
CANCELLED = RunItemStatus.CANCELLED


def item(status: RunItemStatus, source_id: str = "call_001") -> CorpusRunItem:
    return CorpusRunItem(
        source_id=source_id,
        reference="C0001",
        title="Test",
        status=status,
        call_id=1 if status is COMPLETED else None,
        message="reason" if status in (FAILED, SKIPPED) else "",
    )


def run(*statuses: RunItemStatus, status: RunStatus = RunStatus.COMPLETED) -> CorpusRun:
    return CorpusRun(
        id=1,
        provider="ollama",
        model="test",
        force=False,
        status=status,
        created_at=NOW,
        items=tuple(item(value, f"call_{index:03d}") for index, value in enumerate(statuses)),
    )


class TestProgress:
    def test_the_four_outcomes_are_counted_separately(self) -> None:
        # A run that skipped ninety and analysed ten is not the same event as one
        # that analysed a hundred.
        progress = summarise([COMPLETED, COMPLETED, SKIPPED, FAILED, PENDING])

        assert progress.total == 5
        assert (progress.completed, progress.skipped, progress.failed) == (2, 1, 1)
        assert progress.remaining == 1

    def test_percent_counts_every_resting_item_not_only_successes(self) -> None:
        progress = summarise([COMPLETED, SKIPPED, FAILED, PENDING])

        assert progress.percent_complete == 75.0

    def test_an_empty_run_is_finished_rather_than_stalled_at_zero(self) -> None:
        # There is nothing left to do; showing 0% would report a problem.
        progress = summarise([])

        assert progress.percent_complete == 100.0
        assert progress.is_exhausted

    def test_a_running_item_is_not_yet_finished(self) -> None:
        progress = summarise([COMPLETED, RUNNING])

        assert progress.finished == 1
        assert not progress.is_exhausted


class TestRunStatus:
    @pytest.mark.parametrize(
        "status",
        [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.INTERRUPTED],
    )
    def test_terminal_states_are_not_active(self, status: RunStatus) -> None:
        assert status.is_terminal
        assert not status.is_active

    @pytest.mark.parametrize("status", [RunStatus.PENDING, RunStatus.RUNNING, RunStatus.CANCELLING])
    def test_a_cancelling_run_still_counts_as_working(self, status: RunStatus) -> None:
        # It has a call in flight, so a second run must still be refused.
        assert status.is_active
        assert not status.is_terminal

    def test_a_completed_run_is_not_resumable(self) -> None:
        assert not RunStatus.COMPLETED.is_resumable

    @pytest.mark.parametrize(
        "status", [RunStatus.CANCELLED, RunStatus.FAILED, RunStatus.INTERRUPTED]
    )
    def test_a_stopped_run_can_be_picked_up_again(self, status: RunStatus) -> None:
        # Cancelling is a pause the operator chose; refusing to continue it would
        # make cancel a destructive act.
        assert status.is_resumable


class TestItemStatus:
    def test_a_failed_item_is_retried_and_a_skipped_one_is_not(self) -> None:
        # Skipping was a decision about the item; failing was an accident.
        assert RunItemStatus.FAILED.needs_work
        assert not RunItemStatus.SKIPPED.needs_work

    def test_an_item_left_running_by_a_dead_process_is_retried(self) -> None:
        assert RunItemStatus.RUNNING.needs_work


class TestResumability:
    def test_a_cancelled_run_with_work_left_can_resume(self) -> None:
        subject = run(COMPLETED, PENDING, status=RunStatus.CANCELLED)

        assert subject.can_resume

    def test_a_cancelled_run_that_finished_everything_cannot(self) -> None:
        # Offering resume here produces a no-op that reads as a failure.
        subject = run(COMPLETED, SKIPPED, status=RunStatus.CANCELLED)

        assert not subject.can_resume

    def test_a_completed_run_never_offers_to_resume(self) -> None:
        assert not run(COMPLETED, status=RunStatus.COMPLETED).can_resume


class TestItemInvariants:
    def test_a_completed_item_must_name_the_call_it_produced(self) -> None:
        # Otherwise the dashboard counts a call nobody can open.
        with pytest.raises(ValueError, match="without a stored call"):
            CorpusRunItem(source_id="call_001", reference="C0001", title="Test", status=COMPLETED)

    @pytest.mark.parametrize("status", [FAILED, SKIPPED])
    def test_a_failure_or_a_skip_must_say_why(self, status: RunItemStatus) -> None:
        with pytest.raises(ValueError, match="without a reason"):
            CorpusRunItem(source_id="call_001", reference="C0001", title="Test", status=status)

    def test_the_calls_a_run_produced_are_listed(self) -> None:
        subject = run(COMPLETED, FAILED, COMPLETED)

        assert subject.analysed_call_ids == (1, 1)
