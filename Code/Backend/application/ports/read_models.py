"""Read-model port: the aggregate rows the dashboard is computed from.

The split is deliberate. SQL does the grouping and counting, which is what it is
good at; the derived statistics — median, histogram, tier, significance,
percentages — are pure domain functions over these rows. That way every
definition on the dashboard is testable without a database, and there is exactly
one place where each figure is defined.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum

from domain.aggregation.member_risk import MemberCalls
from domain.aggregation.signal_attribution import L4Finding
from domain.aggregation.time_value import CallTime


@dataclass(frozen=True)
class CallSummary:
    """One row of the calls table."""

    id: int
    reference: str
    title: str
    summary: str
    category_code: str
    agent_name: str | None
    member_id: str | None
    member_name: str | None
    # MEMBER, EMPLOYER or BROKER. The row shows it because half the corpus is
    # not a member calling, and a blank member column does not say which.
    caller_type: str | None
    resolution: str
    score: int
    score_status: str
    tier: str
    source: str
    analysed_at: datetime
    signal_codes: tuple[str, ...] = ()
    broker_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class Page:
    """A slice of results with the total available."""

    items: tuple[CallSummary, ...]
    total: int
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total


class CallSort(str, Enum):
    """A column the calls list may be ordered by.

    An allowlist, not a column name passed through: the value arrives from a
    query string, and mapping it to a column here is what stops it reaching SQL.
    """

    SEVERITY = "severity"
    REFERENCE = "reference"
    CATEGORY = "category"
    AGENT = "agent"
    RESOLUTION = "resolution"
    SCORE = "score"
    ANALYSED_AT = "analysed_at"


@dataclass(frozen=True)
class CallFilters:
    """Filters the calls list accepts. All are optional and combine with AND."""

    category_code: str | None = None
    agent_name: str | None = None
    resolution: str | None = None
    max_score: int | None = None
    min_score: int | None = None
    has_broker_signal: bool | None = None
    broker_name: str | None = None
    signal_code: str | None = None
    # An L4 finding category, which is the finding taxonomy rather than the call
    # category above: a Coverage & Benefits call can raise a Process Breakdown
    # finding. Needed because the attention queue counts calls by L4 category
    # and an item that cannot be opened is a claim the reader has to take on
    # trust.
    l4_category_code: str | None = None
    # The hour of the day a call started, 0-23, in the wall-clock the source
    # stated. No zone is applied, for the same reason the hourly chart applies
    # none: the corpus never gave one, and inventing one here would silently
    # move calls between bars and make the drill-down disagree with the chart
    # it was opened from.
    started_hour: int | None = None
    # MEMBER, EMPLOYER or BROKER. Matched exactly rather than by prefix: these
    # are three separate populations, not a spectrum.
    caller_type: str | None = None
    # One member's calls. The at-risk list is member-level, so opening it must
    # narrow to that member exactly rather than searching for a reference.
    member_id: str | None = None
    search: str | None = None


@dataclass(frozen=True)
class AgentAggregate:
    """Per-agent totals, straight from SQL. Tier is derived later, in the domain."""

    agent_name: str
    call_count: int
    average_score: float
    min_score: int
    max_score: int
    # All four outcomes, because the dashboard draws them as proportions of the
    # agent's calls. Deriving "resolved" as the remainder would silently absorb
    # any outcome added later.
    resolved: int
    partially_resolved: int
    escalated: int
    unresolved: int


@dataclass(frozen=True)
class CallFact:
    """One call, reduced to the dimensions the dashboard slices by.

    Fetched once and sliced in the domain — by week, by hour, by caller, by
    sentiment arc — rather than as four GROUP BYs returning four shapes. At
    dashboard scale the join is the cost, not the rows, and the definitions then
    live in testable functions instead of in SQL.
    """

    started_at: datetime | None
    score: int
    resolution: str
    duration_seconds: int | None
    caller_type: str | None
    sentiment_start: str | None
    sentiment_end: str | None


@dataclass(frozen=True)
class BrokerAggregate:
    """Per-broker signal counts and the calls they came from."""

    broker_name: str
    signals: int
    negative: int
    positive: int
    call_references: tuple[str, ...] = field(default_factory=tuple)
    # Attributions naming this broker that failed evidence checking and were
    # never stored. Counted so the scorecard can say what it is not showing.
    discarded: int = 0


@dataclass(frozen=True)
class KeyCount:
    """A count against a key, with the calls behind it."""

    key: str
    count: int
    unresolved: int = 0
    references: tuple[str, ...] = field(default_factory=tuple)


#: A half-open ``[start, end)`` date range, as returned by
#: ``domain.aggregation.period.resolve_period``. ``None`` everywhere below
#: means all-time — the default, unfiltered behaviour every caller had before
#: the page-level Week/Month filter existed.
Period = tuple[date, date]


class ReadModelRepository(ABC):
    """Aggregate queries over analyzed calls."""

    @abstractmethod
    async def total_calls(self, period: Period | None = None) -> int: ...

    @abstractmethod
    async def scores(self, period: Period | None = None) -> tuple[int, ...]:
        """Every call's score, for distribution statistics."""

    @abstractmethod
    async def provisional_score_count(self) -> int:
        """Calls whose score is withheld pending review.

        Surfaced on the Overview because a provisional score is a call waiting
        on a human, not a settled result.
        """

    @abstractmethod
    async def resolution_counts(self, period: Period | None = None) -> tuple[KeyCount, ...]: ...

    @abstractmethod
    async def category_counts(self, period: Period | None = None) -> tuple[KeyCount, ...]:
        """Calls per call category, with how many of each ended unresolved."""

    @abstractmethod
    async def agent_aggregates(
        self, period: Period | None = None
    ) -> tuple[AgentAggregate, ...]: ...

    @abstractmethod
    async def broker_aggregates(
        self, period: Period | None = None
    ) -> tuple[BrokerAggregate, ...]: ...

    @abstractmethod
    async def l4_category_counts(self, period: Period | None = None) -> tuple[KeyCount, ...]:
        """Calls flagged per L4 category. A call raising two signals of one category counts once."""

    @abstractmethod
    async def l4_findings(self, period: Period | None = None) -> tuple[L4Finding, ...]:
        """Every operational finding, with the call it is on and its severity.

        Rows rather than counts, because the owner rollup has to attribute each
        call to one team, and that cannot be derived from per-category totals:
        it needs to know which findings share a call and which of them is the
        most serious.
        """

    @abstractmethod
    async def signal_counts(self) -> tuple[KeyCount, ...]:
        """Calls raising each signal type."""

    @abstractmethod
    async def call_times(self, period: Period | None = None) -> tuple[CallTime, ...]:
        """Category, outcome, duration and score for every timed call.

        Rows rather than aggregates: the minute ledger has to split failures by
        how they compare with a typical *successful* call, which no per-category
        SUM can answer. Calls with no recorded duration are excluded here so the
        minutes cannot be understated by counting a call as zero.
        """

    @abstractmethod
    async def resolved_durations_by_category(
        self, period: Period | None = None
    ) -> Mapping[str, tuple[int, ...]]:
        """Durations of resolved calls, grouped by category code.

        Resolved only, because the figure this feeds is time *to an answer*. The
        quickest way to end a call is to solve nothing, so including unresolved
        calls would reward exactly the behaviour the dashboard exists to catch.
        """

    @abstractmethod
    async def call_durations(self) -> tuple[int, ...]:
        """Every recorded call duration, in minutes."""

    @abstractmethod
    async def member_call_counts(self) -> tuple[MemberCalls, ...]:
        """Per-member totals, for members whose identifier is known.

        Calls with no identifier are excluded rather than grouped together: an
        unknown member is not a member who called many times.
        """

    @abstractmethod
    async def list_calls(
        self,
        filters: CallFilters,
        *,
        limit: int,
        offset: int,
        sort: CallSort = CallSort.SEVERITY,
        descending: bool = False,
    ) -> Page: ...

    @abstractmethod
    async def call_facts(self, period: Period | None = None) -> tuple[CallFact, ...]:
        """Every analyzed call, reduced to the dimensions the dashboard slices by."""

    @abstractmethod
    async def distinct_agents(self) -> tuple[str, ...]: ...

    @abstractmethod
    async def provenance_models(self) -> tuple[str, ...]:
        """Distinct provider/model pairs behind the stored calls."""
