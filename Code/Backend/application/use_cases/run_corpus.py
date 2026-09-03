"""Re-analyse the authored corpus with live progress (DEC-06, plan §7.4).

Three things make this more than a loop over a hundred transcripts.

**It is resumable.** Every item's outcome is written as it happens, so a refresh,
a cancel or a crash leaves a record that says exactly what was done. Nothing about
the run's progress lives only in the worker's memory.

**It is idempotent.** A call that already has an analysis is skipped with a reason
rather than analysed twice. ``force`` replaces instead, and replacement deletes
the old call first — leaving both would double every figure on the dashboard.

**One failure is not a failed run.** A call that fails is recorded as failed, with
the reason, and the run carries on. Ninety-nine analysed calls are worth having;
abandoning them because the hundredth timed out is not a trade anyone would take.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from application.ports.analysis_repository import AnalysisRepository
from application.ports.clock import Clock
from application.ports.corpus_source import CorpusSource
from application.ports.ground_truth_repository import GroundTruthRepository
from application.ports.llm_provider import LLMProvider
from application.ports.run_events import RunEvent, RunEventBus, RunEventKind
from application.ports.run_repository import RunRepository
from application.use_cases.analyze_transcript import AnalyzeTranscript, AnalyzeTranscriptCommand
from domain.entities.analysis import AnalysisSource
from domain.entities.corpus_call import CorpusCall
from domain.entities.corpus_run import CorpusRun, CorpusRunItem
from domain.errors import ConflictError, NanoVoxError, NotFoundError, ValidationError
from domain.value_objects.run_status import RunItemStatus, RunStatus

SKIPPED_ALREADY_ANALYSED = "Already analysed. Re-run with force to replace it."
CANCELLED_BY_OPERATOR = "Cancelled before this call was analysed."
INTERRUPTED_REASON = "The process stopped while this run was working."


@dataclass(frozen=True)
class StartRunCommand:
    """A request to analyse the corpus."""

    provider: str
    model: str
    force: bool = False
    acknowledge_cost: bool = False


class StartCorpusRun:
    """Creates a run record and its per-call items.

    Starting and working are separate steps on purpose: the caller gets a run id
    it can watch immediately, rather than an HTTP request held open for the hours
    the work actually takes.
    """

    def __init__(
        self,
        *,
        corpus: CorpusSource,
        runs: RunRepository,
        ground_truth: GroundTruthRepository,
        clock: Clock,
    ) -> None:
        self._corpus = corpus
        self._runs = runs
        self._ground_truth = ground_truth
        self._clock = clock

    async def execute(self, command: StartRunCommand, *, billable: bool) -> CorpusRun:
        if billable and not command.acknowledge_cost:
            # The guard rail is enforced here rather than drawn in the UI. A
            # confirmation dialog that the API does not require is decoration:
            # any other client, or a stale page, would spend the money anyway.
            raise ValidationError(
                "This run would send every corpus call to a paid provider.",
                detail=(
                    f"Provider {command.provider!r} bills per token, and a run analyses the "
                    "whole corpus five times over — once per layer. Resend with "
                    "acknowledge_cost set to confirm."
                ),
            )

        active = await self._runs.active()
        if active is not None:
            raise ConflictError(
                "A corpus run is already in progress.",
                detail=(
                    f"Run {active.id} is {active.status.value}. Cancel it before starting "
                    "another — two runs over one corpus would double the model spend and "
                    "race for the same call references."
                ),
            )

        calls = self._corpus.load()
        # Ground truth is stored at the start, not at the end: it is what the
        # files said when the run began, and it is what a fidelity report has to
        # compare against even if the run is cancelled halfway.
        await self._ground_truth.upsert_many(calls)

        return await self._runs.create(
            provider=command.provider,
            model=command.model,
            force=command.force,
            calls=calls,
            now=self._clock.now(),
        )


class CancelCorpusRun:
    """Requests cooperative cancellation of a live run."""

    def __init__(self, *, runs: RunRepository, clock: Clock) -> None:
        self._runs = runs
        self._clock = clock

    async def execute(self, run_id: int) -> CorpusRun:
        run = await self._require(run_id)
        if run.status.is_terminal:
            raise ConflictError(
                f"Run {run_id} has already finished.",
                detail=f"Its status is {run.status.value}.",
            )

        # CANCELLING, not CANCELLED. The call in flight is left to finish rather
        # than abandoned mid-analysis, which would leave a half-written call.
        await self._runs.set_status(
            run_id, RunStatus.CANCELLING, now=self._clock.now(), message="Cancelled by operator."
        )
        return await self._require(run_id)

    async def _require(self, run_id: int) -> CorpusRun:
        run = await self._runs.get(run_id)
        if run is None:
            raise NotFoundError(f"There is no corpus run {run_id}.")
        return run


class ResumeCorpusRun:
    """Returns unfinished items to pending so a stopped run can continue."""

    def __init__(self, *, runs: RunRepository, clock: Clock) -> None:
        self._runs = runs
        self._clock = clock

    async def execute(self, run_id: int) -> CorpusRun:
        run = await self._runs.get(run_id)
        if run is None:
            raise NotFoundError(f"There is no corpus run {run_id}.")
        if run.status.is_active:
            raise ConflictError(
                f"Run {run_id} is still working.",
                detail="Wait for it to stop, or cancel it, before resuming.",
            )
        if not run.can_resume:
            raise ConflictError(
                f"Run {run_id} has nothing left to do.",
                detail=(
                    f"Every one of its {run.progress.total} items has finished. "
                    "Start a new run to analyse the corpus again."
                ),
            )

        active = await self._runs.active()
        if active is not None:
            raise ConflictError(
                "A corpus run is already in progress.",
                detail=f"Run {active.id} is {active.status.value}.",
            )

        now = self._clock.now()
        await self._runs.requeue_unfinished(run_id, now=now)
        await self._runs.set_status(run_id, RunStatus.PENDING, now=now, message="Resumed.")
        resumed = await self._runs.get(run_id)
        if resumed is None:  # pragma: no cover - the row was just updated
            raise NotFoundError(f"There is no corpus run {run_id}.")
        return resumed


class CorpusRunWorker:
    """Analyses every pending call in a run, one bounded batch at a time."""

    def __init__(
        self,
        *,
        corpus: CorpusSource,
        runs: RunRepository,
        analyses: AnalysisRepository,
        analyze: AnalyzeTranscript,
        events: RunEventBus,
        clock: Clock,
        concurrency: int,
    ) -> None:
        self._corpus = corpus
        self._runs = runs
        self._analyses = analyses
        self._analyze = analyze
        self._events = events
        self._clock = clock
        self._concurrency = max(1, concurrency)

    async def execute(self, run_id: int, provider: LLMProvider) -> None:
        """Work the run to completion, or until it is cancelled."""
        run = await self._runs.get(run_id)
        if run is None:
            raise NotFoundError(f"There is no corpus run {run_id}.")

        # Only a pending run is moved to running. A cancel can land between the
        # request that created the run and this first write — writing RUNNING
        # unconditionally would erase it, and the run would work on regardless.
        if run.status is RunStatus.PENDING:
            await self._runs.set_status(run_id, RunStatus.RUNNING, now=self._clock.now())

        try:
            calls = {call.source_id: call for call in self._corpus.load()}
            pending = [item for item in run.items if item.status is RunItemStatus.PENDING]
            workable = await self._resolve_skips(run_id, pending, run.force)
            await self._analyse_all(run_id, workable, calls, provider)
            await self._finish(run_id)
        except NanoVoxError as exc:
            # A failure out here is the run's own — an unreadable corpus, a
            # database that has gone away — not one call's. It ends the run.
            await self._runs.set_status(
                run_id, RunStatus.FAILED, now=self._clock.now(), message=exc.message
            )
            await self._publish(run_id, RunEventKind.RUN_FINISHED, message=exc.message)
            raise

    # --- steps -------------------------------------------------------------

    async def _resolve_skips(
        self, run_id: int, pending: Sequence[CorpusRunItem], force: bool
    ) -> list[CorpusRunItem]:
        """Mark already-analysed calls as skipped, or clear the way to replace them."""
        stored = await self._analyses.existing_references([item.reference for item in pending])
        if not stored:
            return list(pending)

        workable: list[CorpusRunItem] = []
        for item in pending:
            if item.reference not in stored:
                workable.append(item)
                continue
            if not force:
                await self._runs.set_item_status(
                    run_id,
                    item.source_id,
                    RunItemStatus.SKIPPED,
                    now=self._clock.now(),
                    message=SKIPPED_ALREADY_ANALYSED,
                )
                continue
            # Replace, never duplicate: the reference is unique, and a second row
            # for the same call would count twice in every dashboard figure.
            await self._analyses.delete_by_reference(item.reference)
            workable.append(item)
        return workable

    async def _analyse_all(
        self,
        run_id: int,
        items: Sequence[CorpusRunItem],
        calls: dict[str, CorpusCall],
        provider: LLMProvider,
    ) -> None:
        semaphore = asyncio.Semaphore(self._concurrency)
        cancelled = False

        async def work(item: CorpusRunItem) -> None:
            nonlocal cancelled
            async with semaphore:
                if cancelled or await self._is_cancelling(run_id):
                    cancelled = True
                    await self._runs.set_item_status(
                        run_id,
                        item.source_id,
                        RunItemStatus.CANCELLED,
                        now=self._clock.now(),
                        message=CANCELLED_BY_OPERATOR,
                    )
                    return
                await self._analyse_one(run_id, item, calls.get(item.source_id), provider)

        # gather rather than a loop so the semaphore, not the iteration, sets the
        # concurrency. Every task handles its own errors, so none can cancel the
        # others by raising.
        await asyncio.gather(*(work(item) for item in items))

    async def _analyse_one(
        self,
        run_id: int,
        item: CorpusRunItem,
        call: CorpusCall | None,
        provider: LLMProvider,
    ) -> None:
        now = self._clock.now()
        if call is None:
            # The corpus changed under a resumed run.
            await self._runs.set_item_status(
                run_id,
                item.source_id,
                RunItemStatus.FAILED,
                now=now,
                message=f"{item.source_id} is no longer in the corpus.",
            )
            await self._publish(run_id, RunEventKind.ITEM_FINISHED, source_id=item.source_id)
            return

        await self._runs.set_item_status(run_id, item.source_id, RunItemStatus.RUNNING, now=now)
        await self._publish(run_id, RunEventKind.ITEM_STARTED, source_id=item.source_id)

        started = self._clock.now()
        try:
            stored = await self._analyze.execute(
                AnalyzeTranscriptCommand(
                    transcript=call.transcript,
                    source=AnalysisSource.CORPUS_RUN,
                    reference=call.reference,
                    duration_minutes=call.duration_minutes,
                ),
                provider,
            )
        except NanoVoxError as exc:
            await self._runs.set_item_status(
                run_id,
                item.source_id,
                RunItemStatus.FAILED,
                now=self._clock.now(),
                message=exc.message,
                duration_ms=self._elapsed_ms(started),
            )
        else:
            await self._runs.set_item_status(
                run_id,
                item.source_id,
                RunItemStatus.COMPLETED,
                now=self._clock.now(),
                call_id=stored.call_id,
                duration_ms=self._elapsed_ms(started),
            )

        await self._publish(run_id, RunEventKind.ITEM_FINISHED, source_id=item.source_id)

    async def _finish(self, run_id: int) -> None:
        """Settle the run's final status from what its items actually did."""
        run = await self._runs.get(run_id)
        if run is None:  # pragma: no cover - defensive
            return

        progress = run.progress
        cancelling = run.status is RunStatus.CANCELLING
        if cancelling or progress.cancelled > 0:
            status, message = RunStatus.CANCELLED, "Cancelled by operator."
        elif progress.failed > 0 and progress.completed == 0 and progress.skipped == 0:
            # Nothing came out of it. Reporting that as "completed" would be a lie
            # told by a green progress bar.
            status, message = RunStatus.FAILED, f"All {progress.failed} calls failed."
        else:
            status, message = RunStatus.COMPLETED, _completion_message(run)

        await self._runs.set_status(run_id, status, now=self._clock.now(), message=message)
        await self._publish(run_id, RunEventKind.RUN_FINISHED, message=message)

    # --- helpers -----------------------------------------------------------

    async def _is_cancelling(self, run_id: int) -> bool:
        status = await self._runs.status_of(run_id)
        return status is None or status is RunStatus.CANCELLING

    def _elapsed_ms(self, started: datetime) -> float:
        return (self._clock.now() - started).total_seconds() * 1000

    async def _publish(
        self,
        run_id: int,
        kind: RunEventKind,
        *,
        source_id: str | None = None,
        message: str = "",
    ) -> None:
        """Broadcast the run's current state, read back from the record.

        Read back rather than assembled in memory so a subscriber can never be
        shown a figure the database does not hold.
        """
        run = await self._runs.get(run_id)
        if run is None:  # pragma: no cover - defensive
            return
        item = next((entry for entry in run.items if entry.source_id == source_id), None)
        await self._events.publish(
            RunEvent(
                run_id=run_id,
                kind=kind,
                at=self._clock.now(),
                run_status=run.status,
                progress=run.progress,
                item=item,
                message=message,
            )
        )


