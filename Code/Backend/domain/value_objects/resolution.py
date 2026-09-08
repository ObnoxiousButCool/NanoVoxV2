"""Call outcome.

Modelled as an enum rather than as taxonomy data because the aggregation code
branches on specific members: first-contact resolution and the escalation rate
are defined in terms of RESOLVED and ESCALATED. A value that code must reason
about individually is part of the model, not configuration.
"""

from __future__ import annotations

from enum import Enum


class Resolution(str, Enum):
    """The four outcomes used across the corpus index."""

    RESOLVED = "RESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY RESOLVED"
    ESCALATED = "ESCALATED"
    UNRESOLVED = "UNRESOLVED"

    @property
    def code(self) -> str:
        """The value, under the name the schema glossary reads."""
        return self.value

    @property
    def label(self) -> str:
        return self.value.title()

    @property
    def description(self) -> str:
        """What this outcome means, as the model is told it.

        These definitions exist because the bare names are not self-evident and
        the model read them generously. Given all four as a plain vocabulary it
        put 18 of 61 authored RESOLVED calls into PARTIALLY RESOLVED, and chose
        ESCALATED for none of the four calls authored that way. The boundary
        that fixes most of it is the one stated below: work that has been
        started and committed to is a resolution, not a partial one.
        """
        return _DESCRIPTIONS[self]

    @property
    def is_first_contact_resolution(self) -> bool:
        """Whether this outcome counts toward FCR.

        Only a full resolution counts. Partially resolved is deliberately
        excluded: counting it would inflate the figure against the industry
        benchmark it is compared with.
        """
        return self is Resolution.RESOLVED

    @property
    def needs_follow_up(self) -> bool:
        return self is not Resolution.RESOLVED


# Kept below the class so each definition can be a readable paragraph. The
# wording follows the corpus authors' own convention, taken from the insight
# panels rather than from the one-word header: a call where the agent opens a
# correction case, a dispute or a coordination request is written up as
# "RESOLVED - correction case opened", not as partial and not as escalated.
_DESCRIPTIONS: dict[Resolution, str] = {
    Resolution.RESOLVED: (
        "The caller's need was met during the call. This includes the case where "
        "the fix cannot complete inside the call but the agent has started it and "
        "committed to it: a correction case raised, a dispute opened, a credit "
        "requested, a form sent, a coordination request logged. A pending "
        "follow-up that the administrator now owns does not make the call "
        "partial. Choose this whenever the caller leaves knowing what will "
        "happen and who is doing it."
    ),
    Resolution.PARTIALLY_RESOLVED: (
        "The caller asked about more than one thing and at least one part was "
        "left undone with nothing arranged for it. The test is a distinct "
        "outstanding part, named in the call and unowned at the end of it - not "
        "a single request that was answered but will take time to complete. If "
        "you cannot say which part is still missing, this is not the right "
        "value."
    ),
    Resolution.ESCALATED: (
        "The call was handed to someone else - another team, a supervisor, the "
        "carrier - and the answer now depends on them rather than on anything "
        "the agent did. Use it where the handover is the outcome. Where the "
        "agent both escalated and told the caller what will happen next, that "
        "is RESOLVED."
    ),
    Resolution.UNRESOLVED: (
        "The caller ends the call with their need unmet and nothing arranged: no "
        "answer, no case, no next step, or a next step that puts the work back "
        "on them ('call your broker', 'try the portal again', 'speak to HR'). "
        "Being told to call back is not a resolution."
    ),
}
