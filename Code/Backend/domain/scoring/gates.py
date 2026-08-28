"""Gate evaluation.

Gates run after the arithmetic and can override its conclusion. They are
deliberately separate from the weights: "this call needs a clinician to look at
it before anyone quotes a number" is a policy, not a penalty, and conflating the
two would mean expressing a safety rule as a subtraction.
"""

from __future__ import annotations

from collections.abc import Collection

from domain.scoring.rubric import Gate, GateCondition
from domain.value_objects.score import Score


def gate_applies(gate: Gate, *, score: Score, signal_codes: Collection[str]) -> bool:
    """Whether this gate's condition is met."""
    if gate.condition is GateCondition.SIGNAL_PRESENT:
        return gate.argument in signal_codes
    return score.value < gate.threshold


def triggered_gates(
    gates: Collection[Gate], *, score: Score, signal_codes: Collection[str]
) -> tuple[Gate, ...]:
    """Every gate whose condition is met, in declaration order."""
    return tuple(
        gate for gate in gates if gate_applies(gate, score=score, signal_codes=signal_codes)
    )
