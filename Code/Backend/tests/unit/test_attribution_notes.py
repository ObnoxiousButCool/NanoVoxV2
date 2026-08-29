"""Discarded-attribution notes must survive the round trip.

The brokers screen counts discards by reading the broker's name back out of a
sentence this module wrote. That coupling is deliberate but fragile in one
direction: if the wording and the parser ever disagree, nothing raises — the
count just quietly drops to zero. These tests are what makes that noisy.
"""

from __future__ import annotations

import pytest

from domain.attribution_notes import broker_name_in, missing_turn_note, quote_not_found_note

NAMES = [
    "Marcus Trent",
    "Patricia Nunez",
    # Apostrophes flip repr() to double quotes; the parser must follow.
    "Daniel O'Brien",
    'Anne "Annie" Fox',
    "Renée Dubois",
    "Dr. Elena Reyes",
]


@pytest.mark.parametrize("name", NAMES)
def test_a_missing_turn_note_names_its_broker(name: str) -> None:
    assert broker_name_in(missing_turn_note(name, 4)) == name


@pytest.mark.parametrize("name", NAMES)
def test_a_quote_note_names_its_broker(name: str) -> None:
    note = quote_not_found_note(name, 1, 'she said "no" — twice')
    assert broker_name_in(note) == name


def test_the_note_still_reads_as_a_sentence() -> None:
    # A person reading one call sees this text, so it has to explain itself.
    note = quote_not_found_note("Marcus Trent", 1, "I want to change my broker")
    assert note.startswith("Attribution to 'Marcus Trent' quotes text")
    assert "turn 1" in note


def test_an_unrecognised_note_yields_no_name_rather_than_raising() -> None:
    # Older or hand-edited rows must not break the scorecard.
    assert broker_name_in("Something written by an earlier version.") is None
    assert broker_name_in("") is None


def test_a_quote_containing_the_prefix_does_not_confuse_the_parser() -> None:
    # The quote is attacker-adjacent: it is model output echoed into the note.
    note = quote_not_found_note("Marcus Trent", 2, "Attribution to 'Someone Else' is wrong")
    assert broker_name_in(note) == "Marcus Trent"
