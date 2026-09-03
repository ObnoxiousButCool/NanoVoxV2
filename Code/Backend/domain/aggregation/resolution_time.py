"""How long it takes to actually resolve a member's problem.

Handle time is the number every contact centre already has, and on its own it
rewards the wrong thing: the fastest way to end a call is to not solve anything.
So the figures here are computed over **resolved calls only**. "Twelve minutes to
an answer" is a service fact; "twelve minutes on the phone" is not.

Split by category because the mix matters more than the average. A pharmacy
query and a coverage appeal are different pieces of work, and a single median
across both describes neither — it moves when the mix of calls changes, which
reads as a change in performance when nothing about the handling changed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise

from domain.aggregation.statistics import median
from domain.errors import ValidationError

__all__ = [
    "CategoryResolutionTime",
    "DurationBand",
    "DurationBandSettings",
    "ResolutionTime",
    "resolution_time",
]


@dataclass(frozen=True)
class DurationBandSettings:
    """Lower bounds of the duration bands, ascending, in minutes.

    Policy rather than code: what counts as a long resolution differs by line of
    business, so it is configured in ``dashboard.yaml`` beside the score bins.
    """

    lower_bounds: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.lower_bounds) < 2:
            raise ValidationError(
                f"Duration bands need at least two lower bounds, got {list(self.lower_bounds)}."
            )
        if self.lower_bounds[0] != 0:
            raise ValidationError(f"Duration bands must start at 0, got {self.lower_bounds[0]}.")
        if any(later <= earlier for earlier, later in pairwise(self.lower_bounds)):
            raise ValidationError(
                f"Duration band bounds must ascend, got {list(self.lower_bounds)}."
            )


@dataclass(frozen=True)
class DurationBand:
    """One bar of the resolution-time distribution."""

    label: str
    lower: int
    # Exclusive, and None for the final open-ended band. Half-open matches the
    # score histogram: "10-20" holds 10 up to 19, and a 20-minute call belongs to
    # the band above rather than to both.
    upper: int | None
    count: int


@dataclass(frozen=True)
class CategoryResolutionTime:
    """How long this kind of problem takes to solve."""

    code: str
    label: str
    resolved_calls: int
    median_minutes: float
    longest_minutes: int


@dataclass(frozen=True)
class ResolutionTime:
    """Time to resolve, overall and per category."""

    resolved_calls: int
    # Every analysed call, so a reader can see what share reached a resolution
    # at all rather than assuming the median describes the whole corpus.
    total_calls: int
    median_minutes: float
    longest_minutes: int
    bands: tuple[DurationBand, ...]
    categories: tuple[CategoryResolutionTime, ...]


def _label(lower: int, upper: int | None) -> str:
    return f"{lower}+" if upper is None else f"{lower}-{upper}"


def _bands(durations: Sequence[int], settings: DurationBandSettings) -> tuple[DurationBand, ...]:
    bounds = settings.lower_bounds
    edges: list[tuple[int, int | None]] = list(pairwise(bounds))
    edges.append((bounds[-1], None))

    return tuple(
        DurationBand(
            label=_label(lower, upper),
            lower=lower,
            upper=upper,
            # A band with no calls is kept, not dropped: an absent bar reads as
            # "this does not happen" rather than "this did not happen here".
            count=sum(
                1 for value in durations if lower <= value and (upper is None or value < upper)
            ),
        )
        for lower, upper in edges
    )


def resolution_time(
    durations_by_category: Mapping[str, tuple[int, ...]],
    *,
    labels: Mapping[str, str],
    total_calls: int,
    settings: DurationBandSettings,
) -> ResolutionTime:
    """Summarise time to resolve.

    ``durations_by_category`` holds the durations of *resolved* calls, keyed by
    category code. A category absent from it has resolved nothing, and is
    reported with zero rather than omitted — a category that never reaches a
    resolution is the most interesting row on the chart, and dropping it would
    hide exactly that.

    **The rows need not sum to the headline.** Only configured categories get a
    row, while the overall figures count every resolved call — so a call whose
    category has since been retired is in the total and in no row. That is the
    right way round: excluding it from the total would understate how much work
    was actually resolved, and the Overview already carries a taxonomy-coverage
    figure whose job is to tell a reader that such calls exist.
    """
    every = tuple(value for values in durations_by_category.values() for value in values)

    categories = tuple(
        sorted(
            (
                CategoryResolutionTime(
                    code=code,
                    label=labels.get(code, code),
                    resolved_calls=len(durations_by_category.get(code, ())),
                    median_minutes=(
                        round(median(durations_by_category[code]), 1)
                        if durations_by_category.get(code)
                        else 0.0
                    ),
                    longest_minutes=max(durations_by_category.get(code, (0,))),
                )
                for code in labels
            ),
            # Slowest first: the point of the breakdown is which work takes
            # longest, and a reader should not have to hunt for it.
            key=lambda entry: (-entry.median_minutes, entry.label),
        )
    )

    return ResolutionTime(
        resolved_calls=len(every),
        total_calls=total_calls,
        median_minutes=round(median(every), 1) if every else 0.0,
        longest_minutes=max(every) if every else 0,
        bands=_bands(every, settings),
        categories=categories,
    )
