"""The dashboard read models.

Each figure here has exactly one definition, stated in plan §6 and implemented
once. Two of them are easy to get wrong in a way that flatters the numbers, so
they are spelled out:

* **First-contact resolution counts only RESOLVED.** Partially resolved is
  excluded. Including it would inflate the figure against the 65-75% industry
  range the dashboard prints beside it.
* **Agents below the significance threshold are shown but not tier-rated.** Four
  of the corpus's thirteen agents have four calls each. Labelling a person on
  that evidence is unfair to them and misleading to the manager reading it.

Categories and owners with no signals are returned with a zero count rather than
omitted, so the absence is visible rather than implied (plan §6.5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from application.ports.read_models import (
    AgentAggregate,
    BrokerAggregate,
    KeyCount,
    ReadModelRepository,
)
from domain.aggregation.attention import (
    AttentionInputs,
    AttentionItem,
    AttentionRule,
    GroupCount,
    evaluate_rules,
)
from domain.aggregation.caller_mix import CallerCall, CallerMix, caller_mix
from domain.aggregation.effort import EffortMetrics, effort_metrics
from domain.aggregation.hourly import HourCall, HourlyLoad, hourly_load
from domain.aggregation.member_risk import MemberAtRisk, members_at_risk
from domain.aggregation.period import resolve_period
from domain.aggregation.resolution_time import (
    DurationBandSettings,
    ResolutionTime,
    resolution_time,
)
from domain.aggregation.sentiment_movement import SentimentMovement
from domain.aggregation.signal_attribution import primary_category_by_call
from domain.aggregation.significance import AgentRating, rate_agent
from domain.aggregation.statistics import (
    Histogram,
    HistogramSettings,
    build_histogram,
    mean,
    median,
    percentage,
)
from domain.aggregation.time_value import TimeValue, time_value
from domain.aggregation.trend import (
    Bucket,
    Trend,
    TrendCall,
    centred_window,
    month_window,
    trend,
    windowed,
)
from domain.scoring.rubric import Rubric
from domain.taxonomy import Taxonomy
from domain.value_objects.caller_type import CallerType
from domain.value_objects.resolution import Resolution
from domain.value_objects.score import Score


@dataclass(frozen=True)
class OverviewMetrics:
    """The metric strip across the top of the Overview screen."""

    total_calls: int
    median_score: float
    mean_score: float
    first_contact_resolution_rate: float
    escalation_rate: float
    unresolved_rate: float
    broker_signal_count: int
    distinct_broker_count: int
    provisional_score_count: int


@dataclass(frozen=True)
class CategoryBreakdown:
    """One bar of "what members call about"."""

    code: str
    label: str
    count: int
    unresolved: int
    percentage_of_total: float


@dataclass(frozen=True)
class Overview:
    """Everything the Overview screen needs."""

    metrics: OverviewMetrics
    histogram: Histogram
    categories: tuple[CategoryBreakdown, ...]
    attention: tuple[AttentionItem, ...]
    taxonomy_coverage: float


@dataclass(frozen=True)
class AgentPerformance:
    """One row of the agent performance table."""

    agent_name: str
    call_count: int
    average_score: float
    min_score: int
    max_score: int
    resolved: int
    partially_resolved: int
    escalated: int
    unresolved: int
    rating: AgentRating


@dataclass(frozen=True)
class BrokerScorecardEntry:
    """One broker's net record."""

    broker_name: str
    signals: int
    negative: int
    positive: int
    call_references: tuple[str, ...]
    discarded: int = 0

    @property
    def is_net_positive(self) -> bool:
        """Net, not cumulative (plan §6.2).

        A broker with one error against otherwise strong performance is a
        coaching signal, not a conduct one. Treating every error as conduct would
        make the scorecard unusable.
        """
        return self.positive > self.negative


@dataclass(frozen=True)
class SignalDistributionEntry:
    """One L4 category's share of the corpus."""

    code: str
    label: str
    owner: str
    count: int
    percentage_of_corpus: float


@dataclass(frozen=True)
class OwnerLoad:
    """How many calls each owning team is carrying."""

    owner: str
    count: int


