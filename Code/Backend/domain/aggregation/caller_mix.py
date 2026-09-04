"""Who is calling, and how differently each of them fares.

Thirty per cent of this corpus is not a member: fifteen employers and seven
brokers, each reaching the same queue. They are different books of business. An
employer is a renewal decision and a whole group's coverage; a broker is a
distribution channel that can move a book elsewhere. Averaging all three into
"first-contact resolution 54%" reports a centre that does not exist.

Reported per caller so the differences are visible at all. On the shipped corpus
an employer call that fails scores 58 against 87 when it succeeds — the same
spread members show, on business worth many times more per call.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from domain.aggregation.statistics import mean, percentage

__all__ = [
    "CallerBreakdown",
    "CallerCall",
    "CallerMix",
    "caller_mix",
]

_RESOLVED = "RESOLVED"


@dataclass(frozen=True)
class CallerCall:
    """One call, reduced to what the mix needs."""

    caller_type: str | None
    resolution: str
    score: int
    duration_seconds: int | None


@dataclass(frozen=True)
class CallerBreakdown:
    """One kind of caller."""

    caller_type: str
    calls: int
    share: float
    resolution_rate: float
    average_score: float
    average_handle_minutes: float | None


@dataclass(frozen=True)
class CallerMix:
    """Every kind of caller, largest population first."""

    callers: tuple[CallerBreakdown, ...]
    total_calls: int
    # Calls whose source never said who was calling — a pasted transcript rather
    # than a corpus call. Kept out of the breakdown and counted here, because a
    # fourth bar labelled "unknown" invites reading it as a fourth population.
    unattributed_calls: int


def _breakdown(caller_type: str, calls: Sequence[CallerCall], total: int) -> CallerBreakdown:
    timed = [call.duration_seconds for call in calls if call.duration_seconds]
    return CallerBreakdown(
        caller_type=caller_type,
        calls=len(calls),
        share=percentage(len(calls), total),
        resolution_rate=percentage(
            sum(1 for call in calls if call.resolution == _RESOLVED), len(calls)
        ),
        average_score=mean([call.score for call in calls]),
        average_handle_minutes=(round(sum(timed) / len(timed) / 60, 1) if timed else None),
    )


def caller_mix(calls: Iterable[CallerCall], *, known_types: Iterable[str]) -> CallerMix:
    """Break calls down by who made them.

    ``known_types`` is the configured vocabulary, and every one of them gets a
    row even at zero: a population nobody heard from is a finding, and a row
    that simply vanishes cannot be noticed.
    """
    every = list(calls)
    attributed = [call for call in every if call.caller_type]

    by_type: dict[str, list[CallerCall]] = {name: [] for name in known_types}
    for call in attributed:
        # A caller type outside the vocabulary still gets a row rather than
        # being dropped — the number has to add up to the calls that exist.
        by_type.setdefault(str(call.caller_type), []).append(call)

    total = len(attributed)
    return CallerMix(
        callers=tuple(
            sorted(
                (
                    _breakdown(caller_type, rows, total)
                    if rows
                    else CallerBreakdown(
                        caller_type=caller_type,
                        calls=0,
                        share=0.0,
                        resolution_rate=0.0,
                        average_score=0.0,
                        average_handle_minutes=None,
                    )
                    for caller_type, rows in by_type.items()
                ),
                key=lambda row: (-row.calls, row.caller_type),
            )
        ),
        total_calls=total,
        unattributed_calls=len(every) - total,
    )
