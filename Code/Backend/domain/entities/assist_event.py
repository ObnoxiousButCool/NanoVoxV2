"""Real-time assist: what fired, or what should have fired and did not.

The prototype's L5 panel on Call #89 shows nothing firing, and presents that
absence as the finding. Modelling "should have fired" as a first-class state —
rather than as an empty list — is what makes that presentable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.errors import ValidationError
from domain.value_objects.severity import Severity


class AssistOutcome(str, Enum):
    """Whether the assist rule fired, and whether it should have."""

    FIRED = "FIRED"
    SHOULD_HAVE_FIRED = "SHOULD_HAVE_FIRED"


@dataclass(frozen=True)
class AssistEvent:
    """One real-time-assist observation for a call."""

    outcome: AssistOutcome
    trigger: str
    recommendation: str
    severity: Severity
    at_turn_seq: int | None = None
    timestamp_label: str | None = None

    def __post_init__(self) -> None:
        if not self.trigger.strip():
            raise ValidationError("Assist event must name the trigger.")
        if not self.recommendation.strip():
            raise ValidationError(
                f"Assist event {self.trigger!r} must state what should have happened."
            )
        if self.at_turn_seq is not None and (
            isinstance(self.at_turn_seq, bool)
            or not isinstance(self.at_turn_seq, int)
            or self.at_turn_seq < 0
        ):
            raise ValidationError(
                f"Assist event turn must be a non-negative integer, got {self.at_turn_seq!r}."
            )

    @property
    def is_gap(self) -> bool:
        """A rule that should have fired and did not — a finding, not an empty state."""
        return self.outcome is AssistOutcome.SHOULD_HAVE_FIRED
