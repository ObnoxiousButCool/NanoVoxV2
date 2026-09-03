"""Recovering the member's name from the summary a call already carries."""

from __future__ import annotations

import pytest

from domain.member_name import find_member_name

# Built from its code point: as a literal it is hard to tell from a backtick.
CURLY = chr(0x2019)


class TestNamesThatAreFound:
    @pytest.mark.parametrize(
        ("context", "expected"),
        [
            ("Maria Gonzalez, a member needing prior authorization.", "Maria Gonzalez"),
            ("James Chen, a member inquiring about billing.", "James Chen"),
            # Real names carry punctuation. Both apostrophes appear, because the
            # text is model-written and inconsistent about them.
            (f"Siobhan O{CURLY}Brien, a member asking about claims.", f"Siobhan O{CURLY}Brien"),
            ("Siobhan O'Brien, a member asking about claims.", "Siobhan O'Brien"),
            ("Anne-Marie Smith-Jones, a member.", "Anne-Marie Smith-Jones"),
            ("Juan Carlos de Vega, a member.", "Juan Carlos de Vega"),
            ("  Priya Nair, a member.", "Priya Nair"),
            ("Robert  Jimenez, a member.", "Robert Jimenez"),
        ],
    )
    def test_a_leading_name_is_read(self, context: str, expected: str) -> None:
        assert find_member_name(context) == expected


class TestWhatIsDeliberatelyNotFound:
    @pytest.mark.parametrize(
        "context",
        [
            # A third of the shipped corpus is written this way. There is no
            # name in the text, so there is nothing to recover.
            "A member who was misinformed about dental coverage and is escalating.",
            "Member is in a hospital parking lot after being turned away.",
            "The caller is asking about a denied claim.",
            "A parent concerned about their child's high fever.",
            "This member has called three times.",
        ],
    )
    def test_a_description_yields_nothing(self, context: str) -> None:
        assert find_member_name(context) is None

    def test_a_name_later_in_the_sentence_is_not_taken(self) -> None:
        # The summaries also mention agents, doctors and employers. A general
        # name-finder would print one of those as the member, on a screen headed
        # "members at risk" — worse than showing no name at all.
        context = "A member complained that Dr. Alvarez, the provider, refused the referral."

        assert find_member_name(context) is None

    def test_a_sentence_without_a_comma_yields_nothing(self) -> None:
        assert find_member_name("Maria Gonzalez needed prior authorization") is None

    def test_a_long_capitalised_run_is_not_a_name(self) -> None:
        # Five capitalised words is a title or a sentence, not somebody's name.
        assert find_member_name("Prior Authorization Review Board Appeal, denied.") is None

    @pytest.mark.parametrize("context", ["", "   ", None])
    def test_nothing_to_read_is_not_an_error(self, context: str | None) -> None:
        assert find_member_name(context) is None
