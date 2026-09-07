"""Statistical significance for agent-level reporting.

Publishing a tier for an agent on three or four calls would be unfair to the
agent and misleading to the manager reading it, so agents below the threshold are
shown — the volume is real — but not tier-rated. The prototype states this rule
on the chart; it is enforced here so it cannot be forgotten by a caller.

The shipped corpus no longer exercises the rule: all thirteen of its agents carry
six calls or more. The rule is kept for the corpus that will, and the threshold
itself lives in ``rubric.yaml`` rather than here.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.errors import ValidationError
from domain.value_objects.score import Score
from domain.value_objects.tier import Tier, TierThresholds

BELOW_THRESHOLD_NOTE = "Below n={minimum} significance threshold"


def is_tier_rated(call_count: int, minimum: int) -> bool:
    """Whether an agent has enough calls to be given a tier."""
    if minimum < 1:
        raise ValidationError(f"Significance threshold must be at least 1, got {minimum}.")
    return call_count >= minimum


@dataclass(frozen=True)
class AgentRating:
    """An agent's tier, or an explicit refusal to assign one."""

    tier: Tier | None
    note: str | None

    @property
    def is_rated(self) -> bool:
        return self.tier is not None


def rate_agent(
    *, average_score: Score, call_count: int, minimum: int, thresholds: TierThresholds
) -> AgentRating:
    """Assign a tier, or decline to when the sample is too small."""
    if not is_tier_rated(call_count, minimum):
        return AgentRating(tier=None, note=BELOW_THRESHOLD_NOTE.format(minimum=minimum))
    return AgentRating(tier=thresholds.tier_for(average_score), note=None)
