"""Validation of model-supplied score markers against the transcript.

Step 2 of the scoring pipeline (plan §5.1). A marker is only allowed to affect
the score if it names a dimension the rubric knows, points at a turn that exists,
and quotes text that genuinely appears in that turn.

Rejected markers are returned rather than discarded silently: a model that keeps
inventing quotes is a finding about the model, and the caller logs it.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum

from domain.entities.score_marker import ScoreMarker
from domain.entities.transcript import Transcript
from domain.scoring.rubric import Rubric


class RejectionReason(str, Enum):
    """Why a marker was refused."""

    UNKNOWN_DIMENSION = "unknown_dimension"
    MISSING_TURN = "missing_turn"
    QUOTE_NOT_IN_TURN = "quote_not_in_turn"


@dataclass(frozen=True)
class RejectedMarker:
    """A marker that was refused, and the reason."""

    marker: ScoreMarker
    reason: RejectionReason

    @property
    def explanation(self) -> str:
        if self.reason is RejectionReason.UNKNOWN_DIMENSION:
            return f"Dimension {self.marker.dimension!r} is not in the rubric."
        if self.reason is RejectionReason.MISSING_TURN:
            return f"Transcript has no turn {self.marker.evidence_turn_seq}."
        return (
            f"Quoted text does not appear in turn {self.marker.evidence_turn_seq}: "
            f"{self.marker.quote!r}"
        )


@dataclass(frozen=True)
class MarkerValidation:
    """The outcome of validating a batch of markers."""

    accepted: tuple[ScoreMarker, ...]
    rejected: tuple[RejectedMarker, ...]

    @property
    def has_rejections(self) -> bool:
        return bool(self.rejected)

    @property
    def rejection_summary(self) -> str:
        return "; ".join(item.explanation for item in self.rejected)


class MarkerValidator:
    """Checks markers against a rubric and the transcript they claim to cite."""

    def __init__(self, rubric: Rubric, transcript: Transcript) -> None:
        self._rubric = rubric
        self._transcript = transcript

    def validate(self, markers: Iterable[ScoreMarker]) -> MarkerValidation:
        accepted: list[ScoreMarker] = []
        rejected: list[RejectedMarker] = []

        for marker in markers:
            reason = self._reject_reason(marker)
            if reason is None:
                accepted.append(marker)
            else:
                rejected.append(RejectedMarker(marker=marker, reason=reason))

        return MarkerValidation(accepted=tuple(accepted), rejected=tuple(rejected))

    def _reject_reason(self, marker: ScoreMarker) -> RejectionReason | None:
        if not self._rubric.has_dimension(marker.dimension):
            return RejectionReason.UNKNOWN_DIMENSION

        turn = self._transcript.turn(marker.evidence_turn_seq)
        if turn is None:
            return RejectionReason.MISSING_TURN

        if not turn.contains(marker.quote):
            return RejectionReason.QUOTE_NOT_IN_TURN

        return None


def accepted_markers(
    rubric: Rubric, transcript: Transcript, markers: Sequence[ScoreMarker]
) -> MarkerValidation:
    """Convenience wrapper for the common one-shot case."""
    return MarkerValidator(rubric, transcript).validate(markers)
