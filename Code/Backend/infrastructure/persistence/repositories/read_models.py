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

from collections.abc import Mapping
from typing import Any

from sqlalchemy import Select, case, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.read_models import (
    AgentAggregate,
    BrokerAggregate,
    CallFact,
    CallFilters,
    CallSort,
    CallSummary,
    KeyCount,
    Page,
    ReadModelRepository,
)
from domain.aggregation.member_risk import UNHAPPY_ENDINGS, MemberCalls
from domain.aggregation.signal_attribution import L4Finding
from domain.aggregation.time_value import CallTime
from domain.attribution_notes import broker_name_in
from domain.value_objects.polarity import Polarity
from domain.value_objects.resolution import Resolution
from domain.value_objects.score import ScoreStatus
from domain.value_objects.severity import Severity
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

# Which column each sortable name maps to. Values arrive from a query string, so
# ordering is chosen from this table rather than built from the caller's text.
_SORT_COLUMNS: dict[CallSort, Any] = {
    CallSort.REFERENCE: CallRow.reference,
    CallSort.CATEGORY: CallRow.category_code,
    CallSort.AGENT: CallRow.agent_name,
    CallSort.RESOLUTION: CallRow.resolution,
    CallSort.SCORE: CallRow.score,
    CallSort.ANALYSED_AT: CallRow.analysed_at,
}


