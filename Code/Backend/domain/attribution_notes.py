"""The wording of a discarded broker attribution, written and read in one place.

A rejected attribution is kept as a sentence, because its first audience is a
person reading one call. But the brokers screen needs to count discards per
broker, which means reading the name back out of that sentence.

Producing and parsing therefore live together here. Split across two modules
they would drift, and the failure would be silent: a reworded note would simply
stop being counted rather than raise.
"""

from __future__ import annotations

import ast
import re

_PREFIX = "Attribution to "
# The name is emitted with repr(), so it is quoted with ' unless it contains
# one, in which case Python switches to ". Both forms must read back.
_NAME = re.compile(r"^Attribution to ('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")")


def missing_turn_note(broker_name: str, turn_seq: int) -> str:
    """The attribution cites a turn the transcript does not have."""
    return f"{_PREFIX}{broker_name!r} cites turn {turn_seq}, which does not exist."


def quote_not_found_note(broker_name: str, turn_seq: int, quote: str) -> str:
    """The cited turn exists, but does not contain the quoted words."""
    return (
        f"{_PREFIX}{broker_name!r} quotes text that does not appear "
        f"in turn {turn_seq}: {quote!r}"
    )


def broker_name_in(note: str) -> str | None:
    """The broker a note refers to, or ``None`` if it is not one of ours.

    Returning ``None`` rather than raising keeps an unrecognised note countable
    in the corpus total: a discard we cannot attribute is still a discard, and
    dropping it silently would understate the number.
    """
    match = _NAME.match(note)
    if match is None:
        return None
    try:
        name = ast.literal_eval(match.group(1))
    except (ValueError, SyntaxError):
        return None
    return name if isinstance(name, str) and name else None
