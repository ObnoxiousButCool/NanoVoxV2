"""A conduct or quality signal attributed to a named broker.

This is the highest-risk record in the system: it names a real person. The rule
from the prototype's attribution panel is enforced here rather than trusted to a
prompt — a signal is only valid when the member named the broker aloud in the
call, or the member ID resolved to a broker of record. Either way it carries the
sentence that produced it. Nothing is inferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.errors import ValidationError
from domain.value_objects.polarity import Polarity


class AttributionBasis(str, Enum):
    """How the broker came to be attached to this call."""

    NAMED_IN_CALL = "NAMED_IN_CALL"
    BROKER_OF_RECORD = "BROKER_OF_RECORD"


@dataclass(frozen=True)
class BrokerSignal:
    """One observation about a broker, tied to the evidence for it."""

    broker_name: str
    polarity: Polarity
    basis: AttributionBasis
    issue: str
    evidence_turn_seq: int
    quote: str

    def __post_init__(self) -> None:
        if not self.broker_name.strip():
            raise ValidationError("Broker signal must name the broker.")
        if not self.issue.strip():
            raise ValidationError(
                f"Broker signal for {self.broker_name!r} must describe the issue."
            )
        if isinstance(self.evidence_turn_seq, bool) or not isinstance(self.evidence_turn_seq, int):
            raise ValidationError(
                f"Broker signal evidence turn must be an integer, got {self.evidence_turn_seq!r}."
            )
        if self.evidence_turn_seq < 0:
            raise ValidationError("Broker signal evidence turn must be non-negative.")
        if not self.quote.strip():
            # Without the sentence, the claim is unverifiable — and this one names
            # a person. An unevidenced attribution must not be storable at all.
            raise ValidationError(
                f"Broker signal for {self.broker_name!r} must quote the sentence that produced it."
            )

    @property
    def is_negative(self) -> bool:
        return not self.polarity.is_positive
