"""What the time on calls bought.

Every other duration figure on this dashboard counts calls. This one counts
minutes, because minutes are what a contact centre actually spends: "how long is
a call" is an operations question, "how many of our hours produced an answer" is
the one a manager is accountable for.

Two things fall out of counting it this way, and both are the point:

* **Unproductive time is visible as a quantity, not a rate.** "47% unresolved"
  is an abstraction; "eight and a half hours bought nothing" is a budget line.
* **Failure splits into two kinds that need opposite responses.** A call that
  ended without an answer *faster* than a typical successful one is a member
  brushed off — coaching. One that ran longer and still failed is an agent who
  did the work against a system that had no answer to give — process. Reported
  as one number, the second group gets coached for the first group's problem.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from domain.aggregation.statistics import median, percentage
from domain.value_objects.resolution import Resolution

__all__ = [
    "CallTime",
    "CategoryMinutes",
    "FailureMode",
    "OutcomeMinutes",
    "TimeValue",
    "time_value",
]


@dataclass(frozen=True)
class CallTime:
    """One call, reduced to what this aggregation needs."""

    category_code: str
    resolution: str
    duration_minutes: int
    score: int


@dataclass(frozen=True)
class OutcomeMinutes:
    """Minutes spent on one outcome within a category."""

    resolution: str
    minutes: int


@dataclass(frozen=True)
class CategoryMinutes:
    """Where one category's minutes went."""

    code: str
    label: str
    total_minutes: int
    resolved_minutes: int
    by_outcome: tuple[OutcomeMinutes, ...]

    @property
    def unproductive_minutes(self) -> int:
        return self.total_minutes - self.resolved_minutes

    @property
    def unproductive_share(self) -> float:
        return percentage(self.unproductive_minutes, self.total_minutes)


@dataclass(frozen=True)
class FailureMode:
    """One of the two ways a call ends without an answer."""

    calls: int
    minutes: int
    average_score: float


@dataclass(frozen=True)
class TimeValue:
    """What the corpus's minutes bought."""

    total_minutes: int
    resolved_minutes: int
    # The median duration of a *resolved* call: the line separating the two
    # failure modes. Derived from this corpus rather than configured, for the
    # same reason as the long-call threshold — a fixed number of minutes means
    # something different for a pharmacy query than for an appeal.
    resolved_median_minutes: float
    fast_fail: FailureMode
    slow_fail: FailureMode
    categories: tuple[CategoryMinutes, ...]

    @property
    def unproductive_minutes(self) -> int:
        return self.total_minutes - self.resolved_minutes

    @property
    def productive_share(self) -> float:
        return percentage(self.resolved_minutes, self.total_minutes)


# Fixed order, worst last, so the stacked bars read the same way every time and
# a category's colours do not shuffle when its mix changes.
_OUTCOME_ORDER: tuple[str, ...] = (
    Resolution.RESOLVED.value,
    Resolution.PARTIALLY_RESOLVED.value,
    Resolution.ESCALATED.value,
    Resolution.UNRESOLVED.value,
)


def _failure_mode(calls: Sequence[CallTime]) -> FailureMode:
    return FailureMode(
        calls=len(calls),
        minutes=sum(call.duration_minutes for call in calls),
        average_score=(round(sum(call.score for call in calls) / len(calls), 1) if calls else 0.0),
    )


def _category(code: str, label: str, calls: Sequence[CallTime]) -> CategoryMinutes:
    minutes = dict.fromkeys(_OUTCOME_ORDER, 0)
    for call in calls:
        # An outcome the taxonomy does not list still has to be counted
        # somewhere, or the bars would not sum to the total beside them.
        minutes[call.resolution] = minutes.get(call.resolution, 0) + call.duration_minutes

    return CategoryMinutes(
        code=code,
        label=label,
        total_minutes=sum(minutes.values()),
        resolved_minutes=minutes.get(Resolution.RESOLVED.value, 0),
        by_outcome=tuple(
            # Zeros kept: an absent segment reads as "this does not happen"
            # rather than "this did not happen here".
            OutcomeMinutes(resolution=outcome, minutes=minutes.get(outcome, 0))
            for outcome in _OUTCOME_ORDER
        ),
    )


def time_value(calls: Sequence[CallTime], *, labels: Mapping[str, str]) -> TimeValue:
    """Summarise what the time on calls bought.

    Calls with no recorded duration are the caller's to exclude; everything
    passed in is counted, because a call silently dropped here would make the
    minutes disagree with the call counts elsewhere on the screen.
    """
    resolved = [call for call in calls if call.resolution == Resolution.RESOLVED.value]
    failed = [call for call in calls if call.resolution != Resolution.RESOLVED.value]
    line = round(median([call.duration_minutes for call in resolved]), 1) if resolved else 0.0

    # With no resolved call there is no line to draw, so every failure counts as
    # slow rather than being split on an invented threshold.
    fast = [call for call in failed if line and call.duration_minutes < line]
    slow = [call for call in failed if not line or call.duration_minutes >= line]

    by_code: dict[str, list[CallTime]] = {}
    for call in calls:
        by_code.setdefault(call.category_code, []).append(call)

    categories = tuple(
        sorted(
            (
                _category(code, labels.get(code, code), by_code.get(code, ()))
                for code in {*labels, *by_code}
            ),
            # Most time first: the longest bar is the biggest claim on the
            # centre's hours, which is what the chart is asked about.
            key=lambda entry: (-entry.total_minutes, entry.label),
        )
    )

    return TimeValue(
        total_minutes=sum(call.duration_minutes for call in calls),
        resolved_minutes=sum(call.duration_minutes for call in resolved),
        resolved_median_minutes=line,
        fast_fail=_failure_mode(fast),
        slow_fail=_failure_mode(slow),
        categories=tuple(entry for entry in categories if entry.total_minutes > 0),
    )
