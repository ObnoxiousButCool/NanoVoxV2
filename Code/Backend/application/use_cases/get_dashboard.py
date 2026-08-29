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
from domain.aggregation.significance import AgentRating, rate_agent
from domain.aggregation.statistics import (
    Histogram,
    HistogramSettings,
    build_histogram,
    mean,
    median,
    percentage,
)
from domain.scoring.rubric import Rubric
from domain.taxonomy import Taxonomy
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

    async def execute(self) -> Overview:
        total = await self._repository.total_calls()
        scores = await self._repository.scores()
        resolutions = {row.key: row.count for row in await self._repository.resolution_counts()}
        categories = await self._repository.category_counts()
        brokers = await self._repository.broker_aggregates()
        signals = await self._repository.signal_counts()
        l4_counts = await self._repository.l4_category_counts()

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

    async def execute(self) -> tuple[AgentPerformance, ...]:
        aggregates = await self._repository.agent_aggregates()
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


class GetSignalDistribution:
    """Builds the L4 signal distribution and the per-owner load."""

    def __init__(self, repository: ReadModelRepository, taxonomy: Taxonomy) -> None:
        self._repository = repository
        self._taxonomy = taxonomy

    async def execute(self) -> tuple[tuple[SignalDistributionEntry, ...], tuple[OwnerLoad, ...]]:
        total = await self._repository.total_calls()
        counts = {row.key: row.count for row in await self._repository.l4_category_counts()}

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

        by_owner: dict[str, int] = {}
        for entry in entries:
            by_owner[entry.owner] = by_owner.get(entry.owner, 0) + entry.count

        loads = tuple(
            OwnerLoad(owner=owner, count=count)
            for owner, count in sorted(by_owner.items(), key=lambda item: (-item[1], item[0]))
        )
        return entries, loads
