"""Dashboard endpoints.

Every figure returned here is counted from stored calls. Nothing on these
responses is written by a model, which is what makes the attention queue
actionable rather than merely readable.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from application.use_cases.get_dashboard import (
    AgentPerformance,
    BrokerScorecardEntry,
    Overview,
    SignalDistributionEntry,
)
from domain.aggregation.attention import AttentionItem, RuleKind
from domain.aggregation.member_risk import RiskFactor
from domain.aggregation.trend import Bucket, TrendPoint
from domain.value_objects.resolution import Resolution
from frameworks_drivers.api.dependencies import (
    AgentPerformanceDep,
    BrokerScorecardDep,
    EffortMetricsDep,
    MembersAtRiskDep,
    OverviewDep,
    PulseDep,
    ResolutionTimeDep,
    SignalDistributionDep,
    TimeValueDep,
    WorkMixDep,
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
    call_filter: dict[str, str] = Field(
        description=(
            "The calls list query that returns exactly the calls this item "
            "counted, as query-string parameters. Sent from here rather than "
            "rebuilt by the client from the rule id: the rule kinds are a "
            "server-side vocabulary, and a client mapping them itself would "
            "quietly produce a dead link the first time a kind is added. Empty "
            "when the item's subject has no filter, which is a gap to close "
            "rather than a state to design for."
        )
    )


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


class DurationBandResponse(BaseModel):
    label: str
    lower: int
    upper: int | None = Field(
        default=None,
        description="Exclusive upper bound in minutes; null for the final open-ended band. "
        "Half-open like the score bins, so '10-20' holds 10 up to 19.",
    )
    count: int


class CategoryResolutionTimeResponse(BaseModel):
    code: str
    label: str
    resolved_calls: int
    median_minutes: float
    longest_minutes: int


class ResolutionTimeResponse(BaseModel):
    resolved_calls: int = Field(
        description="Calls that reached a resolution. Every figure here is measured over "
        "these only — handle time across all calls rewards ending the call, not solving it."
    )
    total_calls: int
    median_minutes: float
    longest_minutes: int
    bands: list[DurationBandResponse]
    categories: list[CategoryResolutionTimeResponse] = Field(
        description="Slowest first. Every configured category appears, including those "
        "that have resolved nothing."
    )


class OutcomeMinutesResponse(BaseModel):
    resolution: str
    minutes: int


class CategoryMinutesResponse(BaseModel):
    code: str
    label: str
    total_minutes: int
    resolved_minutes: int
    unproductive_minutes: int
    unproductive_share: float
    by_outcome: list[OutcomeMinutesResponse] = Field(
        description="Always in the same order, worst last, so a category's segments do not "
        "shuffle when its mix changes. Zero-minute outcomes are kept."
    )


class FailureModeResponse(BaseModel):
    calls: int
    minutes: int
    average_score: float


class TimeValueResponse(BaseModel):
    total_minutes: int
    resolved_minutes: int
    unproductive_minutes: int
    productive_share: float = Field(
        description="Share of all minutes spent on calls that reached a resolution."
    )
    resolved_median_minutes: float = Field(
        description="Median duration of a resolved call, and the line dividing the two "
        "failure modes. Derived from the corpus, not configured."
    )
    fast_fail: FailureModeResponse = Field(
        description="Ended without an answer in less time than a typical successful call — "
        "a member brushed off. A coaching signal."
    )
    slow_fail: FailureModeResponse = Field(
        description="Ended without an answer having taken at least as long as a typical "
        "successful call — the work was done and the system had no answer. A process signal, "
        "and coaching these agents would be the wrong response."
    )
    categories: list[CategoryMinutesResponse] = Field(
        description="Most time first. Categories with no timed calls are omitted."
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


class RiskFactorResponse(BaseModel):
    """One column of the signal matrix."""

    code: str
    label: str
    short_label: str


class MembersAtRiskResponse(BaseModel):
    members: list[MemberAtRiskResponse]
    factor_vocabulary: list[RiskFactorResponse] = Field(
        description=(
            "Every factor this system can observe, in a fixed order, whether or "
            "not any member is currently showing it. A client drawing a column "
            "per factor takes them from here: a factor added to the domain and "
            "not to the client would otherwise go unread with nothing to show "
            "for it, and an absent column is indistinguishable from a column of "
            "no findings."
        )
    )
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
                call_filter=_call_filter(item),
            )
            for item in overview.attention
        ],
        taxonomy_coverage=overview.taxonomy_coverage,
    )


def _call_filter(item: AttentionItem) -> dict[str, str]:
    """The calls list query that reproduces an attention item's count.

    Each rule kind counts calls by one dimension, and each dimension is a filter
    the calls list already accepts — so the mapping is total, and a new kind
    added without a filter shows up here as a missing branch rather than as a
    link that silently returns every call.
    """
    if item.kind is RuleKind.SIGNAL_PRESENT:
        return {"signal": item.subject_key}
    if item.kind is RuleKind.L4_CATEGORY_VOLUME:
        return {"l4_category": item.subject_key}
    if item.kind is RuleKind.BROKER_NEGATIVE:
        return {"broker": item.subject_key}
    # Unresolved in a category: the rule counts only the unresolved ones, so the
    # outcome belongs in the filter. Without it the link would open the whole
    # category and contradict the count it was opened from.
    return {"category": item.subject_key, "resolution": Resolution.UNRESOLVED.value}


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


class TrendPointResponse(BaseModel):
    starting: date
    label: str
    calls: int
    median_score: float | None = Field(
        default=None, description="Absent for a week with no calls, which is a gap not a zero."
    )
    resolution_rate: float | None = None
    median_handle_minutes: float | None = None


class TrendDeltaResponse(BaseModel):
    """The most recent week against the one before it."""

    calls: int
    median_score: float | None
    resolution_rate: float | None
    median_handle_minutes: float | None


class SentimentMovementResponse(BaseModel):
    improved: int
    unchanged: int
    worsened: int
    unclassified: int
    improved_rate: float


class PulseResponse(BaseModel):
    points: list[TrendPointResponse]
    latest: TrendPointResponse | None
    previous: TrendPointResponse | None
    delta: TrendDeltaResponse | None
    sentiment: SentimentMovementResponse
    undated_calls: int
    available_weeks: list[date] = Field(
        description="Every week the corpus spans, oldest first — what a period "
        "picker offers, as distinct from `points`, which is only the anchored window."
    )
    available_months: list[date] = Field(
        description="Every month that actually contains a call, oldest first, as "
        "first-of-month dates. Not the same set as the months of `available_weeks`: "
        "a week starting 31 August whose calls all fall in September would otherwise "
        "offer an August the corpus cannot answer for."
    )


class CallerBreakdownResponse(BaseModel):
    caller_type: str
    calls: int
    share: float
    resolution_rate: float
    average_score: float
    average_handle_minutes: float | None


class HourlyPointResponse(BaseModel):
    hour: int
    label: str
    calls: int
    average_score: float | None
    resolution_rate: float | None
    average_handle_minutes: float | None = Field(
        description=(
            "Mean handle time for this hour in minutes, over the calls that stated one. "
            "Null where none did — an hour that is unmeasured, not an hour that is instant."
        )
    )
    is_thin: bool = Field(description="Too few calls in this hour to read anything into.")


class WorkMixResponse(BaseModel):
    callers: list[CallerBreakdownResponse]
    caller_total: int
    unattributed_calls: int
    hours: list[HourlyPointResponse]
    busiest_hour: str | None
    weakest_hour: str | None


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
    "/time-value",
    response_model=TimeValueResponse,
    summary="What the time on calls bought, in minutes",
)
async def get_time_value(use_case: TimeValueDep) -> TimeValueResponse:
    result = await use_case.execute()
    return TimeValueResponse(
        total_minutes=result.total_minutes,
        resolved_minutes=result.resolved_minutes,
        unproductive_minutes=result.unproductive_minutes,
        productive_share=result.productive_share,
        resolved_median_minutes=result.resolved_median_minutes,
        fast_fail=FailureModeResponse(**result.fast_fail.__dict__),
        slow_fail=FailureModeResponse(**result.slow_fail.__dict__),
        categories=[
            CategoryMinutesResponse(
                code=entry.code,
                label=entry.label,
                total_minutes=entry.total_minutes,
                resolved_minutes=entry.resolved_minutes,
                unproductive_minutes=entry.unproductive_minutes,
                unproductive_share=entry.unproductive_share,
                by_outcome=[
                    OutcomeMinutesResponse(**outcome.__dict__) for outcome in entry.by_outcome
                ],
            )
            for entry in result.categories
        ],
    )


@router.get(
    "/resolution-time",
    response_model=ResolutionTimeResponse,
    summary="How long it takes to resolve a member's problem, by category",
)
async def get_resolution_time(use_case: ResolutionTimeDep) -> ResolutionTimeResponse:
    result = await use_case.execute()
    return ResolutionTimeResponse(
        resolved_calls=result.resolved_calls,
        total_calls=result.total_calls,
        median_minutes=result.median_minutes,
        longest_minutes=result.longest_minutes,
        bands=[DurationBandResponse(**band.__dict__) for band in result.bands],
        categories=[
            CategoryResolutionTimeResponse(**entry.__dict__) for entry in result.categories
        ],
    )


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
        ],
        factor_vocabulary=[
            RiskFactorResponse(
                code=factor.value, label=factor.label, short_label=factor.short_label
            )
            for factor in RiskFactor
        ],
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


def _trend_point(point: TrendPoint) -> TrendPointResponse:
    return TrendPointResponse(
        starting=point.starting,
        label=point.label,
        calls=point.calls,
        median_score=point.median_score,
        resolution_rate=point.resolution_rate,
        median_handle_minutes=point.median_handle_minutes,
    )


def _difference(later: float | None, earlier: float | None) -> float | None:
    """The move between two weeks, or None when either week did not measure it."""
    if later is None or earlier is None:
        return None
    return round(later - earlier, 1)


@router.get(
    "/pulse",
    response_model=PulseResponse,
    summary="Which way the centre is moving, week by week",
)
async def get_pulse(
    use_case: PulseDep,
    # Query() as a default is FastAPI's own idiom for declaring a query
    # parameter's metadata; ruff's B008 doesn't special-case this annotation
    # shape, but the call is inert (it builds a field spec, not a value).
    anchor: date | None = Query(  # noqa: B008
        default=None, description="End the window on the week containing this date."
    ),
    month: date | None = Query(  # noqa: B008
        default=None,
        description="Every week of this date's calendar month, instead of a trailing window.",
    ),
    centre: date | None = Query(  # noqa: B008
        default=None,
        description="The week either side of this date's own week, instead of a trailing "
        "window. Empty if this date does not fall in any week the corpus has.",
    ),
    bucket: Bucket = Query(  # noqa: B008
        default=Bucket.WEEK,
        description="What one point covers. Months are re-bucketed from the calls "
        "themselves, so a month's median is the median of its own calls and not "
        "the median of its weekly medians.",
    ),
) -> PulseResponse:
    pulse = await use_case.execute(anchor=anchor, month=month, centre=centre, bucket=bucket)
    latest, previous = pulse.trend.latest, pulse.trend.previous

    delta = (
        TrendDeltaResponse(
            calls=latest.calls - previous.calls,
            median_score=_difference(latest.median_score, previous.median_score),
            resolution_rate=_difference(latest.resolution_rate, previous.resolution_rate),
            median_handle_minutes=_difference(
                latest.median_handle_minutes, previous.median_handle_minutes
            ),
        )
        if latest and previous
        else None
    )

    return PulseResponse(
        points=[_trend_point(point) for point in pulse.trend.points],
        latest=_trend_point(latest) if latest else None,
        previous=_trend_point(previous) if previous else None,
        delta=delta,
        sentiment=SentimentMovementResponse(
            improved=pulse.sentiment.improved,
            unchanged=pulse.sentiment.unchanged,
            worsened=pulse.sentiment.worsened,
            unclassified=pulse.sentiment.unclassified,
            improved_rate=pulse.sentiment.improved_rate,
        ),
        undated_calls=pulse.trend.undated_calls,
        available_weeks=list(pulse.available_weeks),
        available_months=list(pulse.available_months),
    )


@router.get(
    "/work-mix",
    response_model=WorkMixResponse,
    summary="Who calls, and when the calls come",
)
async def get_work_mix(use_case: WorkMixDep) -> WorkMixResponse:
    mix = await use_case.execute()
    return WorkMixResponse(
        callers=[
            CallerBreakdownResponse(
                caller_type=row.caller_type,
                calls=row.calls,
                share=row.share,
                resolution_rate=row.resolution_rate,
                average_score=row.average_score,
                average_handle_minutes=row.average_handle_minutes,
            )
            for row in mix.callers.callers
        ],
        caller_total=mix.callers.total_calls,
        unattributed_calls=mix.callers.unattributed_calls,
        hours=[
            HourlyPointResponse(
                hour=point.hour,
                label=point.label,
                calls=point.calls,
                average_score=point.average_score,
                resolution_rate=point.resolution_rate,
                average_handle_minutes=point.average_handle_minutes,
                is_thin=point.is_thin,
            )
            for point in mix.hours.hours
        ],
        busiest_hour=mix.hours.busiest.label if mix.hours.busiest else None,
        weakest_hour=mix.hours.weakest.label if mix.hours.weakest else None,
    )