class GetOverview:
    """Builds the Overview screen's read model."""

    def __init__(
        self,
        repository: ReadModelRepository,
        taxonomy: Taxonomy,
        histogram_settings: HistogramSettings,
        rules: tuple[AttentionRule, ...],
    ) -> None:
        self._repository = repository
        self._taxonomy = taxonomy
        self._histogram = histogram_settings
        self._rules = rules

    async def execute(self, anchor: date | None = None, month: date | None = None) -> Overview:
        period = resolve_period(anchor, month)
        total = await self._repository.total_calls(period)
        scores = await self._repository.scores(period)
        resolutions = {
            row.key: row.count for row in await self._repository.resolution_counts(period)
        }
        categories = await self._repository.category_counts(period)
        brokers = await self._repository.broker_aggregates(period)
        signals = await self._repository.signal_counts()
        l4_counts = await self._repository.l4_category_counts(period)

        metrics = OverviewMetrics(
            total_calls=total,
            median_score=median(scores),
            mean_score=mean(scores),
            first_contact_resolution_rate=percentage(
                resolutions.get(Resolution.RESOLVED.value, 0), total
            ),
            escalation_rate=percentage(resolutions.get(Resolution.ESCALATED.value, 0), total),
            unresolved_rate=percentage(resolutions.get(Resolution.UNRESOLVED.value, 0), total),
            broker_signal_count=sum(broker.signals for broker in brokers),
            distinct_broker_count=len(brokers),
            provisional_score_count=await self._repository.provisional_score_count(),
        )

        return Overview(
            metrics=metrics,
            histogram=build_histogram(
                scores,
                self._histogram.bin_edges,
                coaching_threshold=self._histogram.coaching_threshold,
            ),
            categories=self._categories(categories, total),
            attention=evaluate_rules(
                self._rules,
                AttentionInputs(
                    total_calls=total,
                    signal_counts=self._groups(signals, self._signal_labels()),
                    l4_category_counts=self._groups(l4_counts, self._l4_labels()),
                    broker_negative_counts=tuple(
                        GroupCount(
                            key=broker.broker_name,
                            label=broker.broker_name,
                            count=broker.negative,
                            references=broker.call_references,
                        )
                        for broker in brokers
                    ),
                    category_unresolved_counts=self._groups(categories, self._category_labels()),
                ),
            ),
            taxonomy_coverage=percentage(sum(row.count for row in categories), total),
        )

    def _categories(
        self, counts: tuple[KeyCount, ...], total: int
    ) -> tuple[CategoryBreakdown, ...]:
        by_code = {row.key: row for row in counts}
        # Every configured category appears, including those with no calls.
        return tuple(
            CategoryBreakdown(
                code=category.code,
                label=category.label,
                count=by_code[category.code].count if category.code in by_code else 0,
                unresolved=by_code[category.code].unresolved if category.code in by_code else 0,
                percentage_of_total=percentage(
                    by_code[category.code].count if category.code in by_code else 0, total
                ),
            )
            for category in self._taxonomy.categories
        )

    def _signal_labels(self) -> dict[str, str]:
        return {item.code: item.label for item in self._taxonomy.signal_types}

    def _l4_labels(self) -> dict[str, str]:
        return {item.code: item.label for item in self._taxonomy.l4_categories}

    def _category_labels(self) -> dict[str, str]:
        return {item.code: item.label for item in self._taxonomy.categories}

    @staticmethod
    def _groups(counts: tuple[KeyCount, ...], labels: dict[str, str]) -> tuple[GroupCount, ...]:
        return tuple(
            GroupCount(
                key=row.key,
                label=labels.get(row.key, row.key),
                count=row.count,
                unresolved=row.unresolved,
                references=row.references,
            )
            for row in counts
        )


class GetAgentPerformance:
    """Builds the agent performance table."""

    def __init__(self, repository: ReadModelRepository, rubric: Rubric) -> None:
        self._repository = repository
        self._rubric = rubric

    async def execute(
        self, anchor: date | None = None, month: date | None = None
    ) -> tuple[AgentPerformance, ...]:
        aggregates = await self._repository.agent_aggregates(resolve_period(anchor, month))
        return tuple(self._rate(row) for row in aggregates)

    def _rate(self, row: AgentAggregate) -> AgentPerformance:
        return AgentPerformance(
            agent_name=row.agent_name,
            call_count=row.call_count,
            average_score=row.average_score,
            min_score=row.min_score,
            max_score=row.max_score,
            resolved=row.resolved,
            partially_resolved=row.partially_resolved,
            escalated=row.escalated,
            unresolved=row.unresolved,
            rating=rate_agent(
                average_score=Score(round(row.average_score)),
                call_count=row.call_count,
                minimum=self._rubric.min_calls_for_tier_rating,
                thresholds=self._rubric.tiers,
            ),
        )


@dataclass(frozen=True)
class Pulse:
    """Whether the centre is getting better or worse.

    Every other figure the dashboard reports is an all-time total, which answers
    "how are we doing" and not "which way are we going" — and on this corpus the
    two disagree flatly. Resolution reads 54% overall; the weekly series behind
    it runs 88, 70, 43, 33, 57.
    """

    trend: Trend
    sentiment: SentimentMovement
    # Every week the corpus spans, unwindowed — what a period picker offers,
    # as distinct from ``trend.points``, which is only the anchored window.
    available_weeks: tuple[date, ...]
    # The months that actually contain a call, as first-of-month dates. Not
    # derivable from ``available_weeks``: a week starting 31 August whose
    # calls all fall in September makes August look populated when no call
    # was placed in it, and a picker built from the weeks offers a month the
    # corpus cannot answer for.
    available_months: tuple[date, ...]


