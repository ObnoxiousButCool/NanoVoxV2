"""Find the member's identifier in a transcript.

Members read their ID aloud to identify themselves, so it is already in the
words of the call. Recording it is what lets one member's calls be seen as one
member's calls — without it every call is an unrelated event, and nobody can be
noticed ringing for the third time about the same unfixed problem.

Extracted by pattern rather than by the model. An ID is a fixed shape, so a
pattern is exact, free and repeatable, where a model would be approximate,
billed, and capable of inventing a plausible number that belongs to somebody
else. That last failure is the reason this is not a model's job: a wrong ID does
not look wrong.

The pattern itself is configuration. A different plan administrator issues
different identifiers, and that is not a code change.
"""

from __future__ import annotations

import re
from re import Pattern

from domain.entities.transcript import Transcript
from domain.value_objects.speaker import SpeakerRole

__all__ = ["compile_member_id_pattern", "find_member_id"]


def compile_member_id_pattern(pattern: str) -> Pattern[str]:
    """Compile a configured member-ID pattern, case-insensitively."""
    return re.compile(pattern, re.IGNORECASE)


def find_member_id(transcript: Transcript, pattern: Pattern[str]) -> str | None:
    """The member's ID, or ``None`` if the call never states one.

    The member's own turns are searched first. An agent reads IDs back, and
    handles more than one member a day, so a number in an agent's turn is the
    weaker evidence of the two — it is used only when the member never gave one.

    Returns the first match rather than trying to reconcile several. A call
    naming two IDs is a genuine ambiguity, and guessing between them would
    attribute one member's history to another.
    """
    for role in (SpeakerRole.MEMBER, SpeakerRole.AGENT):
        for turn in transcript.turns:
            if turn.role is not role:
                continue
            match = pattern.search(turn.text)
            if match is not None:
                return _normalise(match)
    return None


def _normalise(match: re.Match[str]) -> str:
    """The matched ID in a single canonical form.

    Spoken IDs are transcribed inconsistently — ``CHM-1234567``, ``CHM 1234567``,
    ``chm1234567`` are one member. Every separator is removed rather than
    standardised, because standardising on a dash still leaves the unseparated
    form different from the other two. Three spellings of one member would defeat
    the repeat-contact count this column exists for.

    A capture group wins when the pattern defines one, so a pattern may match
    surrounding words while still naming just the identifier.
    """
    captured = match.group(1) if match.re.groups else match.group(0)
    return re.sub(r"[^A-Za-z0-9]+", "", captured).upper()
