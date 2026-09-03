"""FastAPI dependencies.

The container is attached to application state during startup; these helpers are
the only place that reads it, so route handlers depend on use cases rather than
on the wiring.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

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
    GetCorpusRun,
    GetCorpusStatus,
    ListCorpusRuns,
    ResumeCorpusRun,
    StartCorpusRun,
)
from frameworks_drivers.container import Container
from infrastructure.config.settings import Settings
from infrastructure.persistence.repositories.analysis_repository import SqlAnalysisRepository
from infrastructure.persistence.repositories.read_models import SqlReadModelRepository


def get_container(request: Request) -> Container:
    container = getattr(request.app.state, "container", None)
    if container is None:  # pragma: no cover - only reachable if startup was skipped
        raise RuntimeError("Application container is not initialised.")
    if not isinstance(container, Container):  # pragma: no cover - defensive
        raise TypeError("Application state holds an unexpected container type.")
    return container


ContainerDep = Annotated[Container, Depends(get_container)]


def get_settings_dep(container: ContainerDep) -> Settings:
    return container.settings


def get_health_use_case(container: ContainerDep) -> GetHealth:
    return container.get_health()


def get_list_providers_use_case(container: ContainerDep) -> ListProviders:
    return container.list_providers()


def get_analyze_transcript_use_case(container: ContainerDep) -> AnalyzeTranscript:
    return container.analyze_transcript()


def get_overview_use_case(container: ContainerDep) -> GetOverview:
    return container.get_overview()


def get_agent_performance_use_case(container: ContainerDep) -> GetAgentPerformance:
    return container.get_agent_performance()


def get_broker_scorecard_use_case(container: ContainerDep) -> GetBrokerScorecard:
    return container.get_broker_scorecard()


def get_effort_metrics_use_case(container: ContainerDep) -> GetEffortMetrics:
    return container.get_effort_metrics()


def get_resolution_time_use_case(container: ContainerDep) -> GetResolutionTime:
    return container.get_resolution_time()


def get_time_value_use_case(container: ContainerDep) -> GetTimeValue:
    return container.get_time_value()


def get_members_at_risk_use_case(container: ContainerDep) -> GetMembersAtRisk:
    return container.get_members_at_risk()


def get_signal_distribution_use_case(container: ContainerDep) -> GetSignalDistribution:
    return container.get_signal_distribution()


def get_start_corpus_run_use_case(container: ContainerDep) -> StartCorpusRun:
    return container.start_corpus_run()


def get_cancel_corpus_run_use_case(container: ContainerDep) -> CancelCorpusRun:
    return container.cancel_corpus_run()


def get_clear_corpus_use_case(container: ContainerDep) -> ClearCorpus:
    return container.clear_corpus()


def get_resume_corpus_run_use_case(container: ContainerDep) -> ResumeCorpusRun:
    return container.resume_corpus_run()


def get_corpus_run_use_case(container: ContainerDep) -> GetCorpusRun:
    return container.get_corpus_run()


def get_list_corpus_runs_use_case(container: ContainerDep) -> ListCorpusRuns:
    return container.list_corpus_runs()


def get_corpus_status_use_case(container: ContainerDep) -> GetCorpusStatus:
    return container.get_corpus_status()


def get_read_models(container: ContainerDep) -> SqlReadModelRepository:
    return container.read_models()


def get_analysis_repository(container: ContainerDep) -> SqlAnalysisRepository:
    return container.analysis_repository()


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
GetHealthDep = Annotated[GetHealth, Depends(get_health_use_case)]
ListProvidersDep = Annotated[ListProviders, Depends(get_list_providers_use_case)]
AnalyzeTranscriptDep = Annotated[AnalyzeTranscript, Depends(get_analyze_transcript_use_case)]
OverviewDep = Annotated[GetOverview, Depends(get_overview_use_case)]
AgentPerformanceDep = Annotated[GetAgentPerformance, Depends(get_agent_performance_use_case)]
BrokerScorecardDep = Annotated[GetBrokerScorecard, Depends(get_broker_scorecard_use_case)]
SignalDistributionDep = Annotated[GetSignalDistribution, Depends(get_signal_distribution_use_case)]
EffortMetricsDep = Annotated[GetEffortMetrics, Depends(get_effort_metrics_use_case)]
ResolutionTimeDep = Annotated[GetResolutionTime, Depends(get_resolution_time_use_case)]
TimeValueDep = Annotated[GetTimeValue, Depends(get_time_value_use_case)]
MembersAtRiskDep = Annotated[GetMembersAtRisk, Depends(get_members_at_risk_use_case)]
StartCorpusRunDep = Annotated[StartCorpusRun, Depends(get_start_corpus_run_use_case)]
CancelCorpusRunDep = Annotated[CancelCorpusRun, Depends(get_cancel_corpus_run_use_case)]
ResumeCorpusRunDep = Annotated[ResumeCorpusRun, Depends(get_resume_corpus_run_use_case)]
GetCorpusRunDep = Annotated[GetCorpusRun, Depends(get_corpus_run_use_case)]
ListCorpusRunsDep = Annotated[ListCorpusRuns, Depends(get_list_corpus_runs_use_case)]
CorpusStatusDep = Annotated[GetCorpusStatus, Depends(get_corpus_status_use_case)]
ClearCorpusDep = Annotated[ClearCorpus, Depends(get_clear_corpus_use_case)]
ReadModelsDep = Annotated[SqlReadModelRepository, Depends(get_read_models)]
AnalysisRepositoryDep = Annotated[SqlAnalysisRepository, Depends(get_analysis_repository)]
