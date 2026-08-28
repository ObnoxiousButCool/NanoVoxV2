"""The corpus run, end to end against a real database.

Everything here is behaviour someone would notice going wrong on the day of a
hundred-call run: work that gets done twice, a cancel that does not stop, a
failure that takes the other ninety-nine with it, and a stopped run that cannot
be picked up again.

The model is scripted, not called. Correctness of the runner has to be provable
without four hours and a GPU.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from application.dto.analysis_schemas import build_analysis_schemas
from application.ports.llm_provider import LLMProvider, LlmRequest, StructuredResult, TModel
from application.ports.redaction import NoRedaction
from application.ports.run_events import RunEvent, RunEventKind
from application.use_cases.analyze_transcript import AnalyzeTranscript
from application.use_cases.run_corpus import (
    CancelCorpusRun,
    CorpusRunWorker,
    GetCorpusStatus,
    ResumeCorpusRun,
    StartCorpusRun,
    StartRunCommand,
)
from domain.entities.corpus_run import CorpusRun
from domain.errors import ConflictError, NanoVoxError, ValidationError
from domain.taxonomy import Taxonomy
from domain.value_objects.run_status import RunItemStatus, RunStatus
from infrastructure.config.paths import DEFAULT_RUBRIC_PATH, DEFAULT_TAXONOMY_PATH
from infrastructure.config.rubric_loader import load_rubric
from infrastructure.config.taxonomy_loader import load_taxonomy
from infrastructure.corpus.markdown_corpus import MarkdownCorpusSource
from infrastructure.llm.prompt_source import FilePromptSource
from infrastructure.llm.prompts import PromptLibrary
from infrastructure.persistence.engine import create_database_engine, create_session_factory
from infrastructure.persistence.models import Base
from infrastructure.persistence.repositories.analysis_repository import SqlAnalysisRepository
from infrastructure.persistence.repositories.ground_truth_repository import (
    SqlGroundTruthRepository,
)
from infrastructure.persistence.repositories.run_repository import SqlRunRepository
from infrastructure.runner.event_bus import InMemoryRunEventBus
from tests.support.analysis import ScriptedLayerProvider
from tests.support.clock import FIXED_NOW, FixedClock
from tests.support.settings import make_settings

CORPUS_SIZE = 3

TRANSCRIPT = (
    "Agent Brad: Choice Administrators, Brad.\n"
    "Member: Hello. I wanted to ask what my emergency room copay is.\n"
    "Agent Brad: ER copay is $250, waived if you're admitted.\n"
    "Member: Two hundred and fifty. That's a lot.\n"
    "Agent Brad: That's the plan rate.\n"
    "Member: I've had this pressure in my chest since last night.\n"
    "Agent Brad: Yeah, urgent care is cheaper if you want to go that route.\n"
    "Member: Urgent care might be better then.\n"
    "Agent Brad: Urgent care can handle most things. There's one on Ridgeway if you're nearby.\n"
)


def corpus_file(number: int) -> str:
    return (
        f"# Call #{number} — Fixture call {number}\n\n"
        "- **Agent:** Brad\n"
        "- **Tier:** POOR\n"
        "- **Score:** 36/100\n"
        "- **Resolution:** UNRESOLVED\n\n"
        f"## Transcript\n\n{TRANSCRIPT}\n"
        "## AI Insights Panel — NanoVox 5-Layer Output\n\n"
        "L3 — Agent Score: 36/100.\n"
    )


@pytest.fixture
def corpus_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "corpus"
    directory.mkdir()
    for number in range(1, CORPUS_SIZE + 1):
        (directory / f"call_{number:03d}.md").write_text(corpus_file(number), encoding="utf-8")
    return directory


@pytest.fixture
def taxonomy() -> Taxonomy:
    return load_taxonomy(DEFAULT_TAXONOMY_PATH)


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    subject = create_database_engine(
        make_settings(database_url=f"sqlite+aiosqlite:///{(tmp_path / 'runs.db').as_posix()}")
    )
    async with subject.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield subject
    await subject.dispose()


class Harness:
    """Everything a run needs, wired against one temporary database."""

    def __init__(self, engine: AsyncEngine, taxonomy: Taxonomy, corpus_dir: Path) -> None:
        sessions = create_session_factory(engine)
        rubric = load_rubric(DEFAULT_RUBRIC_PATH, taxonomy)
        self.clock = FixedClock()
        self.corpus = MarkdownCorpusSource(corpus_dir, "call_*.md")
        self.runs = SqlRunRepository(sessions)
        self.analyses = SqlAnalysisRepository(sessions, taxonomy)
        self.ground_truth = SqlGroundTruthRepository(sessions, self.clock)
        self.events = InMemoryRunEventBus()
        self.published: list[RunEvent] = []
        self.analyze = AnalyzeTranscript(
            prompts=FilePromptSource(PromptLibrary()),
            schemas=build_analysis_schemas(taxonomy, rubric),
            taxonomy=taxonomy,
            rubric=rubric,
            redaction=NoRedaction(),
            repository=self.analyses,
            clock=self.clock,
        )

    def start(self) -> StartCorpusRun:
        return StartCorpusRun(
            corpus=self.corpus,
            runs=self.runs,
            ground_truth=self.ground_truth,
            clock=self.clock,
        )

    def worker(self, concurrency: int = 1) -> CorpusRunWorker:
        return CorpusRunWorker(
            corpus=self.corpus,
            runs=self.runs,
            analyses=self.analyses,
            analyze=self.analyze,
            events=_Recording(self.events, self.published),
            clock=self.clock,
            concurrency=concurrency,
        )

    async def run_all(self, provider: LLMProvider | None = None, force: bool = False) -> CorpusRun:
        run = await self.start().execute(
            StartRunCommand(provider="scripted", model="scripted-model", force=force),
            billable=False,
        )
        await self.worker().execute(run.id, provider or ScriptedLayerProvider())
        loaded = await self.runs.get(run.id)
        assert loaded is not None
        return loaded


class _Recording(InMemoryRunEventBus):
    """Passes events through while keeping a copy for assertions."""

    def __init__(self, inner: InMemoryRunEventBus, sink: list[RunEvent]) -> None:
        super().__init__()
        self._inner = inner
        self._sink = sink

    async def publish(self, event: RunEvent) -> None:
        self._sink.append(event)
        await self._inner.publish(event)


@pytest.fixture
def harness(engine: AsyncEngine, taxonomy: Taxonomy, corpus_dir: Path) -> Harness:
    return Harness(engine, taxonomy, corpus_dir)


class TestAFullRun:
    async def test_every_corpus_call_is_analysed_and_stored(self, harness: Harness) -> None:
        run = await harness.run_all()

        assert run.status is RunStatus.COMPLETED
        assert run.progress.completed == CORPUS_SIZE
        assert len(run.analysed_call_ids) == CORPUS_SIZE

    async def test_each_item_links_to_the_call_it_produced(self, harness: Harness) -> None:
        # "Item 89 failed" is only actionable if it names the call.
        run = await harness.run_all()

        for item in run.items:
            assert item.call_id is not None
            stored = await harness.analyses.get(item.call_id)
            assert stored is not None
            assert stored.reference == item.reference

    async def test_corpus_calls_are_marked_as_such(self, harness: Harness) -> None:
        # A corpus figure must never be presented as one a user submitted.
        run = await harness.run_all()

        call_id = run.items[0].call_id
        assert call_id is not None
        stored = await harness.analyses.get(call_id)
        assert stored is not None
        assert stored.source.value == "CORPUS_RUN"

    async def test_the_run_reports_what_it_did(self, harness: Harness) -> None:
        run = await harness.run_all()

        assert run.message == f"{CORPUS_SIZE} analysed."

    async def test_progress_reaches_a_hundred_percent(self, harness: Harness) -> None:
        run = await harness.run_all()

        assert run.progress.percent_complete == 100.0
        assert run.progress.is_exhausted


class TestGroundTruth:
    async def test_authored_figures_are_stored_apart_from_the_analysis(
        self, harness: Harness
    ) -> None:
        # Plan A3. These are what a person wrote, not what the model concluded.
        await harness.run_all()

        truth = await harness.ground_truth.get("C0001")

        assert truth is not None
        assert truth.score == 36
        assert truth.tier == "POOR"

    async def test_ground_truth_is_recorded_even_if_the_run_never_works(
        self, harness: Harness
    ) -> None:
        # A cancelled run must still leave the answer key it read at the start.
        await harness.start().execute(
            StartRunCommand(provider="scripted", model="scripted-model"), billable=False
        )

        assert await harness.ground_truth.get("C0002") is not None

    async def test_re_reading_a_corrected_file_updates_rather_than_duplicates(
        self, harness: Harness, corpus_dir: Path
    ) -> None:
        await harness.ground_truth.upsert_many(harness.corpus.load())
        (corpus_dir / "call_001.md").write_text(
            corpus_file(1).replace("36/100", "72/100"), encoding="utf-8"
        )

        await harness.ground_truth.upsert_many(harness.corpus.load())

        truth = await harness.ground_truth.get("C0001")
        assert truth is not None
        assert truth.score == 72


class TestIdempotency:
    async def test_a_second_run_skips_what_is_already_analysed(self, harness: Harness) -> None:
        await harness.run_all()

        second = await harness.run_all()

        assert second.progress.skipped == CORPUS_SIZE
        assert second.progress.completed == 0
        assert "Already analysed" in second.items[0].message

    async def test_a_skip_leaves_exactly_one_stored_call(self, harness: Harness) -> None:
        # Two rows for one call would double every dashboard figure.
        await harness.run_all()
        await harness.run_all()

        stored = await harness.analyses.existing_references(["C0001", "C0002", "C0003"])
        assert len(stored) == CORPUS_SIZE

    async def test_force_re_analyses_instead_of_skipping(self, harness: Harness) -> None:
        await harness.run_all()

        second = await harness.run_all(force=True)

        assert second.progress.completed == CORPUS_SIZE
        assert second.progress.skipped == 0

    async def test_the_item_points_at_the_call_that_now_exists(self, harness: Harness) -> None:
        # Row ids are reused by SQLite after a delete, so the check that matters
        # is that the item resolves to a live call with the right reference —
        # not that the id changed.
        await harness.run_all()

        second = await harness.run_all(force=True)

        for item in second.items:
            assert item.call_id is not None
            stored = await harness.analyses.get(item.call_id)
            assert stored is not None
            assert stored.reference == item.reference

    async def test_force_does_not_leave_two_calls_behind(self, harness: Harness) -> None:
        await harness.run_all()
        await harness.run_all(force=True)

        status = await GetCorpusStatus(
            corpus=harness.corpus, analyses=harness.analyses, runs=harness.runs
        ).execute()

        assert status.analysed_calls == CORPUS_SIZE
        assert status.total_calls == CORPUS_SIZE


class TestFailureIsolation:
    async def test_one_failed_call_does_not_stop_the_others(self, harness: Harness) -> None:
        # Ninety-nine analysed calls are worth having.
        provider = _FailsOnce()

        run = await harness.run_all(provider=provider)

        assert run.progress.failed == 1
        assert run.progress.completed == CORPUS_SIZE - 1
        assert run.status is RunStatus.COMPLETED

    async def test_a_failure_records_why(self, harness: Harness) -> None:
        run = await harness.run_all(provider=_FailsOnce())

        failed = next(item for item in run.items if item.status is RunItemStatus.FAILED)
        assert "provider is on fire" in failed.message

    async def test_a_run_where_nothing_worked_is_reported_as_failed(
        self, harness: Harness
    ) -> None:
        # A green bar over zero results would be a lie.
        run = await harness.run_all(provider=_AlwaysFails())

        assert run.status is RunStatus.FAILED
        assert run.progress.failed == CORPUS_SIZE
        assert "All 3 calls failed" in run.message


class TestCancellation:
    async def test_cancelling_stops_the_remaining_calls(self, harness: Harness) -> None:
        run = await harness.start().execute(
            StartRunCommand(provider="scripted", model="scripted-model"), billable=False
        )
        await CancelCorpusRun(runs=harness.runs, clock=harness.clock).execute(run.id)

        await harness.worker().execute(run.id, ScriptedLayerProvider())

        finished = await harness.runs.get(run.id)
        assert finished is not None
        assert finished.status is RunStatus.CANCELLED
        assert finished.progress.cancelled == CORPUS_SIZE
        assert finished.progress.completed == 0

    async def test_a_cancelled_item_says_it_was_cancelled_not_that_it_failed(
        self, harness: Harness
    ) -> None:
        run = await harness.start().execute(
            StartRunCommand(provider="scripted", model="scripted-model"), billable=False
        )
        await CancelCorpusRun(runs=harness.runs, clock=harness.clock).execute(run.id)
        await harness.worker().execute(run.id, ScriptedLayerProvider())

        finished = await harness.runs.get(run.id)
        assert finished is not None
        assert finished.progress.failed == 0
        assert "Cancelled" in finished.items[0].message

    async def test_cancelling_a_finished_run_is_refused(self, harness: Harness) -> None:
        run = await harness.run_all()

        with pytest.raises(ConflictError, match="already finished"):
            await CancelCorpusRun(runs=harness.runs, clock=harness.clock).execute(run.id)


class TestResume:
    async def test_a_cancelled_run_continues_where_it_stopped(self, harness: Harness) -> None:
        run = await harness.start().execute(
            StartRunCommand(provider="scripted", model="scripted-model"), billable=False
        )
        await CancelCorpusRun(runs=harness.runs, clock=harness.clock).execute(run.id)
        await harness.worker().execute(run.id, ScriptedLayerProvider())

        resumed = await ResumeCorpusRun(runs=harness.runs, clock=harness.clock).execute(run.id)
        await harness.worker().execute(resumed.id, ScriptedLayerProvider())

        finished = await harness.runs.get(run.id)
        assert finished is not None
        assert finished.status is RunStatus.COMPLETED
        assert finished.progress.completed == CORPUS_SIZE

    async def test_resuming_retries_failures_but_not_skips(self, harness: Harness) -> None:
        # Skipping was a decision about the call; failing was an accident.
        await harness.run_all()  # everything now analysed
        second = await harness.run_all(provider=_AlwaysFails())  # all skipped

        with pytest.raises(ConflictError, match="nothing left to do"):
            await ResumeCorpusRun(runs=harness.runs, clock=harness.clock).execute(second.id)

    async def test_a_completed_run_cannot_be_resumed(self, harness: Harness) -> None:
        run = await harness.run_all()

        with pytest.raises(ConflictError, match="nothing left to do"):
            await ResumeCorpusRun(runs=harness.runs, clock=harness.clock).execute(run.id)

    async def test_a_run_left_active_by_a_dead_process_becomes_resumable(
        self, harness: Harness
    ) -> None:
        run = await harness.start().execute(
            StartRunCommand(provider="scripted", model="scripted-model"), billable=False
        )
        await harness.runs.set_status(run.id, RunStatus.RUNNING, now=FIXED_NOW)

        abandoned = await harness.runs.abandon_active(now=FIXED_NOW, reason="Process stopped.")

        assert abandoned == 1
        interrupted = await harness.runs.get(run.id)
        assert interrupted is not None
        assert interrupted.status is RunStatus.INTERRUPTED
        assert interrupted.can_resume


class TestConcurrentRuns:
    async def test_a_second_run_is_refused_while_one_is_working(self, harness: Harness) -> None:
        # Two workers over one corpus would double the spend and race for the
        # same call references.
        await harness.start().execute(
            StartRunCommand(provider="scripted", model="scripted-model"), billable=False
        )

        with pytest.raises(ConflictError, match="already in progress"):
            await harness.start().execute(
                StartRunCommand(provider="scripted", model="scripted-model"), billable=False
            )

    async def test_a_new_run_is_allowed_once_the_last_one_finished(
        self, harness: Harness
    ) -> None:
        await harness.run_all()

        second = await harness.start().execute(
            StartRunCommand(provider="scripted", model="scripted-model"), billable=False
        )

        assert second.status is RunStatus.PENDING


class TestCostGuard:
    async def test_a_paid_provider_needs_an_acknowledgement(self, harness: Harness) -> None:
        with pytest.raises(ValidationError, match="paid provider"):
            await harness.start().execute(
                StartRunCommand(provider="openai", model="gpt-4o-mini"), billable=True
            )

    async def test_an_acknowledged_paid_run_proceeds(self, harness: Harness) -> None:
        run = await harness.start().execute(
            StartRunCommand(provider="openai", model="gpt-4o-mini", acknowledge_cost=True),
            billable=True,
        )

        assert run.provider == "openai"

    async def test_a_local_provider_needs_no_acknowledgement(self, harness: Harness) -> None:
        run = await harness.start().execute(
            StartRunCommand(provider="ollama", model="qwen2.5:7b-instruct"), billable=False
        )

        assert run.status is RunStatus.PENDING


class TestProgressEvents:
    async def test_every_call_is_announced_starting_and_finishing(self, harness: Harness) -> None:
        await harness.run_all()

        kinds = [event.kind for event in harness.published]
        assert kinds.count(RunEventKind.ITEM_STARTED) == CORPUS_SIZE
        assert kinds.count(RunEventKind.ITEM_FINISHED) == CORPUS_SIZE
        assert kinds[-1] is RunEventKind.RUN_FINISHED

    async def test_every_event_carries_the_progress_at_that_moment(
        self, harness: Harness
    ) -> None:
        # A client that missed an event must be able to catch up from the next.
        await harness.run_all()

        final = harness.published[-1]
        assert final.progress.total == CORPUS_SIZE
        assert final.progress.completed == CORPUS_SIZE

    async def test_events_report_the_state_the_database_holds(self, harness: Harness) -> None:
        run = await harness.run_all()

        final = harness.published[-1]
        assert final.run_status is run.status


class TestCorpusStatus:
    async def test_it_reports_outstanding_work_without_starting_any(
        self, harness: Harness
    ) -> None:
        use_case = GetCorpusStatus(
            corpus=harness.corpus, analyses=harness.analyses, runs=harness.runs
        )

        before = await use_case.execute()
        assert before.total_calls == CORPUS_SIZE
        assert before.analysed_calls == 0
        assert before.outstanding == CORPUS_SIZE
        assert before.active_run_id is None

        await harness.run_all()

        after = await use_case.execute()
        assert after.analysed_calls == CORPUS_SIZE
        assert after.outstanding == 0


class _FailsOnce(ScriptedLayerProvider):
    """Fails the first L1 call it sees, then behaves."""

    def __init__(self) -> None:
        super().__init__()
        self._failed = False

    async def complete(self, request: LlmRequest[TModel]) -> StructuredResult[TModel]:
        if request.prompt_id == "l1_understanding" and not self._failed:
            self._failed = True
            raise NanoVoxError("The provider is on fire.")
        return await super().complete(request)


class _AlwaysFails(ScriptedLayerProvider):
    """Fails every call."""

    async def complete(self, request: LlmRequest[TModel]) -> StructuredResult[TModel]:
        raise NanoVoxError("The provider is on fire.")