@dataclass(frozen=True)
class WorkMix:
    """How the work is distributed — across who calls, and across the day."""

    callers: CallerMix
    hours: HourlyLoad


class GetPulse:
    """Builds the trend: a trailing window ending at ``anchor``, a window
    centred on ``centre``, or a whole calendar ``month`` — whichever one of
    the three is given.

    ``bucket`` decides what one point covers. Weeks are the default and what
    the graph draws; months are for a reader who asked for a month and should
    be given the month's own figures rather than its last week's.
    """

    def __init__(self, repository: ReadModelRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        anchor: date | None = None,
        month: date | None = None,
        centre: date | None = None,
        bucket: Bucket = Bucket.WEEK,
    ) -> Pulse:
        facts = await self._repository.call_facts()
        calls = [
            TrendCall(
                started_at=fact.started_at,
                score=fact.score,
                resolution=fact.resolution,
                duration_seconds=fact.duration_seconds,
            )
            for fact in facts
        ]
        full_trend = trend(calls, bucket)
        # Exactly one of the three ever arrives on a real request — each
        # caller (the trailing-window filter, the centred-window graph, the
        # whole-month graph) builds its own request shape and never mixes
        # them — so precedence between them is academic, not load-bearing.
        if month is not None:
            selected = month_window(full_trend, month)
        elif centre is not None:
            selected = centred_window(full_trend, centre)
        else:
            selected = windowed(full_trend, anchor)
        return Pulse(
            trend=selected,
            # commented out as no longer needed on frontend.
            # sentiment=sentiment_movement(  # noqa: ERA001
            #     SentimentArc(start=fact.sentiment_start, end=fact.sentiment_end)  # noqa: ERA001
            #     for fact in facts
            # ),
            sentiment=SentimentMovement(improved=0, unchanged=0, worsened=0, unclassified=0),
            # Always weekly, whatever this request was bucketed by: this is
            # what both pickers draw their options from, and a month-bucketed
            # request would otherwise empty the week dropdown of the page that
            # made it.
            available_weeks=tuple(
                point.starting
                for point in (full_trend if bucket is Bucket.WEEK else trend(calls)).points
            ),
            available_months=tuple(
                point.starting
                for point in (
                    full_trend if bucket is Bucket.MONTH else trend(calls, Bucket.MONTH)
                ).points
                if point.calls
            ),
        )


class GetWorkMix:
    """Builds the caller breakdown and the hour-of-day load."""

    def __init__(self, repository: ReadModelRepository) -> None:
        self._repository = repository

    async def execute(self, anchor: date | None = None, month: date | None = None) -> WorkMix:
        facts = await self._repository.call_facts(resolve_period(anchor, month))
        return WorkMix(
            callers=caller_mix(
                (
                    CallerCall(
                        caller_type=fact.caller_type,
                        resolution=fact.resolution,
                        score=fact.score,
                        duration_seconds=fact.duration_seconds,
                    )
                    for fact in facts
                ),
                known_types=[member.value for member in CallerType],
            ),
            hours=hourly_load(
                HourCall(
                    started_at=fact.started_at,
                    score=fact.score,
                    resolution=fact.resolution,
                    handle_seconds=fact.duration_seconds,
                )
                for fact in facts
            ),
        )


class GetBrokerScorecard:
    """Builds the broker scorecard."""

    def __init__(self, repository: ReadModelRepository) -> None:
        self._repository = repository

    async def execute(self) -> tuple[BrokerScorecardEntry, ...]:
        return tuple(self._entry(row) for row in await self._repository.broker_aggregates())

    @staticmethod
    def _entry(row: BrokerAggregate) -> BrokerScorecardEntry:
        return BrokerScorecardEntry(
            broker_name=row.broker_name,
            signals=row.signals,
            negative=row.negative,
            positive=row.positive,
            call_references=row.call_references,
            discarded=row.discarded,
        )


