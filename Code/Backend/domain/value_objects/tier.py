"""Performance tier and the thresholds that define it.

Thresholds are data, not constants: they arrive from ``rubric.yaml`` so a
reviewer can see and change where the boundaries sit without reading code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.errors import ValidationError
from domain.value_objects.score import MAX_SCORE, MIN_SCORE, Score


class Tier(str, Enum):
    """Coarse performance band, matching the corpus index vocabulary."""

    GOOD = "GOOD"
    AVERAGE = "AVERAGE"
    POOR = "POOR"


@dataclass(frozen=True)
class TierThresholds:
    """Lower bounds, inclusive: ``score >= good`` is GOOD, ``>= average`` is AVERAGE."""

    good: int
    average: int

    def __post_init__(self) -> None:
        if not MIN_SCORE < self.average < self.good <= MAX_SCORE:
            raise ValidationError(
                "Tier thresholds must satisfy "
                f"{MIN_SCORE} < average < good <= {MAX_SCORE}, "
                f"got average={self.average}, good={self.good}."
            )

    def tier_for(self, score: Score) -> Tier:
        if score.value >= self.good:
            return Tier.GOOD
        if score.value >= self.average:
            return Tier.AVERAGE
        return Tier.POOR
