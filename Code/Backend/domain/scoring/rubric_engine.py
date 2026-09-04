"""The scoring engine.

Pure arithmetic over validated markers. Given the same markers and the same
rubric it returns the same score, on any provider, on any machine — which is the
property that makes the number auditable (DEC-03).

The model of the calculation is:

1. Start at ``base_score``. 100 means "nothing went wrong".
2. Sum negative markers per dimension, capping each dimension at its
   ``max_negative``, so one repeated criticism cannot sink a call on its own.
3. Sum positive markers the same way against ``max_positive``.
4. Positives *offset* penalties rather than adding to the score, and only up to
   ``max_positive_offset``. Good handling can soften a bad call; it cannot erase
   a compliance failure, and it cannot lift a call above "nothing went wrong".
5. Clamp into 0-100, derive the tier, then run the gates.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field

from domain.entities.score_marker import ScoreMarker
from domain.scoring.gates import triggered_gates
from domain.scoring.rubric import Gate, GateEffect, Rubric
from domain.value_objects.polarity import Polarity
from domain.value_objects.score import Score, ScoreStatus
from domain.value_objects.tier import Tier


@dataclass(frozen=True)
class AppliedMarker:
    """A marker together with the signed points it contributed."""

    marker: ScoreMarker
    points: int


@dataclass(frozen=True)
class DimensionTotal:
    """What one dimension contributed, before and after its cap."""

    code: str
    positive: int
    negative: int
    positive_before_cap: int
    negative_before_cap: int

    @property
    def positive_was_capped(self) -> bool:
        return self.positive_before_cap > self.positive

    @property
    def negative_was_capped(self) -> bool:
        return self.negative_before_cap > self.negative


@dataclass(frozen=True)
class ScoreResult:
    """A computed score and the full working behind it."""

    score: Score
    status: ScoreStatus
    tier: Tier
    applied: tuple[AppliedMarker, ...]
    dimension_totals: Mapping[str, DimensionTotal]
    total_positive: int
    total_negative: int
    applied_offset: int
    triggered_gate_ids: tuple[str, ...] = ()
    messages: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_provisional(self) -> bool:
        return self.status is ScoreStatus.PROVISIONAL

    @property
    def net_penalty(self) -> int:
        return max(0, self.total_negative - self.applied_offset)


class RubricEngine:
    """Turns validated markers into a score, deterministically."""

    def __init__(self, rubric: Rubric) -> None:
        self._rubric = rubric

    @property
    def rubric(self) -> Rubric:
        return self._rubric

    def score(
        self,
        markers: Sequence[ScoreMarker],
        signal_codes: Collection[str] = (),
        *,
        evidence_all_rejected: bool = False,
    ) -> ScoreResult:
        """Score a call.

        ``markers`` must already have been validated: this method assumes every
        dimension exists, and will raise if one does not, because scoring an
        unknown dimension would silently drop a penalty.
        """
        applied, totals = self._apply(markers)

        total_positive = sum(total.positive for total in totals.values())
        total_negative = sum(total.negative for total in totals.values())

        # Positives offset penalties; they never lift the score above base.
        applied_offset = min(total_positive, self._rubric.max_positive_offset, total_negative)
        raw = self._rubric.base_score - (total_negative - applied_offset)

        score = Score.clamped(raw)
        tier = self._rubric.tiers.tier_for(score)

        gates = triggered_gates(self._rubric.gates, score=score, signal_codes=signal_codes)
        status = self._status_for(gates, evidence_all_rejected=evidence_all_rejected)

        return ScoreResult(
            score=score,
            status=status,
            tier=tier,
            applied=applied,
            dimension_totals=totals,
            total_positive=total_positive,
            total_negative=total_negative,
            applied_offset=applied_offset,
            triggered_gate_ids=tuple(gate.id for gate in gates),
            messages=tuple(gate.message for gate in gates),
        )

    def _apply(
        self, markers: Sequence[ScoreMarker]
    ) -> tuple[tuple[AppliedMarker, ...], dict[str, DimensionTotal]]:
        raw_positive: dict[str, int] = {}
        raw_negative: dict[str, int] = {}
        applied: list[AppliedMarker] = []

        for marker in markers:
            dimension = self._rubric.dimension(marker.dimension)
            if marker.polarity is Polarity.POSITIVE:
                raw_positive[dimension.code] = raw_positive.get(dimension.code, 0) + (
                    dimension.positive
                )
                applied.append(AppliedMarker(marker=marker, points=dimension.positive))
            else:
                raw_negative[dimension.code] = raw_negative.get(dimension.code, 0) + (
                    dimension.negative
                )
                applied.append(AppliedMarker(marker=marker, points=-dimension.negative))

        totals: dict[str, DimensionTotal] = {}
        for code in sorted(set(raw_positive) | set(raw_negative)):
            dimension = self._rubric.dimension(code)
            positive_before = raw_positive.get(code, 0)
            negative_before = raw_negative.get(code, 0)
            totals[code] = DimensionTotal(
                code=code,
                positive=min(positive_before, dimension.max_positive),
                negative=min(negative_before, dimension.max_negative),
                positive_before_cap=positive_before,
                negative_before_cap=negative_before,
            )

        return tuple(applied), totals

    @staticmethod
    def _status_for(gates: Collection[Gate], *, evidence_all_rejected: bool) -> ScoreStatus:
        if any(gate.effect is GateEffect.SUSPEND_SCORE for gate in gates):
            return ScoreStatus.PROVISIONAL
        if evidence_all_rejected:
            # Every marker the model raised failed checking, so the arithmetic
            # ran over nothing: no penalty was applied because none survived,
            # and the base score came through untouched. That is not a call that
            # went well, it is a call nobody has scored — and confirming it
            # would publish the highest number on the dashboard for the least
            # evidence behind it.
            return ScoreStatus.PROVISIONAL
        return ScoreStatus.CONFIRMED
