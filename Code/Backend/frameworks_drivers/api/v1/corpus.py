"""Corpus run endpoints (DEC-06, plan §7.4).

Starting a run returns immediately with a run id. The work happens on a
background task in this process and reports through Server-Sent Events, because
a hundred calls at minutes each is not something to hold an HTTP request open
for — and a request that did would die at the first proxy timeout, with the run
still running and nothing watching it.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from application.ports.llm_provider import LLMProvider
from application.ports.run_events import RunEvent, RunEventKind
from application.use_cases.import_corpus_document import (
    CorpusImport,
    ImportDocumentCommand,
)
from application.use_cases.run_corpus import CorpusStatus, StartRunCommand
from domain.aggregation.run_progress import RunProgress
from domain.entities.corpus_run import CorpusRun, CorpusRunItem
from frameworks_drivers.api.dependencies import (
    CancelCorpusRunDep,
    ClearCorpusDep,
    ContainerDep,
    CorpusStatusDep,
    GetCorpusRunDep,
    ImportCorpusDocumentDep,
    ListCorpusRunsDep,
    ResumeCorpusRunDep,
    StartCorpusRunDep,
)
from frameworks_drivers.container import Container

router = APIRouter(tags=["corpus"])

# A comment line every fifteen seconds. Analysing one call takes minutes, so
# without it the connection looks idle to anything sitting in the middle and gets
# closed as dead exactly when the run is working hardest.
HEARTBEAT_SECONDS = 15.0
HEARTBEAT_FRAME = ": keep-alive\n\n"


class StartRunRequest(BaseModel):
    provider: str | None = Field(
        default=None, description="Provider name. Defaults to the configured provider."
    )
    model: str | None = Field(default=None, description="Model override for this run.")
    force: bool = Field(
        default=False,
        description="Re-analyse calls that already have an analysis, replacing them.",
    )
    acknowledge_cost: bool = Field(
        default=False,
        description="Required to run against a provider that charges per token.",
    )


class ProgressResponse(BaseModel):
    total: int
    completed: int
    failed: int
    skipped: int
    cancelled: int
    running: int
    pending: int
    finished: int
    remaining: int
    percent_complete: float


class RunItemResponse(BaseModel):
    source_id: str
    reference: str
    title: str
    status: str
    call_id: int | None
    message: str
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: float | None


class RunSummaryResponse(BaseModel):
    id: int
    provider: str
    model: str
    force: bool
    status: str
    message: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    is_active: bool
    can_resume: bool
    progress: ProgressResponse


class RunResponse(RunSummaryResponse):
    items: list[RunItemResponse]


class CorpusStatusResponse(BaseModel):
    location: str = Field(description="Where the corpus is read from.")
    total_calls: int
    analysed_calls: int
    outstanding: int
    active_run_id: int | None


def _progress(progress: RunProgress) -> ProgressResponse:
    return ProgressResponse(
        total=progress.total,
        completed=progress.completed,
        failed=progress.failed,
        skipped=progress.skipped,
        cancelled=progress.cancelled,
        running=progress.running,
        pending=progress.pending,
        finished=progress.finished,
        remaining=progress.remaining,
        percent_complete=progress.percent_complete,
    )


def _item(item: CorpusRunItem) -> RunItemResponse:
    return RunItemResponse(
        source_id=item.source_id,
        reference=item.reference,
        title=item.title,
        status=item.status.value,
        call_id=item.call_id,
        message=item.message,
        started_at=item.started_at,
        finished_at=item.finished_at,
        duration_ms=item.duration_ms,
    )


def _summary(run: CorpusRun) -> RunSummaryResponse:
    return RunSummaryResponse(
        id=run.id,
        provider=run.provider,
        model=run.model,
        force=run.force,
        status=run.status.value,
        message=run.message,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        is_active=run.status.is_active,
        can_resume=run.can_resume,
        progress=_progress(run.progress),
    )


def to_response(run: CorpusRun) -> RunResponse:
    return RunResponse(
        **_summary(run).model_dump(),
        items=[_item(item) for item in run.items],
    )


def _status_response(status_: CorpusStatus) -> CorpusStatusResponse:
    return CorpusStatusResponse(
        location=status_.location,
        total_calls=status_.total_calls,
        analysed_calls=status_.analysed_calls,
        outstanding=status_.outstanding,
        active_run_id=status_.active_run_id,
    )


@router.get(
    "/corpus",
    response_model=CorpusStatusResponse,
    summary="How large the corpus is, and how much of it is analyzed",
)
async def corpus_status(use_case: CorpusStatusDep) -> CorpusStatusResponse:
    return _status_response(await use_case.execute())


class ClearedCorpusResponse(BaseModel):
    calls: int = Field(description="Analyzed calls removed.")
    runs: int = Field(description="Corpus run records removed, with their items.")
    ground_truth_kept: bool = Field(
        default=True,
        description=(
            "Always true. Ground truth is hand-labelled and cannot be regenerated "
            "by re-analysis, so it is never part of a clear."
        ),
    )


@router.delete(
    "/corpus/analyses",
    response_model=ClearedCorpusResponse,
    summary="Discard every analyzed call, keeping ground truth",
)
async def clear_corpus(use_case: ClearCorpusDep) -> ClearedCorpusResponse:
    """Empty the corpus so it can be re-analyzed from nothing.

    Refused with a 409 while a run is working: the worker would be writing to
    rows this is deleting.
    """
    cleared = await use_case.execute()
    return ClearedCorpusResponse(calls=cleared.calls, runs=cleared.runs)


class ImportedCallResponse(BaseModel):
    number: int
    reference: str = Field(description="The reference a corpus run would store this call under.")
    title: str
    filename: str
    agent: str | None
    caller: str | None
    tier: str | None
    score: int | None
    resolution: str | None
    queue: str | None
    turns: int = Field(description="Non-blank transcript lines extracted for this call.")
    has_panel: bool = Field(description="Whether the authored insights panel came through.")
    broker: str | None = Field(description="Broker signal as 'Name: what they did', if any.")
    repeat: bool = Field(description="Whether this call is marked as a repeat contact.")


class CorpusImportResponse(BaseModel):
    name: str = Field(description="Directory this corpus was saved as.")
    directory: str
    total: int
    calls: list[ImportedCallResponse]


class CorpusVersionResponse(BaseModel):
    name: str
    directory: str
    files: int


def _import_response(result: CorpusImport) -> CorpusImportResponse:
    return CorpusImportResponse(
        name=result.saved.name,
        directory=str(result.saved.directory),
        total=result.total,
        calls=[ImportedCallResponse(**vars(call)) for call in result.calls],
    )


@router.post(
    "/corpus/imports",
    response_model=CorpusImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Convert an uploaded corpus document into sample call files",
)
async def import_corpus(
    use_case: ImportCorpusDocumentDep,
    file: Annotated[UploadFile, File(description="A call-corpus PDF.")],
) -> CorpusImportResponse:
    """Extract every call from a corpus PDF and save it as corpus markdown.

    Saved under its own name in the import library, never over the corpus in
    use: the stored analyses are only meaningful against the transcripts they
    were made from, so replacing those silently would leave the dashboard
    describing calls that no longer exist.

    Nothing is analysed here. Import produces files; a run spends money.
    """
    data = await file.read()
    result = use_case.execute(
        ImportDocumentCommand(filename=file.filename or "corpus.pdf", data=data)
    )
    return _import_response(result)


@router.get(
    "/corpus/imports",
    response_model=list[CorpusVersionResponse],
    summary="Corpora that have been imported, newest first",
)
async def list_corpus_imports(use_case: ImportCorpusDocumentDep) -> list[CorpusVersionResponse]:
    return [
        CorpusVersionResponse(name=saved.name, directory=str(saved.directory), files=saved.files)
        for saved in use_case.versions()
    ]


@router.post(
    "/corpus/runs",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a corpus run",
)
async def start_run(
    request: StartRunRequest,
    use_case: StartCorpusRunDep,
    container: ContainerDep,
) -> RunResponse:
    # Built before the run record so an unknown provider or a missing API key is
    # a 4xx on this request, not a run that exists only to fail on its first call.
    provider = container.create_provider(request.provider, request.model)
    try:
        run = await use_case.execute(
            StartRunCommand(
                provider=provider.name,
                model=provider.model,
                force=request.force,
                acknowledge_cost=request.acknowledge_cost,
            ),
            billable=container.provider_is_billable(request.provider),
        )
    except BaseException:
        await provider.aclose()
        raise

    await _launch(container, run.id, provider)
    return to_response(run)


@router.get(
    "/corpus/runs",
    response_model=list[RunSummaryResponse],
    summary="List recent corpus runs",
)
async def list_runs(
    use_case: ListCorpusRunsDep,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[RunSummaryResponse]:
    runs = await use_case.execute(limit)
    return [_summary(run) for run in runs]


@router.get(
    "/corpus/runs/{run_id}",
    response_model=RunResponse,
    summary="One corpus run and every call in it",
)
async def get_run(run_id: int, use_case: GetCorpusRunDep) -> RunResponse:
    return to_response(await use_case.execute(run_id))


@router.post(
    "/corpus/runs/{run_id}/cancel",
    response_model=RunResponse,
    summary="Ask a run to stop after the call in flight",
)
async def cancel_run(run_id: int, use_case: CancelCorpusRunDep) -> RunResponse:
    return to_response(await use_case.execute(run_id))


@router.post(
    "/corpus/runs/{run_id}/resume",
    response_model=RunResponse,
    summary="Continue a run that was cancelled or interrupted",
)
async def resume_run(
    run_id: int,
    use_case: ResumeCorpusRunDep,
    existing: GetCorpusRunDep,
    container: ContainerDep,
) -> RunResponse:
    # The provider is built before the run is touched. Building it afterwards
    # meant that a run whose provider had since lost its API key was already
    # returned to PENDING when construction failed — leaving it active, with no
    # worker, blocking every future run under the single-active-run rule.
    original = await existing.execute(run_id)
    provider = container.create_provider(original.provider, original.model)

    try:
        run = await use_case.execute(run_id)
    except BaseException:
        await provider.aclose()
        raise

    await _launch(container, run.id, provider)
    return to_response(run)


@router.get(
    "/corpus/runs/{run_id}/stream",
    summary="Live progress for a run, as Server-Sent Events",
    response_class=StreamingResponse,
)
async def stream_run(
    run_id: int,
    use_case: GetCorpusRunDep,
    container: ContainerDep,
) -> StreamingResponse:
    # Loaded before the stream opens so a bad run id is a 404 rather than a
    # successful connection that never says anything.
    run = await use_case.execute(run_id)

    return StreamingResponse(
        _events(container, run),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Nginx buffers streamed responses by default, which would hold every
            # event until the run finished and make the whole channel pointless.
            "X-Accel-Buffering": "no",
        },
    )


async def _launch(container: Container, run_id: int, provider: LLMProvider) -> None:
    """Hand the run to a background task, which owns the provider from here."""
    if not container.runner.start(run_id, _work(container, run_id, provider)):
        # Unreachable while the single-active-run rule holds, but a provider that
        # is never handed over is a leaked HTTP client, so it is closed here.
        await provider.aclose()  # pragma: no cover - defensive


async def _work(container: Container, run_id: int, provider: LLMProvider) -> None:
    try:
        await container.corpus_run_worker().execute(run_id, provider)
    finally:
        await provider.aclose()


async def _events(container: Container, run: CorpusRun) -> AsyncIterator[str]:
    """Snapshot first, then live events until the run finishes or the client goes."""
    async with container.events.subscribe(run.id) as events:
        snapshot = RunEvent(
            run_id=run.id,
            kind=RunEventKind.SNAPSHOT,
            at=container.clock.now(),
            run_status=run.status,
            progress=run.progress,
            message=run.message,
        )
        if run.status.is_terminal:
            # Nothing more will happen. Ending the stream is kinder than holding
            # a socket open on a run that finished before anyone connected.
            yield _frame(snapshot)
            return

        async for frame in sse_frames(events, snapshot, HEARTBEAT_SECONDS):
            yield frame


async def sse_frames(
    events: AsyncIterator[RunEvent],
    snapshot: RunEvent,
    heartbeat_seconds: float,
) -> AsyncIterator[str]:
    """Turn a stream of run events into SSE frames, with keep-alives between them.

    The pending read is held in a task across heartbeats rather than re-awaited.
    ``asyncio.wait_for`` cannot be used here: on timeout it *cancels* the awaited
    ``__anext__``, which throws CancelledError into the underlying async
    generator and closes it for good — so the first keep-alive would silently be
    the last thing a client ever received. ``asyncio.wait`` leaves the task alone.
    """
    yield _frame(snapshot)

    stream = events.__aiter__()
    pending: asyncio.Task[RunEvent] | None = None
    try:
        while True:
            if pending is None:
                pending = asyncio.ensure_future(stream.__anext__())

            done, _ = await asyncio.wait({pending}, timeout=heartbeat_seconds)
            if not done:
                yield HEARTBEAT_FRAME
                continue

            finished, pending = pending, None
            try:
                event = finished.result()
            except StopAsyncIteration:  # pragma: no cover - the bus does not end
                return

            yield _frame(event)
            if event.kind is RunEventKind.RUN_FINISHED:
                return
    finally:
        if pending is not None:
            pending.cancel()


def _frame(event: RunEvent) -> str:
    """One SSE frame: a named event plus its JSON payload."""
    payload = {
        "run_id": event.run_id,
        "kind": event.kind.value,
        "at": event.at.isoformat(),
        "run_status": event.run_status.value,
        "message": event.message,
        "progress": _progress(event.progress).model_dump(),
        "item": _item(event.item).model_dump(mode="json") if event.item else None,
    }
    return f"event: {event.kind.value}\ndata: {json.dumps(payload)}\n\n"
