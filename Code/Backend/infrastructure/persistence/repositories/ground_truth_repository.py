"""SQLAlchemy implementation of the ground truth repository (plan A3).

Written once per run, read only by the fidelity report. Nothing in the dashboard
path touches this table, and that separation is the point: these are figures a
person wrote, and the system must never be able to present one as a measurement.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.clock import Clock
from application.ports.ground_truth_repository import GroundTruthRepository
from domain.entities.corpus_call import CorpusCall
from domain.entities.ground_truth import GroundTruth
from infrastructure.persistence.tables import GroundTruthRow


class SqlGroundTruthRepository(GroundTruthRepository):
    """Stores authored corpus expectations in SQLite."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], clock: Clock) -> None:
        self._session_factory = session_factory
        self._clock = clock

    async def upsert_many(self, calls: Sequence[CorpusCall]) -> int:
        if not calls:
            return 0

        now = self._clock.now()
        async with self._session_factory() as session:
            existing = await self._by_reference(session, [call.reference for call in calls])
            written = 0
            for call in calls:
                if call.ground_truth is None:
                    continue
                row = existing.get(call.reference)
                if row is None:
                    row = GroundTruthRow(reference=call.reference)
                    session.add(row)
                _apply(row, call, call.ground_truth, now)
                written += 1
            await session.commit()
            return written

    async def get(self, reference: str) -> GroundTruth | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(GroundTruthRow).where(GroundTruthRow.reference == reference)
            )
            return _to_domain(row) if row is not None else None

    async def _by_reference(
        self, session: AsyncSession, references: Sequence[str]
    ) -> dict[str, GroundTruthRow]:
        rows = await session.scalars(
            select(GroundTruthRow).where(GroundTruthRow.reference.in_(references))
        )
        return {row.reference: row for row in rows}


def _apply(row: GroundTruthRow, call: CorpusCall, truth: GroundTruth, now: datetime) -> None:
    row.source_id = call.source_id
    row.title = call.title
    row.agent_name = truth.agent_name
    row.tier = truth.tier
    row.score = truth.score
    row.resolution = truth.resolution
    row.sentiment_start = truth.sentiment_start
    row.sentiment_end = truth.sentiment_end
    row.topics = list(truth.topics)
    row.broker_names = list(truth.broker_names)
    row.member_context = truth.member_context
    row.panel_text = truth.panel_text
    row.recorded_at = now


def _to_domain(row: GroundTruthRow) -> GroundTruth:
    return GroundTruth(
        agent_name=row.agent_name,
        tier=row.tier,
        score=row.score,
        resolution=row.resolution,
        sentiment_start=row.sentiment_start,
        sentiment_end=row.sentiment_end,
        topics=tuple(row.topics),
        broker_names=tuple(row.broker_names),
        member_context=row.member_context,
        panel_text=row.panel_text,
    )
