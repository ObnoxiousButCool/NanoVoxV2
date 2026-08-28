"""SQL aggregate queries behind the dashboard.

Grouping and counting happen here; the derived statistics happen in the domain.

Three counting rules are enforced in SQL and are each easy to get subtly wrong:

* **L4 categories count *calls*, not signals.** A call raising two compliance
  findings is one call with a compliance problem, not two.
* **Broker signals count *signals*, not calls**, because a broker's scorecard is
  a tally of what members reported about them.
* **Filters are applied before pagination**, so the total a caller sees is the
  total that matches — filtering after the fact would report a page size as a
  result count.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, case, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.read_models import (
    AgentAggregate,
    BrokerAggregate,
    CallFilters,
    CallSummary,
    KeyCount,
    Page,
    ReadModelRepository,
)
from domain.value_objects.polarity import Polarity
from domain.value_objects.resolution import Resolution
from domain.value_objects.score import ScoreStatus
from infrastructure.persistence.tables import (
    BrokerSignalRow,
    CallRow,
    CallSignalRow,
    L4SignalRow,
)

# The calls list surfaces what needs action first — the prototype's stated sort,
# "by severity, not date". A withheld score outranks a confirmed one, then the
# lowest scores, then the most recent.
_SEVERITY_ORDER = (
    CallRow.score_status.desc(),
    CallRow.score.asc(),
    CallRow.analysed_at.desc(),
)


def _count_if(condition: Any) -> Any:
    """Portable conditional count. ``CASE`` rather than SQLite's ``IIF``."""
    return func.sum(case((condition, 1), else_=0))


