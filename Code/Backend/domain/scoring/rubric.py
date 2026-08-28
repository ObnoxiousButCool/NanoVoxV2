"""The rubric: the weights, thresholds and gates that turn markers into a score.

Loaded from ``config/rubric.yaml`` so a non-engineer can review and change what
each failure costs. Every field is validated on construction, because a rubric
that is quietly wrong produces numbers that look plausible and are not.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from domain.errors import NotFoundError, ValidationError
from domain.value_objects.tier import TierThresholds


@dataclass(frozen=True)
class Dimension:
    """One axis of agent performance and what it is worth.

    ``positive`` and ``negative`` are magnitudes: both are non-negative, and the
    engine decides the sign. Caps bound how far a single dimension can move the
    score, so a model that emits the same criticism five different ways cannot
    drive a call to zero on one issue.
    """

    code: str
    label: str
    positive: int
    negative: int
    max_positive: int
    max_negative: int

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValidationError("Rubric dimension code must not be empty.")
        for name, value in (
            ("positive", self.positive),
            ("negative", self.negative),
            ("max_positive", self.max_positive),
            ("max_negative", self.max_negative),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValidationError(
                    f"Rubric dimension {self.code!r} field {name} must be a "
                    f"non-negative magnitude, got {value!r}."
                )
        if self.max_positive < self.positive:
            raise ValidationError(
                f"Rubric dimension {self.code!r}: max_positive ({self.max_positive}) is "
                f"below the value of a single positive marker ({self.positive})."
            )
        if self.max_negative < self.negative:
            raise ValidationError(
                f"Rubric dimension {self.code!r}: max_negative ({self.max_negative}) is "
                f"below the value of a single negative marker ({self.negative})."
            )


class GateCondition(str, Enum):
    """What a gate examines."""

    SIGNAL_PRESENT = "signal_present"
    SCORE_BELOW = "score_below"


class GateEffect(str, Enum):
    """What a gate does when it triggers."""

    SUSPEND_SCORE = "suspend_score"


@dataclass(frozen=True)
class Gate:
    """A rule applied after arithmetic, able to override the result.

    The clinical gate is the reason this exists: a call where an agent missed a
    medical emergency must not present a confident number to a manager before a
    clinician has looked at it.
    """

    id: str
    condition: GateCondition
    argument: str
    effect: GateEffect
    message: str

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValidationError("Gate id must not be empty.")
        if not self.argument.strip():
            raise ValidationError(f"Gate {self.id!r} must specify an argument.")
        if not self.message.strip():
            raise ValidationError(f"Gate {self.id!r} must carry a message to show the reviewer.")
        if self.condition is GateCondition.SCORE_BELOW and not self._argument_is_int():
            raise ValidationError(
                f"Gate {self.id!r} uses score_below, so its argument must be a whole "
                f"number, got {self.argument!r}."
            )

    def _argument_is_int(self) -> bool:
        try:
            int(self.argument)
        except ValueError:
            return False
        return True

    @property
    def threshold(self) -> int:
        """The numeric argument, for conditions that take one."""
        return int(self.argument)


@dataclass(frozen=True)
class Rubric:
    """A complete, versioned scoring definition."""

    version: str
    base_score: int
    max_positive_offset: int
    dimensions: Mapping[str, Dimension]
    tiers: TierThresholds
    min_calls_for_tier_rating: int
    gates: tuple[Gate, ...] = ()

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValidationError("Rubric must declare a version.")
        if not 0 <= self.base_score <= 100:
            raise ValidationError(
                f"Rubric base_score must be between 0 and 100, got {self.base_score}."
            )
        if self.max_positive_offset < 0:
            raise ValidationError(
                f"Rubric max_positive_offset must not be negative, got {self.max_positive_offset}."
            )
        if not self.dimensions:
            raise ValidationError("Rubric must define at least one dimension.")
        if self.min_calls_for_tier_rating < 1:
            raise ValidationError(
                "Rubric min_calls_for_tier_rating must be at least 1, "
                f"got {self.min_calls_for_tier_rating}."
            )
        for code, dimension in self.dimensions.items():
            if code != dimension.code:
                raise ValidationError(
                    f"Rubric dimension is indexed as {code!r} but declares {dimension.code!r}."
                )
        seen: set[str] = set()
        for gate in self.gates:
            if gate.id in seen:
                raise ValidationError(f"Duplicate gate id in rubric: {gate.id!r}.")
            seen.add(gate.id)

    def dimension(self, code: str) -> Dimension:
        try:
            return self.dimensions[code]
        except KeyError as exc:
            raise NotFoundError(
                f"Unknown rubric dimension: {code!r}.",
                detail=f"Known dimensions: {', '.join(sorted(self.dimensions))}",
            ) from exc

    def has_dimension(self, code: str) -> bool:
        return code in self.dimensions
