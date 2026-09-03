"""Whether a quote actually shows a member naming their *broker*.

The evidence rule already in place asks whether the quoted words were really
said. It never asked whether they say what the attribution claims — so a
verbatim quote of a member naming their surgeon, their pharmacy, or the agent
they were talking to all passed, and each became a broker conduct record against
a real person.

Two checks close that, and both are deterministic:

* **The quote must name a broker relationship.** The L4 prompt has always said to
  quote "the words in which the member named that broker"; a quote containing no
  such word is not that evidence. On the shipped corpus this alone separated
  every genuine attribution from every false one.
* **The named party must not be the agent on the call.** An agent introducing
  themselves — "Choice Administrators, this is Carlos" — is not a member naming
  a broker, and we already know who the agent was.

Vocabulary is configuration. A plan that says "agent of record" or "producer"
should not need a release.
"""

from __future__ import annotations

import re
from re import Pattern

__all__ = [
    "compile_broker_terms",
    "is_the_agent",
    "quote_names_a_broker",
]


def compile_broker_terms(terms: str) -> Pattern[str] | None:
    """Compile a comma-separated vocabulary into one whole-word pattern.

    ``None`` when nothing is configured, which disables the check rather than
    matching nothing — an empty vocabulary must not silently reject every
    attribution.
    """
    words = [term.strip() for term in terms.split(",") if term.strip()]
    if not words:
        return None
    joined = "|".join(re.escape(word) for word in words)
    return re.compile(rf"\b(?:{joined})\b", re.IGNORECASE)


def quote_names_a_broker(quote: str, terms: Pattern[str] | None) -> bool:
    """Whether the quoted words describe a broker relationship at all."""
    if terms is None:
        return True
    return bool(terms.search(quote))


def is_the_agent(broker_name: str, agent_name: str | None) -> bool:
    """Whether the attribution names the agent who handled the call.

    Compared on the whole name rather than a first name: two different people
    called Sarah are not the same person, and treating them as one would drop a
    genuine attribution to protect against a rarer mistake.
    """
    if not agent_name:
        return False
    return broker_name.strip().casefold() == agent_name.strip().casefold()