class SqlReadModelRepository(ReadModelRepository):
    """Aggregate queries over the calls tables."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def total_calls(self) -> int:
        async with self._session_factory() as session:
            return int(await session.scalar(select(func.count()).select_from(CallRow)) or 0)

    async def scores(self) -> tuple[int, ...]:
        async with self._session_factory() as session:
            rows = await session.scalars(select(CallRow.score))
            return tuple(int(value) for value in rows)

    async def provisional_score_count(self) -> int:
        async with self._session_factory() as session:
            return int(
                await session.scalar(
                    select(func.count())
                    .select_from(CallRow)
                    .where(CallRow.score_status == ScoreStatus.PROVISIONAL.value)
                )
                or 0
            )

    async def resolution_counts(self) -> tuple[KeyCount, ...]:
        async with self._session_factory() as session:
            rows = await session.execute(
                select(CallRow.resolution, func.count()).group_by(CallRow.resolution)
            )
            return tuple(KeyCount(key=str(key), count=int(count)) for key, count in rows)

    async def category_counts(self) -> tuple[KeyCount, ...]:
        unresolved = _count_if(CallRow.resolution == Resolution.UNRESOLVED.value)
        async with self._session_factory() as session:
            rows = await session.execute(
                select(
                    CallRow.category_code,
                    func.count(),
                    unresolved,
                    func.group_concat(CallRow.reference),
                )
                .group_by(CallRow.category_code)
                .order_by(func.count().desc())
            )
            return tuple(
                KeyCount(
                    key=str(code),
                    count=int(count),
                    unresolved=int(open_count or 0),
                    references=_split(references),
                )
                for code, count, open_count, references in rows
            )

    async def agent_aggregates(self) -> tuple[AgentAggregate, ...]:
        async with self._session_factory() as session:
            rows = await session.execute(
                select(
                    CallRow.agent_name,
                    func.count(),
                    func.avg(CallRow.score),
                    func.min(CallRow.score),
                    func.max(CallRow.score),
                    _count_if(CallRow.resolution == Resolution.UNRESOLVED.value),
                    _count_if(CallRow.resolution == Resolution.ESCALATED.value),
                )
                .where(CallRow.agent_name.is_not(None))
                .group_by(CallRow.agent_name)
                .order_by(func.avg(CallRow.score).desc())
            )
            return tuple(
                AgentAggregate(
                    agent_name=str(name),
                    call_count=int(count),
                    average_score=round(float(average or 0), 1),
                    min_score=int(lowest or 0),
                    max_score=int(highest or 0),
                    unresolved=int(unresolved or 0),
                    escalated=int(escalated or 0),
                )
                for name, count, average, lowest, highest, unresolved, escalated in rows
            )

    async def broker_aggregates(self) -> tuple[BrokerAggregate, ...]:
        async with self._session_factory() as session:
            rows = await session.execute(
                select(
                    BrokerSignalRow.broker_name,
                    func.count(),
                    _count_if(BrokerSignalRow.polarity == Polarity.NEGATIVE.value),
                    _count_if(BrokerSignalRow.polarity == Polarity.POSITIVE.value),
                    func.group_concat(distinct(CallRow.reference)),
                )
                .join(CallRow, CallRow.id == BrokerSignalRow.call_id)
                .group_by(BrokerSignalRow.broker_name)
                .order_by(func.count().desc())
            )
            return tuple(
                BrokerAggregate(
                    broker_name=str(name),
                    signals=int(count),
                    negative=int(negative or 0),
                    positive=int(positive or 0),
                    call_references=_split(references),
                )
                for name, count, negative, positive, references in rows
            )

    async def l4_category_counts(self) -> tuple[KeyCount, ...]:
        calls = func.count(distinct(L4SignalRow.call_id))
        async with self._session_factory() as session:
            rows = await session.execute(
                select(
                    L4SignalRow.category_code,
                    calls,
                    func.group_concat(distinct(CallRow.reference)),
                )
                .join(CallRow, CallRow.id == L4SignalRow.call_id)
                .group_by(L4SignalRow.category_code)
                .order_by(calls.desc())
            )
            return tuple(
                KeyCount(key=str(code), count=int(count), references=_split(references))
                for code, count, references in rows
            )

    async def signal_counts(self) -> tuple[KeyCount, ...]:
        unresolved = _count_if(CallRow.resolution == Resolution.UNRESOLVED.value)
        async with self._session_factory() as session:
            rows = await session.execute(
                select(
                    CallSignalRow.code,
                    func.count(distinct(CallSignalRow.call_id)),
                    unresolved,
                    func.group_concat(distinct(CallRow.reference)),
                )
                .join(CallRow, CallRow.id == CallSignalRow.call_id)
                .group_by(CallSignalRow.code)
                .order_by(func.count(distinct(CallSignalRow.call_id)).desc())
            )
            return tuple(
                KeyCount(
                    key=str(code),
                    count=int(count),
                    unresolved=int(open_count or 0),
                    references=_split(references),
                )
                for code, count, open_count, references in rows
            )

    async def list_calls(
        self, filters: CallFilters, *, limit: int, offset: int, order_by_severity: bool = True
    ) -> Page:
        async with self._session_factory() as session:
            total = int(
                await session.scalar(_apply(select(func.count()).select_from(CallRow), filters))
                or 0
            )

            statement = _apply(select(CallRow), filters)
            statement = statement.order_by(
                *(_SEVERITY_ORDER if order_by_severity else (CallRow.analysed_at.desc(),))
            )
            rows = (await session.scalars(statement.limit(limit).offset(offset))).all()
            call_ids = tuple(row.id for row in rows)

            brokers = await _names_by_call(
                session,
                select(BrokerSignalRow.call_id, BrokerSignalRow.broker_name).where(
                    BrokerSignalRow.call_id.in_(call_ids)
                ),
                call_ids,
            )
            signals = await _names_by_call(
                session,
                select(CallSignalRow.call_id, CallSignalRow.code).where(
                    CallSignalRow.call_id.in_(call_ids)
                ),
                call_ids,
            )

        return Page(
            items=tuple(
                _to_summary(row, signals.get(row.id, ()), brokers.get(row.id, ())) for row in rows
            ),
            total=total,
            limit=limit,
            offset=offset,
        )

    async def distinct_agents(self) -> tuple[str, ...]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(distinct(CallRow.agent_name))
                .where(CallRow.agent_name.is_not(None))
                .order_by(CallRow.agent_name)
            )
            return tuple(str(name) for name in rows)

    async def provenance_models(self) -> tuple[str, ...]:
        async with self._session_factory() as session:
            rows = await session.execute(
                select(CallRow.provider, CallRow.model)
                .distinct()
                .order_by(CallRow.provider, CallRow.model)
            )
            return tuple(f"{provider}/{model}" for provider, model in rows)


async def _names_by_call(
    session: AsyncSession, statement: Select[Any], call_ids: tuple[int, ...]
) -> dict[int, tuple[str, ...]]:
    if not call_ids:
        return {}
    rows = await session.execute(statement)
    collected: dict[int, list[str]] = {}
    for call_id, value in rows:
        collected.setdefault(int(call_id), []).append(str(value))
    return {call_id: tuple(sorted(set(values))) for call_id, values in collected.items()}


def _split(concatenated: object) -> tuple[str, ...]:
    if not isinstance(concatenated, str) or not concatenated:
        return ()
    return tuple(sorted({part for part in concatenated.split(",") if part}))


def _to_summary(
    row: CallRow, signal_codes: tuple[str, ...], broker_names: tuple[str, ...]
) -> CallSummary:
    return CallSummary(
        id=row.id,
        reference=row.reference,
        title=row.title,
        summary=row.summary,
        category_code=row.category_code,
        agent_name=row.agent_name,
        resolution=row.resolution,
        score=row.score,
        score_status=row.score_status,
        tier=row.tier,
        source=row.source,
        analysed_at=row.analysed_at,
        signal_codes=signal_codes,
        broker_names=broker_names,
    )


def _apply(statement: Select[Any], filters: CallFilters) -> Select[Any]:
    """Narrow a query by the caller's filters. Applied before counting or paging."""
    if filters.category_code:
        statement = statement.where(CallRow.category_code == filters.category_code)
    if filters.agent_name:
        statement = statement.where(CallRow.agent_name == filters.agent_name)
    if filters.resolution:
        statement = statement.where(CallRow.resolution == filters.resolution)
    if filters.max_score is not None:
        statement = statement.where(CallRow.score <= filters.max_score)
    if filters.min_score is not None:
        statement = statement.where(CallRow.score >= filters.min_score)
    if filters.has_broker_signal is not None:
        having = CallRow.id.in_(select(BrokerSignalRow.call_id))
        statement = statement.where(having if filters.has_broker_signal else ~having)
    if filters.signal_code:
        statement = statement.where(
            CallRow.id.in_(
                select(CallSignalRow.call_id).where(CallSignalRow.code == filters.signal_code)
            )
        )
    if filters.search:
        pattern = f"%{filters.search}%"
        statement = statement.where(
            or_(
                CallRow.title.ilike(pattern),
                CallRow.summary.ilike(pattern),
                CallRow.reference.ilike(pattern),
            )
        )
    return statement
