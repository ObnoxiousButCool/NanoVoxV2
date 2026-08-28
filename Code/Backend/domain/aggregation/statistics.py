"""Descriptive statistics for the dashboard.

Pure functions over already-fetched values. SQL does the grouping; these do the
arithmetic, so the definitions are testable without a database and there is
exactly one place where "median" means something.

The distribution matters here more than usual. The corpus is bimodal — a large
cluster of strong calls and a small cluster of very weak ones — so the mean sits
in a gap where no agent actually falls. Reporting one number would hide the
calls that need action, which is why both are computed and the histogram is a
first-class figure rather than decoration.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from domain.errors import ValidationError


def validate_bin_edges(edges: Sequence[int]) -> None:
    """Bin edges must be ascending, distinct and within 0-100."""
    if len(edges) < 2:
        raise ValidationError("A histogram needs at least two bin edges.")
    if list(edges) != sorted(set(edges)):
        raise ValidationError("Histogram bin edges must be ascending and distinct.")
    if edges[0] < 0 or edges[-1] > 100:
        raise ValidationError("Histogram bin edges must lie within 0-100.")


def mean(values: Sequence[int]) -> float:
    """Arithmetic mean, rounded to one decimal. Zero for an empty set."""
    if not values:
        return 0.0
    return round(sum(values) / len(values), 1)


def median(values: Sequence[int]) -> float:
    """Middle value, averaging the two middles for an even count."""
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[middle])
    return round((ordered[middle - 1] + ordered[middle]) / 2, 1)


def percentage(part: int, whole: int) -> float:
    """``part`` as a percentage of ``whole``, rounded to one decimal."""
    if whole <= 0:
        return 0.0
    return round(part * 100 / whole, 1)


@dataclass(frozen=True)
class HistogramSettings:
    """Bin edges and the threshold that marks a bin as needing coaching.

    Lives in the domain because it describes the histogram, not the file it
    happens to be loaded from. Keeping it in the loader made the application
    layer import infrastructure, which the dependency rule forbids.
    """

    bin_edges: tuple[int, ...]
    coaching_threshold: int

    def __post_init__(self) -> None:
        # Validated here so a bad configuration fails at startup rather than at
        # the first dashboard render.
        validate_bin_edges(self.bin_edges)
        if not 0 <= self.coaching_threshold <= 100:
            raise ValidationError(
                "Histogram coaching threshold must lie within 0-100, "
                f"got {self.coaching_threshold}."
            )


@dataclass(frozen=True)
class HistogramBin:
    """One bar: the half-open range ``[lower, upper)``, except the last, which includes 100."""

    lower: int
    upper: int
    count: int
    is_below_threshold: bool

    @property
    def label(self) -> str:
        return f"{self.lower}-{self.upper}"

    def contains(self, value: int) -> bool:
        if self.upper >= 100:
            return self.lower <= value <= 100
        return self.lower <= value < self.upper


@dataclass(frozen=True)
class Histogram:
    """A score distribution over configured bin edges."""

    bins: tuple[HistogramBin, ...]

    @property
    def total(self) -> int:
        return sum(item.count for item in self.bins)

    @property
    def below_threshold_count(self) -> int:
        """How many calls fall in bins the coaching threshold marks as concerning."""
        return sum(item.count for item in self.bins if item.is_below_threshold)

    @property
    def peak(self) -> int:
        return max((item.count for item in self.bins), default=0)


def build_histogram(
    values: Sequence[int], edges: Sequence[int], *, coaching_threshold: int
) -> Histogram:
    """Bucket scores into the configured bins.

    ``edges`` are the lower bounds, ascending; the final bin runs to 100
    inclusive. Bins entirely below ``coaching_threshold`` are marked, because the
    prototype colours them as the population that needs intervention.
    """
    validate_bin_edges(edges)

    bounds = [*edges, 101]
    bins: list[HistogramBin] = []

    for index in range(len(edges)):
        lower = bounds[index]
        upper = min(bounds[index + 1], 100) if index == len(edges) - 1 else bounds[index + 1]
        count = sum(
            1
            for value in values
            if (lower <= value <= 100 if index == len(edges) - 1 else lower <= value < upper)
        )
        bins.append(
            HistogramBin(
                lower=lower,
                upper=upper,
                count=count,
                # A bin counts as concerning only if every score in it is below
                # the threshold; a bin straddling it would overstate the problem.
                is_below_threshold=upper <= coaching_threshold,
            )
        )

    return Histogram(bins=tuple(bins))
