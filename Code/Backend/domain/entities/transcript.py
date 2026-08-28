"""An ordered sequence of speaker turns."""

from __future__ import annotations

from dataclasses import dataclass

from domain.entities.turn import Turn
from domain.errors import ValidationError
from domain.value_objects.speaker import SpeakerRole


@dataclass(frozen=True)
class Transcript:
    """The turns of one call, in order."""

    turns: tuple[Turn, ...]

    def __post_init__(self) -> None:
        if not self.turns:
            raise ValidationError("A transcript must contain at least one speaker turn.")

        seen: set[int] = set()
        previous = -1
        for turn in self.turns:
            if turn.seq in seen:
                raise ValidationError(f"Transcript has a duplicate turn sequence: {turn.seq}.")
            if turn.seq <= previous:
                raise ValidationError(
                    f"Transcript turns must be in ascending sequence; "
                    f"{turn.seq} follows {previous}."
                )
            seen.add(turn.seq)
            previous = turn.seq

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def speaker_count(self) -> int:
        """Distinct participating speakers, excluding system lines."""
        return len({turn.role for turn in self.turns if turn.role is not SpeakerRole.SYSTEM})

    def turn(self, seq: int) -> Turn | None:
        """The turn with this sequence number, or ``None`` if there is none."""
        for turn in self.turns:
            if turn.seq == seq:
                return turn
        return None

    def turns_for(self, role: SpeakerRole) -> tuple[Turn, ...]:
        return tuple(turn for turn in self.turns if turn.role is role)