class GetEffortMetrics:
    """What getting an answer costs a member (plan §4.2)."""

    def __init__(self, repository: ReadModelRepository) -> None:
        self._repository = repository

    async def execute(self) -> EffortMetrics:
        durations = await self._repository.call_durations()
        members = await self._repository.member_call_counts()
        repeat = tuple(member for member in members if member.call_count > 1)
        # A member's time to an answer is every minute they spent, not just the
        # call that happened to end in a resolution — ringing back is part of
        # what the answer cost them.
        answered = tuple(member for member in members if member.resolved > 0)
        return effort_metrics(
            durations,
            identified_members=len(members),
            repeat_members=len(repeat),
            calls_by_repeat_members=sum(member.call_count for member in repeat),
            minutes_to_answer=tuple(member.total_minutes for member in answered),
            members_without_answer=len(members) - len(answered),
        )


class GetResolutionTime:
    """How long it takes to resolve a member's problem, split by category.

    Resolved calls only. Handle time over every call rewards ending the call,
    not solving the problem, and the two figures are easy to confuse once they
    are on the same screen.
    """

    def __init__(
        self,
        repository: ReadModelRepository,
        taxonomy: Taxonomy,
        bands: DurationBandSettings,
    ) -> None:
        self._repository = repository
        self._taxonomy = taxonomy
        self._bands = bands

    async def execute(
        self, anchor: date | None = None, month: date | None = None
    ) -> ResolutionTime:
        period = resolve_period(anchor, month)
        return resolution_time(
            await self._repository.resolved_durations_by_category(period),
            # Every configured category, so one that never reaches a resolution
            # is visible as a zero rather than missing from the list.
            labels={category.code: category.label for category in self._taxonomy.categories},
            total_calls=await self._repository.total_calls(period),
            settings=self._bands,
        )


class GetTimeValue:
    """What the time on calls bought (the minute ledger).

    Counts minutes rather than calls: "how long is a call" is an operations
    question, "how many of our hours produced an answer" is the one a manager
    answers for.
    """

    def __init__(self, repository: ReadModelRepository, taxonomy: Taxonomy) -> None:
        self._repository = repository
        self._taxonomy = taxonomy

    async def execute(self, anchor: date | None = None, month: date | None = None) -> TimeValue:
        return time_value(
            await self._repository.call_times(resolve_period(anchor, month)),
            labels={category.code: category.label for category in self._taxonomy.categories},
        )


class GetMembersAtRisk:
    """Members showing signs of leaving, ranked by how many (plan §4.3).

    Deliberately not a prediction. Nothing here has been measured against a real
    departure, so the use case reports the signs a member is carrying and leaves
    the judgement to whoever reads it.
    """

    def __init__(self, repository: ReadModelRepository, dashboard: HistogramSettings) -> None:
        self._repository = repository
        self._dashboard = dashboard

    async def execute(self, limit: int = 25) -> tuple[MemberAtRisk, ...]:
        members = await self._repository.member_call_counts()
        ranked = members_at_risk(members, coaching_threshold=self._dashboard.coaching_threshold)
        return ranked[:limit]


class GetSignalDistribution:
    """Builds the L4 signal distribution and the per-owner load."""

    def __init__(self, repository: ReadModelRepository, taxonomy: Taxonomy) -> None:
        self._repository = repository
        self._taxonomy = taxonomy

    async def execute(
        self, anchor: date | None = None, month: date | None = None
    ) -> tuple[tuple[SignalDistributionEntry, ...], tuple[OwnerLoad, ...]]:
        period = resolve_period(anchor, month)
        total = await self._repository.total_calls(period)
        counts = {row.key: row.count for row in await self._repository.l4_category_counts(period)}

        # Every configured category is returned, including those with no signals:
        # "Provider relations has no signals in this sample. Shown so the absence
        # is visible rather than implied."
        entries = tuple(
            SignalDistributionEntry(
                code=category.code,
                label=category.label,
                owner=category.owner.name,
                count=counts.get(category.code, 0),
                percentage_of_corpus=percentage(counts.get(category.code, 0), total),
            )
            for category in self._taxonomy.l4_categories
        )

        # Each call counts for exactly one team: the owner of its most serious
        # finding. Summing per-category counts instead would put a call with two
        # findings on two teams' bars, and both managers would read it as theirs.
        # The category figures above still count both findings, which is true of
        # the call; this rollup answers "how many calls are mine", so it has to
        # total the number of flagged calls.
        primary = primary_category_by_call(
            await self._repository.l4_findings(period), self._taxonomy.l4_categories
        )
        owner_of = {category.code: category.owner.name for category in self._taxonomy.l4_categories}
        # Seeded with every owner at zero, so a team with no findings keeps its
        # row rather than vanishing from the chart.
        by_owner = {category.owner.name: 0 for category in self._taxonomy.l4_categories}
        for code in primary.values():
            by_owner[owner_of[code]] += 1

        loads = tuple(
            OwnerLoad(owner=owner, count=count)
            for owner, count in sorted(by_owner.items(), key=lambda item: (-item[1], item[0]))
        )
        return entries, loads
