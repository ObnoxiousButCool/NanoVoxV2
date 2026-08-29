"""SQLAlchemy implementation of the corpus run repository.

Every method here commits on its own. That is deliberate and is the opposite of
the rule the analysis repository follows: an analysis is one atomic thing, but a
run is a hundred separate facts, and holding them in one transaction would mean a
crash at call ninety-nine leaves no record that the first ninety-eight happened.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from application.ports.run_repository import RunRepository
from domain.entities.corpus_call import CorpusCall
from domain.entities.corpus_run import CorpusRun, CorpusRunItem
from domain.value_objects.run_status import RunItemStatus, RunStatus
from infrastructure.persistence.tables import RunItemRow, RunRow

_ACTIVE_STATUSES = tuple(status.value for status in RunStatus if status.is_active)
_UNFINISHED_ITEM_STATUSES = tuple(status.value for status in RunItemStatus if status.needs_work)


class SqlRunRepository(RunRepository):
    """Stores corpus runs in SQLite."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(
        self,
        *,
        provider: str,
        model: str,
        force: bool,
        calls: Sequence[CorpusCall],
        now: datetime,
    ) -> CorpusRun:
        row = RunRow(
            provider=provider,
            model=model,
            force=force,
            status=RunStatus.PENDING.value,
            message="",
            created_at=now,
            items=[
                RunItemRow(
                    sequence=call.sequence,
                    source_id=call.source_id,
                    reference=call.reference,
                    title=call.title,
                    status=RunItemStatus.PENDING.value,
                    message="",
                )
                for call in calls
            ],
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
            return await self._load(session, row.id)

    async def get(self, run_id: int) -> CorpusRun | None:
        async with self._session_factory() as session:
            row = await self._row(session, run_id)
            return _to_domain(row) if row is not None else None

    async def status_of(self, run_id: int) -> RunStatus | None:
        async with self._session_factory() as session:
            value = await session.scalar(select(RunRow.status).where(RunRow.id == run_id))
            return RunStatus(value) if value is not None else None

    async def recent(self, limit: int) -> tuple[CorpusRun, ...]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(RunRow)
                .options(selectinload(RunRow.items))
                .order_by(RunRow.id.desc())
                .limit(limit)
            )
            return tuple(_to_domain(row) for row in rows)

    async def active(self) -> CorpusRun | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(RunRow)
                .options(selectinload(RunRow.items))
                .where(RunRow.status.in_(_ACTIVE_STATUSES))
                .order_by(RunRow.id.desc())
                .limit(1)
            )
            return _to_domain(row) if row is not None else None

    async def set_status(
        self,
        run_id: int,
        status: RunStatus,
        *,
        now: datetime,
        message: str = "",
    ) -> None:
        values: dict[str, object] = {"status": status.value}
        if message:
            values["message"] = message
        if status is RunStatus.RUNNING:
            values["started_at"] = now
        if status.is_terminal:
            values["finished_at"] = now

        async with self._session_factory() as session:
            await session.execute(update(RunRow).where(RunRow.id == run_id).values(**values))
            await session.commit()

    async def set_item_status(
        self,
        run_id: int,
        source_id: str,
        status: RunItemStatus,
        *,
        now: datetime,
        call_id: int | None = None,
        message: str = "",
        duration_ms: float | None = None,
    ) -> None:
        values: dict[str, object] = {"status": status.value, "message": message}
        if status is RunItemStatus.RUNNING:
            values["started_at"] = now
        if status.is_finished:
            values["finished_at"] = now
        if call_id is not None:
            values["call_id"] = call_id
        if duration_ms is not None:
            values["duration_ms"] = duration_ms

        async with self._session_factory() as session:
            await session.execute(
                update(RunItemRow)
                .where(RunItemRow.run_id == run_id, RunItemRow.source_id == source_id)
                .values(**values)
            )
            await session.commit()

    async def requeue_unfinished(self, run_id: int, *, now: datetime) -> int:
        """Reset unfinished items so a resume picks them up.

        Timestamps and messages are cleared with the status. Leaving the previous
        attempt's failure message on a pending item would show the run reporting
        an error it is in the middle of retrying.
        """
        async with self._session_factory() as session:
            # Selected before the update rather than read from a driver rowcount,
            # which SQLAlchemy types as unavailable on a generic Result and which
            # not every driver reports honestly.
            unfinished = await session.scalars(
                select(RunItemRow.id).where(
                    RunItemRow.run_id == run_id,
                    RunItemRow.status.in_(_UNFINISHED_ITEM_STATUSES),
                )
            )
            item_ids = list(unfinished)
            if not item_ids:
                return 0

            await session.execute(
                update(RunItemRow)
                .where(RunItemRow.id.in_(item_ids))
                .values(
                    status=RunItemStatus.PENDING.value,
                    message="",
                    started_at=None,
                    finished_at=None,
                    duration_ms=None,
                )
            )
            await session.commit()
            return len(item_ids)

    async def delete_all(self) -> int:
        """Remove every run. Items go with them through the run_id cascade."""
        async with self._session_factory() as session, session.begin():
            rows = (await session.scalars(select(RunRow))).all()
            for row in rows:
                await session.delete(row)
            return len(rows)

    async def abandon_active(self, *, now: datetime, reason: str) -> int:
        async with self._session_factory() as session:
            runs = await session.scalars(
                select(RunRow.id).where(RunRow.status.in_(_ACTIVE_STATUSES))
            )
            run_ids = list(runs)
            if not run_ids:
                return 0

            # An item still marked RUNNING belongs to a worker that no longer
            # exists. Returning it to pending is what makes the run resumable;
            # leaving it running would show permanent activity.
            await session.execute(
                update(RunItemRow)
                .where(
                    RunItemRow.run_id.in_(run_ids),
                    RunItemRow.status == RunItemStatus.RUNNING.value,
                )
                .values(status=RunItemStatus.PENDING.value, message="", started_at=None)
            )
            await session.execute(
                update(RunRow)
                .where(RunRow.id.in_(run_ids))
                .values(
                    status=RunStatus.INTERRUPTED.value,
                    message=reason,
                    finished_at=now,
                )
            )
            await session.commit()
            return len(run_ids)

    async def _load(self, session: AsyncSession, run_id: int) -> CorpusRun:
        row = await self._row(session, run_id)
        if row is None:  # pragma: no cover - the row was just written
            raise RuntimeError(f"Run {run_id} vanished immediately after being created.")
        return _to_domain(row)

    async def _row(self, session: AsyncSession, run_id: int) -> RunRow | None:
        row: RunRow | None = await session.scalar(
            select(RunRow).options(selectinload(RunRow.items)).where(RunRow.id == run_id)
        )
        return row


def _to_domain(row: RunRow) -> CorpusRun:
    return CorpusRun(
        id=row.id,
        provider=row.provider,
        model=row.model,
        force=row.force,
        status=RunStatus(row.status),
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        message=row.message,
        items=tuple(_item_to_domain(item) for item in row.items),
    )


def _item_to_domain(row: RunItemRow) -> CorpusRunItem:
    return CorpusRunItem(
        source_id=row.source_id,
        reference=row.reference,
        title=row.title,
        status=RunItemStatus(row.status),
        call_id=row.call_id,
        message=row.message,
        started_at=row.started_at,
        finished_at=row.finished_at,
        duration_ms=row.duration_ms,
    )
