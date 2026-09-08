"""Whether members leave a call feeling better than they arrived.

Every call already stores a sentiment arc — the state the member was in at the
start and the state they were in at the end. Nothing read it. It is the closest
thing in this system to a satisfaction measure, and unlike a survey it exists
for every call rather than for the few per cent who answer one.

The arc is reduced to a **direction**, not a distance. "Worried to satisfied"
being worth two points and "confused to informed" one is a precision the
underlying labels cannot support: they come from a model choosing words, and the
gap between two adjacent words is not a measured quantity. Direction is what
survives that — a call that moved a member up a band, held them, or sent them
down one — and direction is what a leader acts on.

The bands are deliberately coarse and every configured sentiment belongs to
exactly one. A state this module does not know is reported as **unclassified**
rather than assumed flat: a vocabulary that grew without this file being updated
must show up as a gap in the count, not as a silent run of calls that "did not
move".
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum

__all__ = [
    "ArcDirection",
    "SentimentArc",
    "SentimentMovement",
    "band_of",
    "sentiment_movement",
]

# Five bands, worst to best. Grouped by what the member is left with, not by
# intensity of feeling: RESIGNED and DISMISSED are quiet, but they describe
# somebody who gave up, which belongs with the unhappy ones.
_BANDS: tuple[tuple[str, ...], ...] = (
    ("ANGRY", "DISTRESSED", "PANICKED", "ALARMED", "ABANDONED"),
    ("FRUSTRATED", "ANXIOUS", "WORRIED", "RESIGNED", "DISMISSED", "ESCALATED", "CONFUSED"),
    ("NEUTRAL", "CURIOUS"),
    (
        "PARTIALLY_SATISFIED",
        "PARTIALLY_HELPED",
        "PARTIALLY_REASSURED",
        "PARTIALLY_CALMED",
        "INFORMED",
    ),
    ("SATISFIED", "REASSURED", "RELIEVED", "CALMED", "POSITIVE"),
)

_BAND_BY_STATE: dict[str, int] = {
    state: index for index, states in enumerate(_BANDS) for state in states
}


class ArcDirection(str, Enum):
    """Which way a call moved the member."""

    IMPROVED = "IMPROVED"
    UNCHANGED = "UNCHANGED"
    WORSENED = "WORSENED"
    UNCLASSIFIED = "UNCLASSIFIED"


@dataclass(frozen=True)
class SentimentArc:
    """One call's arc, as stored."""

    start: str | None
    end: str | None


@dataclass(frozen=True)
class SentimentMovement:
    """How a body of calls moved the members who made them."""

    improved: int
    unchanged: int
    worsened: int
    # Calls whose sentiment this module could not place. Reported rather than
    # folded into "unchanged", so a vocabulary change is visible as a gap.
    unclassified: int

    @property
    def classified(self) -> int:
        return self.improved + self.unchanged + self.worsened

    @property
    def improved_rate(self) -> float:
        """Share of *classified* calls that left the member better off.

        Measured against what could be classified rather than against every
        call: including calls with no readable arc in the denominator would
        report a fall in satisfaction when what actually happened is that a
        sentiment label stopped being recognised.
        """
        if self.classified == 0:
            return 0.0
        return round(self.improved * 100 / self.classified, 1)


def band_of(state: str | None) -> int | None:
    """The band a sentiment belongs to, or ``None`` if it is not one we know."""
    if state is None:
        return None
    return _BAND_BY_STATE.get(state.strip().upper())


def direction_of(arc: SentimentArc) -> ArcDirection:
    """Which way one call moved."""
    start, end = band_of(arc.start), band_of(arc.end)
    if start is None or end is None:
        return ArcDirection.UNCLASSIFIED
    if end > start:
        return ArcDirection.IMPROVED
    if end < start:
        return ArcDirection.WORSENED
    return ArcDirection.UNCHANGED


def sentiment_movement(arcs: Iterable[SentimentArc]) -> SentimentMovement:
    """Count which way a body of calls moved the members who made them."""
    counts = dict.fromkeys(ArcDirection, 0)
    for arc in arcs:
        counts[direction_of(arc)] += 1
    return SentimentMovement(
        improved=counts[ArcDirection.IMPROVED],
        unchanged=counts[ArcDirection.UNCHANGED],
        worsened=counts[ArcDirection.WORSENED],
        unclassified=counts[ArcDirection.UNCLASSIFIED],
    )


def unknown_states(states: Sequence[str]) -> tuple[str, ...]:
    """Configured sentiments this module has no band for.

    Used by the taxonomy check: a state added to ``taxonomy.yaml`` and not here
    would silently make calls unclassifiable.
    """
    return tuple(sorted({state for state in states if band_of(state) is None}))
