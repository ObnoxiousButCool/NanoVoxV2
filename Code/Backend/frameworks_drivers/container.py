"""Composition root.

Every concrete adapter is chosen here and nowhere else. Use cases receive their
dependencies through constructors, so no module reaches out for a global.

Long-lived resources (the engine, the session factory) are built once per process
and held on the container; use cases are cheap and are built per request.
"""

from __future__ import annotations

from dataclasses import dataclass
from re import Pattern

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from application.dto.analysis_schemas import AnalysisSchemas, build_analysis_schemas
from application.ports.clock import Clock
from application.ports.corpus_source import CorpusSource
from application.ports.health_probe import HealthProbe
from application.ports.llm_provider import LLMProvider
from application.ports.redaction import NoRedaction, RedactionPort
from application.use_cases.analyze_transcript import AnalyzeTranscript
from application.use_cases.clear_corpus import ClearCorpus
from application.use_cases.get_dashboard import (
    GetAgentPerformance,
    GetBrokerScorecard,
    GetEffortMetrics,
    GetMembersAtRisk,
    GetOverview,
    GetResolutionTime,
    GetSignalDistribution,
    GetTimeValue,
)
from application.use_cases.get_health import GetHealth
from application.use_cases.list_providers import ListProviders
from application.use_cases.run_corpus import (
    CancelCorpusRun,
    CorpusRunWorker,
    GetCorpusRun,
    GetCorpusStatus,
    ListCorpusRuns,
    ResumeCorpusRun,
    StartCorpusRun,
)
from domain.broker_evidence import compile_broker_terms
from domain.member_id import compile_member_id_pattern
from domain.scoring.rubric import Rubric
from domain.scoring.rubric_engine import RubricEngine
from domain.taxonomy import Taxonomy
from infrastructure.config.dashboard_loader import DashboardConfig, load_dashboard_config
from infrastructure.config.rubric_loader import load_rubric
from infrastructure.config.settings import Settings
from infrastructure.config.taxonomy_loader import load_taxonomy
from infrastructure.corpus.markdown_corpus import MarkdownCorpusSource
from infrastructure.llm.prompt_source import FilePromptSource
from infrastructure.llm.prompts import PromptLibrary
from infrastructure.llm.provider_probe import RegistryProviderProbe
from infrastructure.llm.registry import ProviderRegistry, is_billable
from infrastructure.logging.llm_audit import LlmAuditLog
from infrastructure.persistence.engine import create_database_engine, create_session_factory
from infrastructure.persistence.health_probe import DatabaseHealthProbe
from infrastructure.persistence.repositories.analysis_repository import SqlAnalysisRepository
from infrastructure.persistence.repositories.ground_truth_repository import (
    SqlGroundTruthRepository,
)
from infrastructure.persistence.repositories.read_models import SqlReadModelRepository
from infrastructure.persistence.repositories.run_repository import SqlRunRepository
from infrastructure.runner.background_runner import BackgroundRunner
from infrastructure.runner.event_bus import InMemoryRunEventBus
from infrastructure.system_clock import SystemClock


