"""A single scored observation, anchored to transcript evidence.

Evidence is mandatory by construction. A marker cannot exist without naming the
turn it came from and quoting it, which is what makes every point of deduction
traceable to a sentence somebody actually said (plan §5.3). Whether the quote is
*truthful* is checked separately, against the transcript, by the marker validator.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.errors import ValidationError
from domain.value_objects.polarity import Polarity


@dataclass(frozen=True)
class ScoreMarker:
    """One positive or negative observation about how the agent handled the call."""

    polarity: Polarity
    dimension: str
    description: str
    evidence_turn_seq: int
    quote: str

    def __post_init__(self) -> None:
        if not self.dimension.strip():
            raise ValidationError("Score marker must name a rubric dimension.")
        if not self.description.strip():
            raise ValidationError(
                f"Score marker for {self.dimension!r} must describe what was observed."
            )
        if isinstance(self.evidence_turn_seq, bool) or not isinstance(self.evidence_turn_seq, int):
            raise ValidationError(
                f"Score marker evidence turn must be an integer, got {self.evidence_turn_seq!r}."
            )
        if self.evidence_turn_seq < 0:
            raise ValidationError("Score marker evidence turn must be non-negative.")
        if not self.quote.strip():
            raise ValidationError(
                f"Score marker for {self.dimension!r} must quote the evidence it relies on."
            )

    @property
    def is_positive(self) -> bool:
        return self.polarity.is_positive