def _completion_message(run: CorpusRun) -> str:
    progress = run.progress
    parts = [f"{progress.completed} analysed"]
    if progress.skipped:
        parts.append(f"{progress.skipped} skipped")
    if progress.failed:
        parts.append(f"{progress.failed} failed")
    return ", ".join(parts) + "."


class GetCorpusRun:
    """Loads one run for display."""

    def __init__(self, runs: RunRepository) -> None:
        self._runs = runs

    async def execute(self, run_id: int) -> CorpusRun:
        run = await self._runs.get(run_id)
        if run is None:
            raise NotFoundError(f"There is no corpus run {run_id}.")
        return run


class ListCorpusRuns:
    """Lists recent runs, newest first."""

    def __init__(self, runs: RunRepository) -> None:
        self._runs = runs

    async def execute(self, limit: int = 20) -> tuple[CorpusRun, ...]:
        return await self._runs.recent(limit)


@dataclass(frozen=True)
class CorpusStatus:
    """What is in the corpus, and how much of it has been analysed."""

    location: str
    total_calls: int
    analysed_calls: int
    active_run_id: int | None

    @property
    def outstanding(self) -> int:
        return max(0, self.total_calls - self.analysed_calls)


class GetCorpusStatus:
    """Reports corpus size against what is already stored.

    Answers the question the run screen opens with — "is there anything to do?" —
    without starting anything.
    """

    def __init__(
        self, *, corpus: CorpusSource, analyses: AnalysisRepository, runs: RunRepository
    ) -> None:
        self._corpus = corpus
        self._analyses = analyses
        self._runs = runs

    async def execute(self) -> CorpusStatus:
        calls = self._corpus.load()
        stored = await self._analyses.existing_references([call.reference for call in calls])
        active = await self._runs.active()
        return CorpusStatus(
            location=self._corpus.describe(),
            total_calls=len(calls),
            analysed_calls=len(stored),
            active_run_id=active.id if active is not None else None,
        )
