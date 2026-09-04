"""What speed costs.

The dashboard already reports handle time and quality, in separate cards, as
separate facts. Put beside each other on the shipped corpus they stop being two
facts: every agent averaging under six minutes scores below 66, and every agent
averaging over six and a half scores above 81. Brad, 4.7 minutes, 57. Sarah, ten
minutes, 84.

That is the most consequential relationship in this data, because the lever it
implicates — an average-handle-time target — is one leadership actually pulls.
An AHT target rewards ending the call, and the fastest way to end a call is to
not solve anything. The ledger in ``time_value`` argues the same thing from the
other end: eighteen calls ended early *and* unresolved.

So this module states the comparison rather than leaving a reader to find it,
and states it carefully:

* **The split is measured over calls, not over agents.** Thirteen agents is
  thirteen data points and most of them have four calls; fifty calls is fifty.
  Splitting agents would also have to exclude everyone below the tier threshold
  — which on this corpus leaves one agent, and one agent is not a comparison.
  The per-agent points stay as the picture; the *number* comes from the calls.
* **The split is at the median call, not at a configured target.** A target is a
  policy this module should not know, and it anchors to a figure set for a
  different year; the median moves with the mix of work.
* **Agents below the tier threshold are marked, not dropped.** They are shown,
  because the volume is real, and flagged, because a four-call average lands
  anywhere. That is the rule the agent table already applies, and it is about
  fairness to a named person rather than about the statistic.
* **The gap is reported, never called a cause.** Slower calls may simply be
  harder ones. The chart's job is to stop anyone reading "fast" as "good"
  without looking; it is not to prove which way the arrow points.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from domain.aggregation.statistics import mean, median

__all__ = [
    "AgentSpeed",
    "HandleTimeQuality",
    "SpeedGroup",
    "TimedCall",
    "handle_time_quality",
]


@dataclass(frozen=True)
class AgentSpeed:
    """One agent's average score against their average handle time."""

    agent_name: str
    calls: int
    average_score: float
    average_handle_minutes: float
    # False for agents below the tier threshold, whose average is drawn from too
    # few calls to read individually. They are still plotted.
    is_comparable: bool


@dataclass(frozen=True)
class TimedCall:
    """One call that states how long it took."""

    duration_seconds: int
    score: int


@dataclass(frozen=True)
class SpeedGroup:
    """One side of the split, counted in calls."""

    label: str
    calls: int
    average_score: float
    average_handle_minutes: float


@dataclass(frozen=True)
class HandleTimeQuality:
    """Every agent's point, and the comparison between the two halves of the calls."""

    agents: tuple[AgentSpeed, ...]
    faster: SpeedGroup | None
    slower: SpeedGroup | None
    split_minutes: float
    # Agents drawn on the chart but below the tier threshold, so a reader knows
    # how much of the picture rests on four-call averages.
    flagged_agents: int

    @property
    def score_gap(self) -> float:
        """Points of quality between the slower half and the faster half.

        Positive means the slower half scores higher, which is the direction
        that matters: it is the one an AHT target makes worse.
        """
        if self.faster is None or self.slower is None:
            return 0.0
        return round(self.slower.average_score - self.faster.average_score, 1)


def _group(label: str, calls: list[TimedCall]) -> SpeedGroup | None:
    if not calls:
        return None
    return SpeedGroup(
        label=label,
        calls=len(calls),
        average_score=mean([call.score for call in calls]),
        average_handle_minutes=round(
            sum(call.duration_seconds for call in calls) / len(calls) / 60, 1
        ),
    )


def handle_time_quality(
    agents: Iterable[AgentSpeed], calls: Iterable[TimedCall]
) -> HandleTimeQuality:
    """Plot the agents, and split the calls at their median length to compare quality."""
    every_agent = tuple(agents)
    timed = [call for call in calls if call.duration_seconds > 0]
    flagged = sum(1 for agent in every_agent if not agent.is_comparable)

    if len(timed) < 2:
        # Nothing to split. Reported as a chart with no comparison rather than
        # as a comparison of one call against none.
        return HandleTimeQuality(
            agents=every_agent,
            faster=None,
            slower=None,
            split_minutes=0.0,
            flagged_agents=flagged,
        )

    split_seconds = median([call.duration_seconds for call in timed])
    return HandleTimeQuality(
        # Slowest first: the point of the chart is that the top of it is slow.
        agents=tuple(sorted(every_agent, key=lambda agent: -agent.average_handle_minutes)),
        faster=_group(
            f"under {round(split_seconds / 60, 1)} min",
            [call for call in timed if call.duration_seconds < split_seconds],
        ),
        slower=_group(
            f"at {round(split_seconds / 60, 1)} min and over",
            [call for call in timed if call.duration_seconds >= split_seconds],
        ),
        split_minutes=round(split_seconds / 60, 1),
        flagged_agents=flagged,
    )
