"""How much work a member had to do to get their problem solved.

Effort is the most consistently evidenced predictor of leaving in service
research, and it is the one members rarely complain about. Somebody can tell you
they were satisfied and still cancel, because the *whole thing* — three calls,
two transfers, forty minutes — was exhausting. Satisfaction asks how the last
conversation felt; effort asks what it cost.

Every figure here is counted from calls already stored. Nothing is modelled.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.aggregation.statistics import median


@dataclass(frozen=True)
class EffortMetrics:
    """What getting an answer costs a member."""

    calls_with_duration: int
    median_minutes: float
    mean_minutes: float
    longest_minutes: int
    # Calls at or beyond the long-call threshold, which is derived rather than
    # configured: see ``long_call_threshold``.
    long_call_count: int
    long_call_threshold: int

    identified_members: int
    repeat_members: int
    calls_by_repeat_members: int

    # Time to an answer, measured per member rather than per call: the minutes a
    # member spent across every call they made, for those who ended up with a
    # resolution. Per call it would flatter a member who was handed a ten-minute
    # non-answer and had to ring back.
    members_with_answer: int
    members_without_answer: int
    median_minutes_to_answer: float

    @property
    def repeat_contact_rate(self) -> float:
        """Share of identified members who have called more than once.

        The headline effort figure. A member calling twice about one problem has
        already spent double what the first call promised.
        """
        if self.identified_members == 0:
            return 0.0
        return round(self.repeat_members * 100 / self.identified_members, 1)


def long_call_threshold(durations: tuple[int, ...]) -> int:
    """Where "long" starts, derived from this corpus rather than configured.

    Twice the median. A fixed number in minutes would mean something different
    for a pharmacy query than for an appeal, and would drift as call mix changes;
    twice the typical call is comparable across both.
    """
    if not durations:
        return 0
    return max(1, round(median(durations) * 2))


def effort_metrics(
    durations: tuple[int, ...],
    *,
    identified_members: int,
    repeat_members: int,
    calls_by_repeat_members: int,
    minutes_to_answer: tuple[int, ...] = (),
    members_without_answer: int = 0,
) -> EffortMetrics:
    """Summarise effort across the corpus.

    ``minutes_to_answer`` holds one total per member who reached a resolution.
    Members still waiting are counted separately rather than folded in: their
    clock has not stopped, and averaging an unfinished wait in alongside finished
    ones would report a *shorter* time to an answer the longer people are left
    waiting.
    """
    if not durations:
        return EffortMetrics(
            calls_with_duration=0,
            median_minutes=0.0,
            mean_minutes=0.0,
            longest_minutes=0,
            long_call_count=0,
            long_call_threshold=0,
            identified_members=identified_members,
            repeat_members=repeat_members,
            calls_by_repeat_members=calls_by_repeat_members,
            members_with_answer=len(minutes_to_answer),
            members_without_answer=members_without_answer,
            median_minutes_to_answer=(
                round(median(minutes_to_answer), 1) if minutes_to_answer else 0.0
            ),
        )

    threshold = long_call_threshold(durations)
    return EffortMetrics(
        calls_with_duration=len(durations),
        median_minutes=round(median(durations), 1),
        mean_minutes=round(sum(durations) / len(durations), 1),
        longest_minutes=max(durations),
        long_call_count=sum(1 for value in durations if value >= threshold),
        long_call_threshold=threshold,
        identified_members=identified_members,
        repeat_members=repeat_members,
        calls_by_repeat_members=calls_by_repeat_members,
        members_with_answer=len(minutes_to_answer),
        members_without_answer=members_without_answer,
        median_minutes_to_answer=(
            round(median(minutes_to_answer), 1) if minutes_to_answer else 0.0
        ),
    )
