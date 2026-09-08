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

Both were necessary and neither was sufficient. On the timestamped corpus the
only two attributions in the system quoted an *agent* saying "talk to your
broker", and named the administrator whose greeting opens every call — a quote
containing the word "broker", naming nobody, spoken by the wrong person. So
three more checks, all equally deterministic:

* **The quote must actually name the party.** "Your broker can pull it" is not
  evidence that the broker is anyone in particular. If the attributed name
  appears nowhere in the words quoted, the citation is decorative.
* **The words must be the caller's.** The prompt has always said the *member*
  names the broker aloud; nothing enforced it, and an agent recommending that
  someone consult a broker was read as the someone naming one.
* **Our own organisation is never a broker.** The administrator's name is the
  one name spoken in every call in the corpus, and the one name that cannot be
  the answer.

Vocabulary is configuration. A plan that says "agent of record" or "producer"
should not need a release, and neither should the administrator's own name.
"""

from __future__ import annotations

import re
from re import Pattern

__all__ = [
    "compile_broker_terms",
    "is_our_organisation",
    "is_the_agent",
    "quote_names_a_broker",
    "quote_names_the_party",
]

# Words that identify nobody on their own. A quote saying "benefits" is not
# evidence for "Rossi Benefits"; a quote saying "Rossi" is. Kept deliberately
# short: every word here is one that cannot carry an attribution by itself, not
# every word that happens to be common.
_GENERIC_NAME_WORDS = frozenset(
    {
        "agencies",
        "agency",
        "and",
        "associates",
        "benefit",
        "benefits",
        "brokerage",
        "co",
        "company",
        "consultants",
        "consulting",
        "corp",
        "corporation",
        "group",
        "groups",
        "inc",
        "insurance",
        "llc",
        "llp",
        "ltd",
        "of",
        "partners",
        "service",
        "services",
        "solutions",
        "the",
    }
)

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


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


def _words(text: str) -> list[str]:
    """The alphabetic words of a name or quote, casefolded."""
    return [match.group().casefold() for match in _WORD.finditer(text)]


def quote_names_the_party(quote: str, broker_name: str) -> bool:
    """Whether the quoted words name the party the attribution is about.

    Matched on the distinctive words of the name rather than the whole string: a
    member says "my broker is Rossi" about an agency filed as "Rossi Benefits
    Group", and demanding the full name would discard that. A name made only of
    generic words has no distinctive part, so it has to appear in full.
    """
    if not broker_name.strip():
        return False

    name_words = _words(broker_name)
    if not name_words:
        return False

    quote_words = set(_words(quote))
    distinctive = [word for word in name_words if word not in _GENERIC_NAME_WORDS]
    if distinctive:
        return any(word in quote_words for word in distinctive)

    # Nothing distinctive to look for, so the words must appear together and in
    # order — otherwise "the group" in any quote would evidence "The Group".
    return " ".join(name_words) in " ".join(_words(quote))


def is_our_organisation(broker_name: str, administrator_name: str | None) -> bool:
    """Whether the attribution names the plan administrator rather than a broker.

    Containment rather than equality: the administrator's name reaches the model
    through a greeting, and comes back with a suffix attached as often as not
    ("Choice Administrators TPA"). ``None`` or blank disables the check.
    """
    if not administrator_name or not administrator_name.strip():
        return False
    return " ".join(_words(administrator_name)) in " ".join(_words(broker_name))


def is_the_agent(broker_name: str, agent_name: str | None) -> bool:
    """Whether the attribution names the agent who handled the call.

    Compared on the whole name rather than a first name: two different people
    called Sarah are not the same person, and treating them as one would drop a
    genuine attribution to protect against a rarer mistake.
    """
    if not agent_name:
        return False
    return broker_name.strip().casefold() == agent_name.strip().casefold()
