"""Dashboard endpoints.

Every figure returned here is counted from stored calls. Nothing on these
responses is written by a model, which is what makes the attention queue
actionable rather than merely readable.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from application.use_cases.get_dashboard import (
    AgentPerformance,
    BrokerScorecardEntry,
    Overview,
    OwnerLoad,
    SignalDistributionEntry,
)
from frameworks_drivers.api.dependencies import (
    AgentPerformanceDep,
    BrokerScorecardDep,
    OverviewDep,
    SignalDistributionDep,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class MetricsResponse(BaseModel):
    total_calls: int
    median_score: float
    mean_score: float = Field(
        description="Reported alongside the median because the distribution is bimodal; "
        "one number alone would hide the low cluster."
    )
    first_contact_resolution_rate: float = Field(
        description="RESOLVED as a percentage of all calls. Excludes PARTIALLY RESOLVED."
    )
    escalation_rate: float
    unresolved_rate: float
    broker_signal_count: int
    distinct_broker_count: int
    provisional_score_count: int


class HistogramBinResponse(BaseModel):
    label: str
    lower: int
    upper: int
    count: int
    is_below_threshold: bool


class HistogramResponse(BaseModel):
    bins: list[HistogramBinResponse]
    total: int
    below_threshold_count: int
    peak: int


class CategoryResponse(BaseModel):
    code: str
    label: str
    count: int
    unresolved: int
    percentage_of_total: float


class AttentionItemResponse(BaseModel):
    rule_id: str
    title: str
    subject: str
    why: str
    owner: str
    severity: str
    count: int
    unresolved: int
    references: list[str]


class OverviewResponse(BaseModel):
    metrics: MetricsResponse
    histogram: HistogramResponse
    categories: list[CategoryResponse]
    attention: list[AttentionItemResponse]
    taxonomy_coverage: float = Field(
        description="Share of calls landing in a defined category. Below 90% means the "
        "taxonomy needs revising, not the chart."
    )


class AgentResponse(BaseModel):
    agent_name: str
    call_count: int
    average_score: float
    min_score: int
    max_score: int
    unresolved: int
    escalated: int
    tier: str | None = Field(
        description="Null when the sample is too small to rate the agent fairly."
    )
    note: str | None


class BrokerResponse(BaseModel):
    broker_name: str
    signals: int
    negative: int
    positive: int
    is_net_positive: bool
    call_references: list[str]


class SignalEntryResponse(BaseModel):
    code: str
    label: str
    owner: str
    count: int
    percentage_of_corpus: float


class OwnerLoadResponse(BaseModel):
    owner: str
    count: int


class SignalsResponse(BaseModel):
    categories: list[SignalEntryResponse] = Field(
        description="Every configured L4 category, including those with no signals — "
        "the absence is shown rather than implied."
    )
    owners: list[OwnerLoadResponse]


def _overview_response(overview: Overview) -> OverviewResponse:
    return OverviewResponse(
        metrics=MetricsResponse(**overview.metrics.__dict__),
        histogram=HistogramResponse(
            bins=[
                HistogramBinResponse(
                    label=item.label,
                    lower=item.lower,
                    upper=item.upper,
                    count=item.count,
                    is_below_threshold=item.is_below_threshold,
                )
                for item in overview.histogram.bins
            ],
            total=overview.histogram.total,
            below_threshold_count=overview.histogram.below_threshold_count,
            peak=overview.histogram.peak,
        ),
        categories=[CategoryResponse(**item.__dict__) for item in overview.categories],
        attention=[
            AttentionItemResponse(
                rule_id=item.rule_id,
                title=item.title,
                subject=item.subject,
                why=item.why,
                owner=item.owner,
                severity=item.severity.value,
                count=item.count,
                unresolved=item.unresolved,
                references=list(item.references),
            )
            for item in overview.attention
        ],
        taxonomy_coverage=overview.taxonomy_coverage,
    )


def _agent_response(agent: AgentPerformance) -> AgentResponse:
    return AgentResponse(
        agent_name=agent.agent_name,
        call_count=agent.call_count,
        average_score=agent.average_score,
        min_score=agent.min_score,
        max_score=agent.max_score,
        unresolved=agent.unresolved,
        escalated=agent.escalated,
        tier=agent.rating.tier.value if agent.rating.tier else None,
        note=agent.rating.note,
    )


def _broker_response(broker: BrokerScorecardEntry) -> BrokerResponse:
    return BrokerResponse(
        broker_name=broker.broker_name,
        signals=broker.signals,
        negative=broker.negative,
        positive=broker.positive,
        is_net_positive=broker.is_net_positive,
        call_references=list(broker.call_references),
    )


@router.get("/overview", response_model=OverviewResponse, summary="What needs attention")
async def get_overview(use_case: OverviewDep) -> OverviewResponse:
    return _overview_response(await use_case.execute())


@router.get("/agents", response_model=list[AgentResponse], summary="Agent performance")
async def get_agents(use_case: AgentPerformanceDep) -> list[AgentResponse]:
    return [_agent_response(agent) for agent in await use_case.execute()]


@router.get("/brokers", response_model=list[BrokerResponse], summary="Broker scorecard")
async def get_brokers(use_case: BrokerScorecardDep) -> list[BrokerResponse]:
    return [_broker_response(broker) for broker in await use_case.execute()]


@router.get("/signals", response_model=SignalsResponse, summary="L4 signal distribution")
async def get_signals(use_case: SignalDistributionDep) -> SignalsResponse:
    entries, owners = await use_case.execute()
    return SignalsResponse(
        categories=[_signal_entry(entry) for entry in entries],
        owners=[OwnerLoadResponse(owner=load.owner, count=load.count) for load in owners],
    )


def _signal_entry(entry: SignalDistributionEntry) -> SignalEntryResponse:
    return SignalEntryResponse(**entry.__dict__)


def _owner_load(load: OwnerLoad) -> OwnerLoadResponse:
    return OwnerLoadResponse(owner=load.owner, count=load.count)
