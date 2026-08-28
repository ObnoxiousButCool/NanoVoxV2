"""Turning pasted text into an ordered transcript.

The prototype states the rule the user sees: *"Turns are detected from the
speaker prefix. If everything lands on one line, the prefixes are missing."*
This module is that rule.

Two behaviours matter more than they look:

* **Continuation lines are joined to the turn above.** The corpus transcripts are
  hard-wrapped mid-sentence, so treating every line as a turn would shred them —
  and quotes spanning a wrap would then never validate against any single turn.
* **The speaker's role is inferred, not assumed.** "Agent Brad", "Brad", "Member"
  and "System" have to land on the right side, because scoring only judges what
  the *agent* said.
"""

from __future__ import annotations

import re

from domain.entities.transcript import Transcript
from domain.entities.turn import Turn
from domain.errors import ValidationError
from domain.value_objects.speaker import SpeakerRole

# "Speaker: text" — a short prefix before the first colon. Bounded so that a
# sentence containing a colon is not mistaken for a speaker change.
_SPEAKER_LINE = re.compile(r"^(?P<speaker>[^:]{1,40}?):\s*(?P<text>.*)$")

_AGENT_PREFIX = "agent"
_MEMBER_WORDS = frozenset({"member", "caller", "customer", "patient"})
_SYSTEM_WORDS = frozenset({"system", "ivr", "hold", "recording", "note"})

MISSING_PREFIX_HELP = (
    "No speaker turns were found. Each line must start with a speaker prefix, "
    "for example 'Agent Sarah: ...' or 'Member: ...'."
)


def _role_and_name(speaker: str) -> tuple[SpeakerRole, str | None]:
    cleaned = speaker.strip()
    lowered = cleaned.lower()

    if lowered in _SYSTEM_WORDS:
        return SpeakerRole.SYSTEM, None
    if lowered in _MEMBER_WORDS:
        return SpeakerRole.MEMBER, None
    if lowered.startswith(_AGENT_PREFIX):
        # "Agent Brad" -> Brad; a bare "Agent" has no name to record.
        name = cleaned[len(_AGENT_PREFIX) :].strip(" :-") or None
        return SpeakerRole.AGENT, name

    # An unqualified name is the agent: the corpus writes the member as "Member"
    # and names only the agent. Guessing the other way would attribute the
    # member's words to the agent's score.
    return SpeakerRole.AGENT, cleaned or None


def parse_transcript(text: str) -> Transcript:
    """Parse pasted text into a transcript.

    Raises:
        ValidationError: if no speaker prefixes were found, with the guidance the
            UI shows the user.
    """
    if not text.strip():
        raise ValidationError("The transcript is empty.", detail=MISSING_PREFIX_HELP)

    turns: list[Turn] = []
    speakers: list[tuple[SpeakerRole, str | None]] = []
    bodies: list[list[str]] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = _SPEAKER_LINE.match(line)
        if match is None:
            if bodies:
                # A wrapped continuation of the turn above.
                bodies[-1].append(line)
            continue

        speakers.append(_role_and_name(match.group("speaker")))
        bodies.append([match.group("text").strip()])

    for index, ((role, name), body) in enumerate(zip(speakers, bodies, strict=True)):
        joined = " ".join(part for part in body if part).strip()
        if not joined:
            # A prefix with nothing after it carries no evidence; keeping it would
            # shift every later turn index.
            continue
        turns.append(Turn(seq=index, role=role, text=joined, speaker_name=name))

    if not turns:
        raise ValidationError("No speaker turns were found.", detail=MISSING_PREFIX_HELP)

    # Sequences must be contiguous after any empty turns were dropped.
    return Transcript(
        tuple(
            Turn(seq=position, role=turn.role, text=turn.text, speaker_name=turn.speaker_name)
            for position, turn in enumerate(turns)
        )
    )


def count_turns(text: str) -> int:
    """How many turns the parser would find. Used for the live counter in the UI."""
    try:
        return parse_transcript(text).turn_count
    except ValidationError:
        return 0
