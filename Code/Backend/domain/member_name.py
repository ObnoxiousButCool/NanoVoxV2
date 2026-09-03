"""The member's name, recovered from the summary a call already carries.

``member_context`` is a sentence written about the caller, and most of them open
with the person: *"Maria Gonzalez, a member needing prior authorization…"*. The
name is right there, it just was never kept in a field of its own.

**Only that opening form is read.** A name is the one thing on this dashboard a
reader will recognise personally, and attaching the wrong one to a list titled
"members at risk" is a worse failure than showing an identifier. So the rule is
narrow on purpose: capitalised words at the very start, followed by a comma. A
context written as *"A member who was misinformed about dental coverage"* yields
nothing, and nothing is what the caller gets — the screen then shows the
identifier alone, which is still true.

The rule is deliberately not a general name-finder. Scanning the whole sentence
would pick up the agent, a doctor, an employer or a plan name, all of which
appear in these summaries and any of which would then be printed as the member.
"""

from __future__ import annotations

import re

__all__ = ["find_member_name"]

# Up to four capitalised words at the start, then a comma. Four covers a double
# first name and a double surname; more than that is a sentence, not a name.
#
# The character class allows the apostrophes and hyphens that real names carry
# ("O'Brien", "Smith-Jones", both curly and straight apostrophes, since the text
# comes from a model and is inconsistent about them).
# The curly apostrophe is built from its code point rather than typed: as a
# literal it is hard to tell from a backtick in a diff, and it has to stay
# exactly what it is.
_APOSTROPHES = "'" + chr(0x2019)
_WORD = rf"[A-Z][\w{_APOSTROPHES}.-]*"

# Lowercase particles that sit inside a surname. Without them "Juan Carlos de
# Vega" is read as "Juan Carlos" — a different person's name, printed with
# confidence, which is the failure this module exists to avoid.
_PARTICLE = r"(?:de|del|della|da|di|dos|van|von|der|den|ter|la|le|du|bin|ibn|al|of)"

# A particle only ever appears *before* another capitalised word, so a trailing
# "Maria de," cannot match and leave a dangling word.
_LEADING_NAME = re.compile(rf"^\s*({_WORD}(?:\s+(?:{_PARTICLE}\s+)?{_WORD}){{0,3}})\s*,")

# Words that start a sentence about a member rather than naming one. Without
# this, "Member is inquiring about a denied claim" reads as a person called
# "Member" — capitalised, at the start, and followed by nothing that says
# otherwise.
_NOT_A_NAME = frozenset({"member", "caller", "patient", "the", "a", "an", "this", "his", "her"})


def find_member_name(member_context: str | None) -> str | None:
    """The member's name if the context opens with one, otherwise ``None``.

    ``None`` is a real answer here, not a failure: roughly a third of these
    summaries describe the caller instead of naming them, and there is nothing
    in the text to recover.
    """
    if not member_context:
        return None

    match = _LEADING_NAME.match(member_context)
    if not match:
        return None

    name = " ".join(match.group(1).split())
    if name.split()[0].strip(".").lower() in _NOT_A_NAME:
        return None
    return name
