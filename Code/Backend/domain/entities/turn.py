"""A single speaker turn.

``seq`` is the anchor for every piece of evidence in the system: a score marker,
a broker attribution and a real-time-assist trigger all point at a turn by
sequence number. Highlighting in the UI is driven from these indices rather than
by searching the transcript text in the browser, so evidence cannot drift from
what was actually scored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from domain.errors import ValidationError
from domain.value_objects.speaker import SpeakerRole

_WHITESPACE = re.compile(r"\s+")


def normalise_for_matching(text: str) -> str:
    """Collapse whitespace and case for quote comparison.

    A model reproduces a quote from a transcript that may have been wrapped
    across lines, so an exact comparison would reject correct evidence. Case and
    whitespace are the only tolerances allowed: the words themselves must match.
    """
    return _WHITESPACE.sub(" ", text).strip().casefold()


@dataclass(frozen=True)
class Turn:
    """One utterance by one speaker."""

    seq: int
    role: SpeakerRole
    text: str
    speaker_name: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.seq, bool) or not isinstance(self.seq, int) or self.seq < 0:
            raise ValidationError(
                f"Turn sequence must be a non-negative integer, got {self.seq!r}."
            )
        if not self.text.strip():
            raise ValidationError(f"Turn {self.seq} has no text.")

    def contains(self, quote: str) -> bool:
        """Whether ``quote`` genuinely appears in this turn."""
        if not quote.strip():
            return False
        return normalise_for_matching(quote) in normalise_for_matching(self.text)