def _order_clauses(sort: CallSort, *, descending: bool) -> list[Any]:
    """The ORDER BY for one sort choice.

    Every ordering ends with the call id. Without a unique final key, rows that
    tie on every other column have no defined order between them, and SQLite is
    free to return them differently for each page — which shows up as a row
    appearing twice while another never appears at all.
    """
    if sort is CallSort.SEVERITY:
        clauses = [clause.reverse_sort() if descending else clause for clause in _SEVERITY_ORDER]
        return [*clauses, CallRow.id.asc()]

    column = _SORT_COLUMNS[sort]
    clauses = []
    if sort is CallSort.AGENT:
        # The only nullable sortable column. A block of dashes at the top is not
        # what "sort by agent" means, so absent names go last either way.
        clauses.append(case((CallRow.agent_name.is_(None), 1), else_=0).asc())
    clauses.append(column.desc() if descending else column.asc())
    return [*clauses, CallRow.id.asc()]


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
                    _count_if(CallRow.resolution == Resolution.RESOLVED.value),
                    _count_if(CallRow.resolution == Resolution.PARTIALLY_RESOLVED.value),
                    _count_if(CallRow.resolution == Resolution.ESCALATED.value),
                    _count_if(CallRow.resolution == Resolution.UNRESOLVED.value),
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
                    resolved=int(resolved or 0),
                    partially_resolved=int(partial or 0),
                    escalated=int(escalated or 0),
                    unresolved=int(unresolved or 0),
                )
                for (
                    name,
                    count,
                    average,
                    lowest,
                    highest,
                    resolved,
                    partial,
                    escalated,
                    unresolved,
                ) in rows
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
            discarded = await self._discarded_attributions(session)
            return tuple(
                BrokerAggregate(
                    broker_name=str(name),
                    signals=int(count),
                    negative=int(negative or 0),
                    positive=int(positive or 0),
                    call_references=_split(references),
                    discarded=discarded.get(str(name), 0),
                )
                for name, count, negative, positive, references in rows
            )

    @staticmethod
    async def _discarded_attributions(session: AsyncSession) -> dict[str, int]:
        """How many attributions were refused, per broker named in them.

        Read in Python rather than SQL because the notes are a JSON array of
        sentences; SQLite's JSON functions could unnest them but not parse the
        name back out, which is the part that has to stay next to the code that
        writes it.
        """
        counts: dict[str, int] = {}
        rows = await session.scalars(
            select(CallRow.rejected_attribution_notes).where(
                CallRow.rejected_attribution_notes.is_not(None)
            )
        )
        for notes in rows:
            for note in notes or ():
                name = broker_name_in(note)
                if name:
                    counts[name] = counts.get(name, 0) + 1
        return counts

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

    async def l4_findings(self) -> tuple[L4Finding, ...]:
        """Every L4 finding as a row, for attribution that needs the severities."""
        async with self._session_factory() as session:
            rows = await session.execute(
                select(L4SignalRow.call_id, L4SignalRow.category_code, L4SignalRow.severity)
            )
            return tuple(
                L4Finding(
                    call_id=int(call_id),
                    category_code=str(code),
                    severity=Severity(str(severity)),
                )
                for call_id, code, severity in rows
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

    async def call_times(self) -> tuple[CallTime, ...]:
        """Every timed call, reduced to what the minute ledger needs."""
        async with self._session_factory() as session:
            rows = await session.execute(
                select(
                    CallRow.category_code,
                    CallRow.resolution,
                    CallRow.duration_minutes,
                    CallRow.score,
                ).where(CallRow.duration_minutes.is_not(None))
            )
            return tuple(
                CallTime(
                    category_code=str(code),
                    resolution=str(resolution),
                    duration_minutes=int(minutes),
                    score=int(score),
                )
                for code, resolution, minutes, score in rows
            )

    async def resolved_durations_by_category(self) -> Mapping[str, tuple[int, ...]]:
        """Resolved calls' durations, per category."""
        async with self._session_factory() as session:
            rows = await session.execute(
                select(CallRow.category_code, CallRow.duration_minutes)
                .where(CallRow.resolution == Resolution.RESOLVED.value)
                .where(CallRow.duration_minutes.is_not(None))
            )
            grouped: dict[str, list[int]] = {}
            for code, minutes in rows:
                grouped.setdefault(str(code), []).append(int(minutes))
            return {code: tuple(values) for code, values in grouped.items()}

    async def call_durations(self) -> tuple[int, ...]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(CallRow.duration_minutes).where(CallRow.duration_minutes.is_not(None))
            )
            # The None check is redundant against the WHERE, but the column is
            # nullable and the type says so.
            return tuple(int(value) for value in rows if value is not None)

    async def member_call_counts(self) -> tuple[MemberCalls, ...]:
        """Per-member totals, counted in SQL.

        Calls with no member identifier are excluded, not grouped: they are
        different unknown people, and folding them together would invent one
        member with a hundred calls.
        """
        unhappy = _count_if(CallRow.sentiment_end.in_(tuple(UNHAPPY_ENDINGS)))
        async with self._session_factory() as session:
            rows = await session.execute(
                select(
                    CallRow.member_id,
                    # Any call of theirs that stated a name; they agree across a
                    # member's calls, and MAX simply ignores the nulls.
                    func.max(CallRow.member_name),
                    func.count(),
                    func.coalesce(func.sum(CallRow.duration_minutes), 0),
                    _count_if(CallRow.resolution == Resolution.RESOLVED.value),
                    _count_if(CallRow.resolution == Resolution.UNRESOLVED.value),
                    _count_if(CallRow.resolution == Resolution.ESCALATED.value),
                    unhappy,
                    func.min(CallRow.score),
                    func.group_concat(CallRow.reference),
                )
                .where(CallRow.member_id.is_not(None))
                .group_by(CallRow.member_id)
            )
            members = []
            for (
                member_id,
                member_name,
                count,
                minutes,
                resolved,
                unresolved,
                escalated,
                ended_unhappy,
                lowest,
                refs,
            ) in rows:
                references = _split(refs)
                members.append(
                    MemberCalls(
                        member_id=str(member_id),
                        member_name=str(member_name) if member_name else None,
                        call_count=int(count),
                        total_minutes=int(minutes or 0),
                        resolved=int(resolved or 0),
                        unresolved=int(unresolved or 0),
                        escalated=int(escalated or 0),
                        ended_unhappy=int(ended_unhappy or 0),
                        lowest_score=int(lowest or 0),
                        # Newest last in the concatenation is not guaranteed, so
                        # the reference that sorts highest stands in for "latest":
                        # references are allocated in order.
                        latest_reference=max(references) if references else "",
                        references=references,
                    )
                )
            return tuple(members)

    async def list_calls(
        self,
        filters: CallFilters,
        *,
        limit: int,
        offset: int,
        sort: CallSort = CallSort.SEVERITY,
        descending: bool = False,
    ) -> Page:
        async with self._session_factory() as session:
            total = int(
                await session.scalar(_apply(select(func.count()).select_from(CallRow), filters))
                or 0
            )

            statement = _apply(select(CallRow), filters)
            statement = statement.order_by(*_order_clauses(sort, descending=descending))
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

    async def call_facts(self) -> tuple[CallFact, ...]:
        """Every call, reduced to the dimensions the dashboard slices by."""
        async with self._session_factory() as session:
            rows = await session.execute(
                select(
                    CallRow.started_at,
                    CallRow.score,
                    CallRow.resolution,
                    CallRow.duration_seconds,
                    CallRow.caller_type,
                    CallRow.sentiment_start,
                    CallRow.sentiment_end,
                )
            )
            return tuple(
                CallFact(
                    started_at=started_at,
                    score=int(score),
                    resolution=str(resolution),
                    duration_seconds=int(seconds) if seconds is not None else None,
                    caller_type=str(caller) if caller else None,
                    sentiment_start=str(start) if start else None,
                    sentiment_end=str(end) if end else None,
                )
                for started_at, score, resolution, seconds, caller, start, end in rows
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
        member_id=row.member_id,
        member_name=row.member_name,
        caller_type=row.caller_type,
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
    if filters.broker_name:
        # A call is matched by the brokers named on it, not by a column of its
        # own: one call can attribute several brokers.
        statement = statement.where(
            CallRow.id.in_(
                select(BrokerSignalRow.call_id).where(
                    BrokerSignalRow.broker_name == filters.broker_name
                )
            )
        )
    if filters.caller_type:
        statement = statement.where(CallRow.caller_type == filters.caller_type)
    if filters.member_id:
        statement = statement.where(CallRow.member_id == filters.member_id)
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
