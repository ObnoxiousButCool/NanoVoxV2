"""Read-model port: the aggregate rows the dashboard is computed from.

The split is deliberate. SQL does the grouping and counting, which is what it is
good at; the derived statistics — median, histogram, tier, significance,
percentages — are pure domain functions over these rows. That way every
definition on the dashboard is testable without a database, and there is exactly
one place where each figure is defined.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class CallSummary:
    """One row of the calls table."""

    id: int
    reference: str
    title: str
    summary: str
    category_code: str
    agent_name: str | None
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


@dataclass(frozen=True)
class CallFilters:
    """Filters the calls list accepts. All are optional and combine with AND."""

    category_code: str | None = None
    agent_name: str | None = None
    resolution: str | None = None
    max_score: int | None = None
    min_score: int | None = None
    has_broker_signal: bool | None = None
    signal_code: str | None = None
    search: str | None = None


@dataclass(frozen=True)
class AgentAggregate:
    """Per-agent totals, straight from SQL. Tier is derived later, in the domain."""

    agent_name: str
    call_count: int
    average_score: float
    min_score: int
    max_score: int
    unresolved: int
    escalated: int


@dataclass(frozen=True)
class BrokerAggregate:
    """Per-broker signal counts and the calls they came from."""

    broker_name: str
    signals: int
    negative: int
    positive: int
    call_references: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class KeyCount:
    """A count against a key, with the calls behind it."""

    key: str
    count: int
    unresolved: int = 0
    references: tuple[str, ...] = field(default_factory=tuple)


class ReadModelRepository(ABC):
    """Aggregate queries over analysed calls."""

    @abstractmethod
    async def total_calls(self) -> int: ...

    @abstractmethod
    async def scores(self) -> tuple[int, ...]:
        """Every call's score, for distribution statistics."""

    @abstractmethod
    async def provisional_score_count(self) -> int:
        """Calls whose score is withheld pending review.

        Surfaced on the Overview because a provisional score is a call waiting
        on a human, not a settled result.
        """

    @abstractmethod
    async def resolution_counts(self) -> tuple[KeyCount, ...]: ...

    @abstractmethod
    async def category_counts(self) -> tuple[KeyCount, ...]:
        """Calls per call category, with how many of each ended unresolved."""

    @abstractmethod
    async def agent_aggregates(self) -> tuple[AgentAggregate, ...]: ...

    @abstractmethod
    async def broker_aggregates(self) -> tuple[BrokerAggregate, ...]: ...

    @abstractmethod
    async def l4_category_counts(self) -> tuple[KeyCount, ...]:
        """Calls flagged per L4 category. A call raising two signals of one category counts once."""

    @abstractmethod
    async def signal_counts(self) -> tuple[KeyCount, ...]:
        """Calls raising each signal type."""

    @abstractmethod
    async def list_calls(
        self, filters: CallFilters, *, limit: int, offset: int, order_by_severity: bool = True
    ) -> Page: ...

    @abstractmethod
    async def distinct_agents(self) -> tuple[str, ...]: ...

    @abstractmethod
    async def provenance_models(self) -> tuple[str, ...]:
        """Distinct provider/model pairs behind the stored calls."""
