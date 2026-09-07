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

A label is read with different strictness depending on where it sits, and the
asymmetry is the point:

* **At the start of a line, almost anything is a speaker.** Somebody put it on
  its own line, so ambiguity resolves toward "this names a speaker" — which is
  what keeps a bare "Brad:" working. It still has to *look* like a label, or a
  wrapped sentence carrying an early colon gets read as a speaker: one line of
  the shipped corpus produced a turn spoken by an agent called "new enrollments
  effective the 1st".
* **Mid-line, only a recognised role is.** Ambiguity resolves the other way,
  toward "this is prose", because a colon inside speech is ordinary — five of
  the corpus's 758 turns contain one. Recognising them there is what rescues a
  transcript pasted with its line breaks stripped, which otherwise collapses
  into a single turn with every speaker attributed to whoever spoke first.
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

# The words that may open a turn from inside a line. Narrower than the set above
# on purpose: "note", "hold" and "recording" are things people say mid-sentence
# — "one thing worth noting:" — and splitting on them would invent a speaker out
# of a turn of phrase. A role recognised here may carry up to two capitalised
# words after it, which covers "Agent Sarah" and "Agent Mary Beth".
_INLINE_ROLE = r"(?:agent|member|caller|customer|patient|system|ivr)"

# A turn ends before the next speaker begins, so an inline label only counts
# where a sentence has just closed. Without that, "I told the member: it was
# already paid" opens a turn for the member in the middle of the agent's
# sentence. Every one of the 707 speaker boundaries in the shipped corpus ends
# in a full stop or a question mark, so the rule costs nothing there \u2014 and a
# closing quote is allowed to sit between the two ("call back." Caller: ...).
_SENTENCE_END = r"[.!?][\"'\u201d\u2019]?"
#
# The boundary is matched rather than looked behind, because an optional closing
# quote makes it variable width. The cut therefore uses the *speaker* group's
# start, which leaves the full stop on the turn it ended.
_INLINE_LABEL = re.compile(
    rf"(?:^|{_SENTENCE_END}\s+)"
    rf"(?P<speaker>{_INLINE_ROLE}(?:\s+[A-Z][\w'\u2019.-]*){{0,2}})\s*:\s+",
    re.IGNORECASE,
)

# A name is short and capitalised. Longer than this and it is a sentence that
# happens to contain a colon, not somebody's name.
_MOST_WORDS_IN_A_NAME = 3

MISSING_PREFIX_HELP = (
    "No speaker turns were found. Each line must start with a speaker prefix, "
    "for example 'Agent Sarah: ...' or 'Member: ...'."
)


def _looks_like_label(speaker: str) -> bool:
    """Whether a line's prefix names a speaker rather than ending a clause.

    A recognised role always does. Anything else has to read as a name — short,
    and capitalised the way names are — because the alternative is treating the
    front of a wrapped sentence as a person.
    """
    cleaned = speaker.strip()
    if not cleaned:
        return False

    words = cleaned.split()
    if words[0].lower().strip(".,") in _MEMBER_WORDS | _SYSTEM_WORDS:
        return True
    if words[0].lower().startswith(_AGENT_PREFIX):
        return True

    return len(words) <= _MOST_WORDS_IN_A_NAME and all(word[:1].isupper() for word in words)


def _inline_segments(text: str) -> list[tuple[str | None, str]]:
    """One line's text, cut at every recognised speaker label inside it.

    The first segment's label is ``None``: whatever precedes the first inline
    label belongs to the speaker who opened the line, or — where nothing opened
    it — to the turn above.
    """
    segments: list[tuple[str | None, str]] = []
    speaker: str | None = None
    cursor = 0

    for match in _INLINE_LABEL.finditer(text):
        segments.append((speaker, text[cursor : match.start("speaker")].strip()))
        speaker = match.group("speaker")
        cursor = match.end()

    segments.append((speaker, text[cursor:].strip()))
    return segments


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
        opening: str | None = None
        remainder = line
        if match is not None and _looks_like_label(match.group("speaker")):
            opening = match.group("speaker")
            remainder = match.group("text")

        for inline, body in _inline_segments(remainder):
            speaker = inline if inline is not None else opening
            if speaker is None:
                # A wrapped continuation of the turn above, or text before any
                # prefix — which belongs to no turn.
                if bodies:
                    bodies[-1].append(body)
                continue
            speakers.append(_role_and_name(speaker))
            bodies.append([body])

    for index, ((role, name), parts) in enumerate(zip(speakers, bodies, strict=True)):
        joined = " ".join(part for part in parts if part).strip()
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
