"""Composition root.

Every concrete adapter is chosen here and nowhere else. Use cases receive their
dependencies through constructors, so no module reaches out for a global.

Long-lived resources (the engine, the session factory) are built once per process
and held on the container; use cases are cheap and are built per request.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from application.dto.analysis_schemas import AnalysisSchemas, build_analysis_schemas
from application.ports.clock import Clock
from application.ports.health_probe import HealthProbe
from application.ports.llm_provider import LLMProvider
from application.ports.redaction import NoRedaction, RedactionPort
from application.use_cases.analyze_transcript import AnalyzeTranscript
from application.use_cases.get_dashboard import (
    GetAgentPerformance,
    GetBrokerScorecard,
    GetOverview,
    GetSignalDistribution,
)
from application.use_cases.get_health import GetHealth
from application.use_cases.list_providers import ListProviders
from domain.scoring.rubric import Rubric
from domain.scoring.rubric_engine import RubricEngine
from domain.taxonomy import Taxonomy
from infrastructure.config.dashboard_loader import DashboardConfig, load_dashboard_config
from infrastructure.config.rubric_loader import load_rubric
from infrastructure.config.settings import Settings
from infrastructure.config.taxonomy_loader import load_taxonomy
from infrastructure.llm.prompt_source import FilePromptSource
from infrastructure.llm.prompts import PromptLibrary
from infrastructure.llm.provider_probe import RegistryProviderProbe
from infrastructure.llm.registry import ProviderRegistry
from infrastructure.logging.llm_audit import LlmAuditLog
from infrastructure.persistence.engine import create_database_engine, create_session_factory
from infrastructure.persistence.health_probe import DatabaseHealthProbe
from infrastructure.persistence.repositories.analysis_repository import SqlAnalysisRepository
from infrastructure.persistence.repositories.read_models import SqlReadModelRepository
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

    def get_health(self) -> GetHealth:
        return GetHealth(probes=self.health_probes, clock=self.clock)

    def rubric_engine(self) -> RubricEngine:
        return RubricEngine(self.rubric)

    def list_providers(self) -> ListProviders:
        default = self.settings.llm_provider
        return ListProviders(
            probe=RegistryProviderProbe(self.provider_registry, default),
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

    def get_signal_distribution(self) -> GetSignalDistribution:
        return GetSignalDistribution(self.read_models(), self.taxonomy)

    def analyze_transcript(self) -> AnalyzeTranscript:
        return AnalyzeTranscript(
            prompts=FilePromptSource(self.prompts),
            schemas=self.schemas,
            taxonomy=self.taxonomy,
            rubric=self.rubric,
            redaction=self.redaction,
            repository=self.analysis_repository(),
            clock=self.clock,
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
    )


async def dispose_container(container: Container) -> None:
    """Release the resources held by the container."""
    await container.engine.dispose()
