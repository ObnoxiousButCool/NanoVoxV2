"""Copy every row from the local SQLite database into an empty Postgres one.

Moving to Postgres (Render, or anywhere else without durable local disk) gives
a deployment a fresh, empty schema — `alembic upgrade head` creates tables,
not data. This copies what is actually in the local corpus across, table by
table, in an order that respects every foreign key, and repairs each table's
identity sequence afterward so the next row Postgres itself assigns an id to
does not collide with one this script just wrote explicitly.

Refuses to run against a target that already holds any rows, in any of these
tables — the one case this could silently do the wrong thing is running it
twice, or against a database that already has real data of its own.

    python scripts/migrate_sqlite_to_postgres.py --target postgresql+asyncpg://...
    python scripts/migrate_sqlite_to_postgres.py --target postgresql+asyncpg://... --dry-run

The target is also read from $DATABASE_URL if --target is omitted, so the
connection string need not be typed where shell history keeps it.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sqlite3
import sys
from pathlib import Path

if sys.platform == "win32":
    # asyncpg's SSL transport, torn down under Proactor (the Windows default
    # loop), leaves a harmless-but-noisy traceback on the way out — real work
    # is already finished and the exit code is already 0 by the time it
    # fires. Selector avoids the issue entirely; nothing here needs Proactor's
    # subprocess support.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

BACKEND = Path(__file__).resolve().parent.parent / "Code" / "Backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import func, insert, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.orm import DeclarativeBase  # noqa: E402

from infrastructure.config.paths import DEFAULT_DATABASE_FILE  # noqa: E402
from infrastructure.persistence.engine import _connect_args_for  # noqa: E402
from infrastructure.persistence.tables import (  # noqa: E402
    AssistEventRow,
    BrokerSignalRow,
    CallRow,
    CallSignalRow,
    GroundTruthRow,
    L4SignalRow,
    LayerRow,
    RunItemRow,
    RunRow,
    ScoreMarkerRow,
    TurnRow,
)

# Parents before children, so a foreign key is never written before the row
# it points at exists. `RunItemRow` is last of the two run tables because it
# references `calls` as well as `analysis_runs`.
TABLES_IN_ORDER: tuple[type[DeclarativeBase], ...] = (
    CallRow,
    TurnRow,
    LayerRow,
    ScoreMarkerRow,
    L4SignalRow,
    BrokerSignalRow,
    AssistEventRow,
    CallSignalRow,
    RunRow,
    RunItemRow,
    GroundTruthRow,
)


def _checkpoint_wal(sqlite_path: Path) -> None:
    """Fold the WAL into the main file so a fresh read sees every commit.

    The same fix applied to the file shared with Ranjit: a connection can
    have committed rows that exist only in `-wal` until this runs, and this
    script's own read otherwise risks missing exactly those.
    """
    if not sqlite_path.exists():
        return
    connection = sqlite3.connect(str(sqlite_path))
    try:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.commit()
    finally:
        connection.close()


async def _row_count(session: AsyncSession, model: type[DeclarativeBase]) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


# One INSERT per chunk rather than the whole table at once. The turns table
# alone is ~1700 rows; a single statement that size, over a pooled connection
# with the statement cache disabled (see _connect_args_for), was observed to
# sit with no visible progress for minutes. Chunking bounds how much each
# individual round trip has to do, and gives a place to report progress from.
_CHUNK_SIZE = 200


async def _copy_table(
    source: AsyncSession, target: AsyncSession, model: type[DeclarativeBase]
) -> int:
    columns = list(model.__table__.columns)  # type: ignore[attr-defined]
    rows = (await source.execute(select(model))).scalars().all()
    if not rows:
        return 0
    values = [{column.name: getattr(row, column.name) for column in columns} for row in rows]
    for start in range(0, len(values), _CHUNK_SIZE):
        chunk = values[start : start + _CHUNK_SIZE]
        await target.execute(insert(model), chunk)
        print(f"    ...{min(start + _CHUNK_SIZE, len(values))}/{len(values)}")
    return len(values)


async def _repair_sequence(target: AsyncSession, model: type[DeclarativeBase]) -> None:
    """Move Postgres's own next-id counter past every id this script wrote.

    Explicit inserts never touch the table's identity sequence, so without
    this the first row the *application* inserts would try to reuse id 1 —
    already taken — and fail. ``pg_get_serial_sequence`` and ``setval`` are
    Postgres-only, so this is plain SQL rather than the query builder; the
    table name is interpolated because it names a table, not a value, and it
    only ever comes from this script's own hardcoded model list, never from
    input.
    """
    table_name = model.__tablename__  # type: ignore[attr-defined]
    # table_name only ever comes from TABLES_IN_ORDER above, never from input.
    await target.execute(
        text(
            f"SELECT setval(pg_get_serial_sequence(:table_name, 'id'), "  # noqa: S608
            f"COALESCE((SELECT MAX(id) FROM {table_name}), 1))"
        ),
        {"table_name": table_name},
    )


async def _run(source_path: Path, target_url: str, *, dry_run: bool) -> int:
    _checkpoint_wal(source_path)

    source_engine = create_async_engine(f"sqlite+aiosqlite:///{source_path.as_posix()}")
    target_engine = create_async_engine(target_url, connect_args=_connect_args_for(target_url))

    async with source_engine.connect() as source_conn, target_engine.connect() as target_conn:
        source = AsyncSession(bind=source_conn, expire_on_commit=False)
        target = AsyncSession(bind=target_conn, expire_on_commit=False)

        print(f"Source: {source_path}")
        print(f"Target: {target_engine.url.render_as_string(hide_password=True)}")
        print()

        occupied = {
            model.__tablename__: await _row_count(target, model)  # type: ignore[attr-defined]
            for model in TABLES_IN_ORDER
        }
        already_has_rows = {name: count for name, count in occupied.items() if count > 0}
        if already_has_rows:
            print("Refusing to run: the target already has rows in:")
            for name, count in already_has_rows.items():
                print(f"  {name}: {count}")
            print("This script only writes into an empty database.")
            return 1

        counts = {
            model.__tablename__: await _row_count(source, model)  # type: ignore[attr-defined]
            for model in TABLES_IN_ORDER
        }
        for name, count in counts.items():
            print(f"{name}: {count} row(s) to copy")

        if dry_run:
            print("\n--dry-run: nothing written.")
            return 0

        print()
        for model in TABLES_IN_ORDER:
            written = await _copy_table(source, target, model)
            print(f"  wrote {written} row(s) into {model.__tablename__}")  # type: ignore[attr-defined]

        for model in TABLES_IN_ORDER:
            await _repair_sequence(target, model)
        await target.commit()

        print()
        mismatched = {}
        for model in TABLES_IN_ORDER:
            name = model.__tablename__  # type: ignore[attr-defined]
            landed = await _row_count(target, model)
            if landed != counts[name]:
                mismatched[name] = (counts[name], landed)
            print(f"{name}: {landed} row(s) now in the target")

    await source_engine.dispose()
    await target_engine.dispose()

    if mismatched:
        print("\nMismatch — source and target disagree on row count:")
        for name, (expected, actual) in mismatched.items():
            print(f"  {name}: expected {expected}, target has {actual}")
        return 1

    print("\nDone. Every table's row count matches the source.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_DATABASE_FILE,
        help=f"path to the source SQLite file (default: {DEFAULT_DATABASE_FILE})",
    )
    parser.add_argument(
        "--target",
        default=os.environ.get("DATABASE_URL"),
        help="target Postgres URL (postgresql+asyncpg://...); defaults to $DATABASE_URL",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report row counts without writing anything",
    )
    args = parser.parse_args(argv)

    if not args.target:
        raise SystemExit("No target given: pass --target or set $DATABASE_URL")
    if not args.target.startswith("postgresql+asyncpg:"):
        raise SystemExit("--target must be a postgresql+asyncpg:// URL")
    if not args.source.exists():
        raise SystemExit(f"No such file: {args.source}")

    return asyncio.run(_run(args.source, args.target, dry_run=args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
