"""Which members show signs of leaving, and on what evidence.

**This does not predict churn, and does not pretend to.** Nothing in this system
yet records whether a member actually left, so no weight here has ever been
measured against an outcome. What it does instead is count the warning signs a
member is carrying and name them.

That distinction is the whole design. A single number — "73% churn risk" — would
be indistinguishable from a measured one while being pure invention, and would
be acted on as though it were fact. A list of factors is honest about what it
knows: *this member's issue is unresolved, they ended the call unhappy, and this
is their third call.* Someone can read that and decide. They cannot argue with a
percentage.

The ordering is by how many independent signs a member shows, because a member
carrying three is more clearly in trouble than one carrying any single sign —
that much is true without needing outcome data. Once membership outcomes exist
(and the join can be measured), these factors become candidates for a weighted
score, and the weights should come from that measurement rather than from here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# Sentiment states in which a member has plainly not been left in a good place.
# Drawn from the taxonomy's vocabulary; a state absent here is not "good", it is
# merely not evidence of a member at risk.
UNHAPPY_ENDINGS: frozenset[str] = frozenset(
    {
        "FRUSTRATED",
        "ANGRY",
        "DISTRESSED",
        "PANICKED",
        "ALARMED",
        "RESIGNED",
        "DISMISSED",
        "ABANDONED",
    }
)


class RiskFactor(str, Enum):
    """One observable reason to think a member may be leaving."""

    UNRESOLVED = "unresolved"
    ENDED_UNHAPPY = "ended_unhappy"
    REPEAT_CONTACT = "repeat_contact"
    LOW_SCORE = "low_score"
    ESCALATED = "escalated"

    @property
    def label(self) -> str:
        return {
            RiskFactor.UNRESOLVED: "Issue unresolved",
            RiskFactor.ENDED_UNHAPPY: "Ended the call unhappy",
            RiskFactor.REPEAT_CONTACT: "Has called more than once",
            RiskFactor.LOW_SCORE: "Poorly handled",
            RiskFactor.ESCALATED: "Escalated without resolution",
        }[self]


@dataclass(frozen=True)
class MemberCalls:
    """What is known about one member's calls, counted in SQL."""

    member_id: str
    # None where no call of theirs stated a name. The identifier always exists;
    # the name is the part that may not.
    member_name: str | None
    call_count: int
    # Minutes across every call this member made, and whether any of them ended
    # resolved. Together they answer what an answer cost this person.
    total_minutes: int
    resolved: int
    unresolved: int
    escalated: int
    ended_unhappy: int
    lowest_score: int
    latest_reference: str
    references: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemberAtRisk:
    """A member and the signs they are showing."""

    member_id: str
    member_name: str | None
    call_count: int
    factors: tuple[RiskFactor, ...]
    lowest_score: int
    latest_reference: str
    references: tuple[str, ...] = ()

    @property
    def rank_key(self) -> tuple[int, int, int]:
        """Most signs first, then most contact, then worst handling.

        Negated so a plain descending sort reads naturally at the call site.
        """
        return (-len(self.factors), -self.call_count, self.lowest_score)


def assess(member: MemberCalls, *, coaching_threshold: int) -> MemberAtRisk:
    """Name the risk factors one member's calls show."""
    factors: list[RiskFactor] = []

    if member.unresolved > 0:
        factors.append(RiskFactor.UNRESOLVED)
    if member.escalated > 0:
        factors.append(RiskFactor.ESCALATED)
    if member.ended_unhappy > 0:
        factors.append(RiskFactor.ENDED_UNHAPPY)
    if member.call_count > 1:
        factors.append(RiskFactor.REPEAT_CONTACT)
    if member.lowest_score < coaching_threshold:
        factors.append(RiskFactor.LOW_SCORE)

    return MemberAtRisk(
        member_id=member.member_id,
        member_name=member.member_name,
        call_count=member.call_count,
        factors=tuple(factors),
        lowest_score=member.lowest_score,
        latest_reference=member.latest_reference,
        references=member.references,
    )


def members_at_risk(
    members: tuple[MemberCalls, ...], *, coaching_threshold: int
) -> tuple[MemberAtRisk, ...]:
    """Rank the members showing at least one sign.

    Members showing none are omitted rather than listed with an empty row: this
    is a work queue, and a queue that lists everybody is not one.
    """
    assessed = (assess(member, coaching_threshold=coaching_threshold) for member in members)
    at_risk = [member for member in assessed if member.factors]
    return tuple(sorted(at_risk, key=lambda member: member.rank_key))