@dataclass(frozen=True)
class Container:
    """Holds the process-wide dependencies and builds use cases on demand."""

    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    clock: Clock
    health_probes: tuple[HealthProbe, ...]
    taxonomy: Taxonomy
    rubric: Rubric
    prompts: PromptLibrary
    provider_registry: ProviderRegistry
    schemas: AnalysisSchemas
    redaction: RedactionPort
    dashboard: DashboardConfig
    corpus: CorpusSource
    # One event bus and one runner per process: a subscriber and the worker
    # publishing to it must be looking at the same object, and a per-request
    # instance would leave every stream permanently silent.
    events: InMemoryRunEventBus
    runner: BackgroundRunner
    # Compiled once at startup rather than per analysis, and None when the
    # setting is blank, which turns extraction off rather than matching nothing.
    member_id_pattern: Pattern[str] | None
    broker_terms: Pattern[str] | None
    administrator_name: str

    def get_health(self) -> GetHealth:
        return GetHealth(probes=self.health_probes, clock=self.clock)

    def rubric_engine(self) -> RubricEngine:
        return RubricEngine(self.rubric)

    def list_providers(self) -> ListProviders:
        default = self.settings.llm_provider
        return ListProviders(
            probe=RegistryProviderProbe(
                self.provider_registry, default, self.settings.llm_probe_timeout_seconds
            ),
            names=self.provider_registry.names,
            default_name=default,
        )

    def create_provider(self, name: str | None = None, model: str | None = None) -> LLMProvider:
        return self.provider_registry.create(name, model)

    def analysis_repository(self) -> SqlAnalysisRepository:
        return SqlAnalysisRepository(self.session_factory, self.taxonomy)

    def read_models(self) -> SqlReadModelRepository:
        return SqlReadModelRepository(self.session_factory)

    def get_overview(self) -> GetOverview:
        return GetOverview(
            self.read_models(),
            self.taxonomy,
            self.dashboard.histogram,
            self.dashboard.attention_rules,
        )

    def get_agent_performance(self) -> GetAgentPerformance:
        return GetAgentPerformance(self.read_models(), self.rubric)

    def get_broker_scorecard(self) -> GetBrokerScorecard:
        return GetBrokerScorecard(self.read_models())

    def get_effort_metrics(self) -> GetEffortMetrics:
        return GetEffortMetrics(self.read_models())

    def get_resolution_time(self) -> GetResolutionTime:
        return GetResolutionTime(self.read_models(), self.taxonomy, self.dashboard.duration_bands)

    def get_time_value(self) -> GetTimeValue:
        return GetTimeValue(self.read_models(), self.taxonomy)

    def get_members_at_risk(self) -> GetMembersAtRisk:
        return GetMembersAtRisk(self.read_models(), self.dashboard.histogram)

    def get_signal_distribution(self) -> GetSignalDistribution:
        return GetSignalDistribution(self.read_models(), self.taxonomy)

    def run_repository(self) -> SqlRunRepository:
        return SqlRunRepository(self.session_factory)

    def ground_truth_repository(self) -> SqlGroundTruthRepository:
        return SqlGroundTruthRepository(self.session_factory, self.clock)

    def start_corpus_run(self) -> StartCorpusRun:
        return StartCorpusRun(
            corpus=self.corpus,
            runs=self.run_repository(),
            ground_truth=self.ground_truth_repository(),
            clock=self.clock,
        )

    def cancel_corpus_run(self) -> CancelCorpusRun:
        return CancelCorpusRun(runs=self.run_repository(), clock=self.clock)

    def clear_corpus(self) -> ClearCorpus:
        return ClearCorpus(analyses=self.analysis_repository(), runs=self.run_repository())

    def resume_corpus_run(self) -> ResumeCorpusRun:
        return ResumeCorpusRun(runs=self.run_repository(), clock=self.clock)

    def get_corpus_run(self) -> GetCorpusRun:
        return GetCorpusRun(self.run_repository())

    def list_corpus_runs(self) -> ListCorpusRuns:
        return ListCorpusRuns(self.run_repository())

    def get_corpus_status(self) -> GetCorpusStatus:
        return GetCorpusStatus(
            corpus=self.corpus,
            analyses=self.analysis_repository(),
            runs=self.run_repository(),
        )

    def corpus_run_worker(self) -> CorpusRunWorker:
        return CorpusRunWorker(
            corpus=self.corpus,
            runs=self.run_repository(),
            analyses=self.analysis_repository(),
            analyze=self.analyze_transcript(),
            events=self.events,
            clock=self.clock,
            concurrency=self.settings.corpus_run_concurrency,
        )

    def provider_is_billable(self, name: str | None) -> bool:
        return is_billable(name or self.settings.llm_provider)

    def analyze_transcript(self) -> AnalyzeTranscript:
        return AnalyzeTranscript(
            prompts=FilePromptSource(self.prompts),
            schemas=self.schemas,
            taxonomy=self.taxonomy,
            rubric=self.rubric,
            redaction=self.redaction,
            repository=self.analysis_repository(),
            clock=self.clock,
            member_id_pattern=self.member_id_pattern,
            broker_terms=self.broker_terms,
            administrator_name=self.administrator_name,
        )


def build_container(settings: Settings) -> Container:
    """Wire the object graph for a running application.

    The taxonomy and rubric are loaded here, at startup, rather than on first
    use: a malformed rubric is a configuration failure, and it should stop the
    process with a clear message instead of failing partway through an analysis.
    """
    taxonomy = load_taxonomy(settings.taxonomy_path)
    rubric = load_rubric(settings.rubric_path, taxonomy)
    prompts = PromptLibrary()
    audit = LlmAuditLog(include_bodies=settings.log_llm_prompts)

    engine = create_database_engine(settings)
    return Container(
        settings=settings,
        engine=engine,
        session_factory=create_session_factory(engine),
        clock=SystemClock(),
        health_probes=(DatabaseHealthProbe(engine),),
        taxonomy=taxonomy,
        rubric=rubric,
        prompts=prompts,
        provider_registry=ProviderRegistry(settings, audit),
        schemas=build_analysis_schemas(taxonomy, rubric),
        redaction=NoRedaction(),
        dashboard=load_dashboard_config(settings.dashboard_path, taxonomy),
        corpus=MarkdownCorpusSource(settings.corpus_path, settings.corpus_glob),
        events=InMemoryRunEventBus(),
        runner=BackgroundRunner(),
        member_id_pattern=(
            compile_member_id_pattern(settings.member_id_pattern)
            if settings.member_id_pattern.strip()
            else None
        ),
        broker_terms=compile_broker_terms(settings.broker_evidence_terms),
        administrator_name=settings.administrator_name,
    )


async def dispose_container(container: Container) -> None:
    """Release the resources held by the container.

    Background work is stopped before the engine goes: a worker mid-analysis
    would otherwise reach for a disposed connection pool and fail with a
    confusing database error instead of a clean cancellation.
    """
    await container.runner.shutdown()
    await container.engine.dispose()
