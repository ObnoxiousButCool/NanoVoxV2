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
    SignalDistributionEntry,
)
from frameworks_drivers.api.dependencies import (
    AgentPerformanceDep,
    BrokerScorecardDep,
    EffortMetricsDep,
    MembersAtRiskDep,
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
    resolved: int
    partially_resolved: int
    escalated: int
    unresolved: int
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
    discarded: int = Field(
        default=0,
        description=(
            "Attributions naming this broker that failed evidence checking and "
            "were never recorded. Not included in the signal counts."
        ),
    )


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


class EffortResponse(BaseModel):
    calls_with_duration: int
    median_minutes: float
    mean_minutes: float
    longest_minutes: int
    long_call_count: int = Field(
        description="Calls at or beyond twice the median, which is where 'long' starts."
    )
    long_call_threshold: int
    identified_members: int = Field(
        description="Members whose identifier was stated in the call. Calls without "
        "one are excluded rather than grouped, since unknown members are different people."
    )
    repeat_members: int
    calls_by_repeat_members: int
    repeat_contact_rate: float = Field(
        description="Share of identified members who called more than once, as a percentage."
    )
    median_minutes_to_answer: float = Field(
        description="Median minutes a member spent across all their calls before one of "
        "them resolved their issue. Members still waiting are excluded, not counted as zero."
    )
    members_with_answer: int = Field(
        description="Identified members who reached a resolution. The population the "
        "time-to-answer figure is measured over."
    )
    members_without_answer: int = Field(
        description="Identified members with no resolved call. Their clock has not stopped, "
        "so folding them in would shorten the reported time the longer they are left waiting."
    )


class MemberAtRiskResponse(BaseModel):
    member_id: str
    member_name: str | None = Field(
        default=None,
        description="The member's name where a call stated one. Null otherwise — the "
        "identifier is always known, the name is not.",
    )
    call_count: int
    factors: list[str] = Field(
        description="Machine-readable risk factor codes observed for this member."
    )
    factor_labels: list[str]
    lowest_score: int
    latest_reference: str
    references: list[str]


class MembersAtRiskResponse(BaseModel):
    members: list[MemberAtRiskResponse]
    basis: str = Field(
        description=(
            "What this list is. Stated on the response because a client must not "
            "present it as a prediction: no factor here has been measured against "
            "an actual departure."
        ),
        default=(
            "Observed warning signs, not a prediction. Ranked by how many signs a "
            "member shows. No weighting has been validated against real churn."
        ),
    )


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
        resolved=agent.resolved,
        partially_resolved=agent.partially_resolved,
        escalated=agent.escalated,
        unresolved=agent.unresolved,
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
        discarded=broker.discarded,
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


@router.get(
    "/effort",
    response_model=EffortResponse,
    summary="What getting an answer costs a member",
)
async def get_effort(use_case: EffortMetricsDep) -> EffortResponse:
    metrics = await use_case.execute()
    return EffortResponse(
        calls_with_duration=metrics.calls_with_duration,
        median_minutes=metrics.median_minutes,
        mean_minutes=metrics.mean_minutes,
        longest_minutes=metrics.longest_minutes,
        long_call_count=metrics.long_call_count,
        long_call_threshold=metrics.long_call_threshold,
        identified_members=metrics.identified_members,
        repeat_members=metrics.repeat_members,
        calls_by_repeat_members=metrics.calls_by_repeat_members,
        repeat_contact_rate=metrics.repeat_contact_rate,
        median_minutes_to_answer=metrics.median_minutes_to_answer,
        members_with_answer=metrics.members_with_answer,
        members_without_answer=metrics.members_without_answer,
    )


@router.get(
    "/members-at-risk",
    response_model=MembersAtRiskResponse,
    summary="Members showing signs of leaving, with the evidence",
)
async def get_members_at_risk(use_case: MembersAtRiskDep) -> MembersAtRiskResponse:
    members = await use_case.execute()
    return MembersAtRiskResponse(
        members=[
            MemberAtRiskResponse(
                member_id=member.member_id,
                member_name=member.member_name,
                call_count=member.call_count,
                factors=[factor.value for factor in member.factors],
                factor_labels=[factor.label for factor in member.factors],
                lowest_score=member.lowest_score,
                latest_reference=member.latest_reference,
                references=list(member.references),
            )
            for member in members
        ]
    )


@router.get("/signals", response_model=SignalsResponse, summary="L4 signal distribution")
async def get_signals(use_case: SignalDistributionDep) -> SignalsResponse:
    entries, owners = await use_case.execute()
    return SignalsResponse(
        categories=[_signal_entry(entry) for entry in entries],
        owners=[OwnerLoadResponse(owner=load.owner, count=load.count) for load in owners],
    )


def _signal_entry(entry: SignalDistributionEntry) -> SignalEntryResponse:
    return SignalEntryResponse(**entry.__dict__)
