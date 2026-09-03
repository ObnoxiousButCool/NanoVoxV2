"""Whether a quote shows a member naming their broker.

These records name real people and are reviewed by Compliance, so the cost of a
wrong one is borne by somebody who did nothing. The tests below are drawn from
what actually reached the broker scorecard: five surgeons, three provider
groups, two pharmacy partners, the plan itself, and three of the agents who
answered the calls.
"""

from __future__ import annotations

import pytest

from domain.broker_evidence import (
    compile_broker_terms,
    is_our_organisation,
    is_the_agent,
    quote_names_a_broker,
    quote_names_the_party,
)

TERMS = compile_broker_terms("broker,broker of record,BOR")


class TestAQuoteThatNamesABroker:
    @pytest.mark.parametrize(
        "quote",
        [
            "My broker, Anthony Salerno, signed me up for this plan.",
            "my broker — Denise Whitfield — told me about the deductible",
            "I want to change my broker.",
            "I've been trying to reach my broker, Patricia Nunez.",
            "Can I request a BOR change?",
        ],
    )
    def test_it_is_accepted(self, quote: str) -> None:
        assert quote_names_a_broker(quote, TERMS)


class TestAQuoteThatDoesNot:
    @pytest.mark.parametrize(
        ("who", "quote"),
        [
            ("a surgeon", "My surgeon Dr. Patel at Mercy Medical has scheduled it."),
            ("a doctor", "Dr. Reyes at Sutter — is she a good choice?"),
            ("a pharmacy", "the preferred specialty pharmacy partner"),
            ("a telehealth vendor", "Your plan has a preferred telehealth partner."),
            ("a provider group", "three claims from Summit Physical Therapy"),
            ("the plan itself", "Thank you for calling Choice Administrators."),
            ("an internal colleague", "I spoke with our claims corrections supervisor."),
            ("the agent greeting", "Choice Administrators, this is Carlos."),
        ],
    )
    def test_it_is_refused(self, who: str, quote: str) -> None:
        # Every one of these was a real attribution on the broker scorecard.
        assert not quote_names_a_broker(quote, TERMS), who

    def test_the_word_must_stand_alone(self) -> None:
        # "brokerage" is a business, not a member's broker; a substring match
        # would let a whole class of vendor names back in.
        assert not quote_names_a_broker("I called the brokerage firm downtown.", TERMS)


class TestTheConfiguredVocabulary:
    def test_another_plans_wording_is_configuration_not_a_release(self) -> None:
        other = compile_broker_terms("agent of record,producer")

        assert quote_names_a_broker("My producer set this up.", other)
        assert not quote_names_a_broker("My broker set this up.", other)

    def test_a_blank_vocabulary_disables_the_check_rather_than_refusing_everything(self) -> None:
        """Absent configuration must not silently empty the scorecard.

        Refusing every attribution would look identical to having no brokers,
        which is the failure mode hardest to notice.
        """
        assert compile_broker_terms("") is None
        assert quote_names_a_broker("anything at all", None)


class TestTheAgentOnTheCall:
    def test_the_agent_is_not_a_broker(self) -> None:
        assert is_the_agent("James", "James")

    def test_the_comparison_ignores_case_and_padding(self) -> None:
        assert is_the_agent("  sarah ", "Sarah")

    def test_a_different_person_is_not_the_agent(self) -> None:
        assert not is_the_agent("Marcus Trent", "Brad")

    def test_a_shared_first_name_does_not_make_someone_the_agent(self) -> None:
        # Two people called Sarah are two people. Matching on the first name
        # would discard a genuine attribution to prevent a rarer mistake.
        assert not is_the_agent("Sarah Whitfield", "Sarah")

    def test_an_unknown_agent_refuses_nothing(self) -> None:
        assert not is_the_agent("Marcus Trent", None)


class TestTheQuoteMustNameTheParty:
    """A quote saying only "your broker" is true of every group and names nobody.

    Both attributions in the timestamped corpus were of this shape: a quote
    containing the word "broker", filed against a name the quote never said.
    """

    @pytest.mark.parametrize(
        "quote",
        [
            "My broker, Anthony Salerno, signed me up for this plan.",
            "I've been trying to reach Salerno for a week.",
            "salerno never called me back",
        ],
    )
    def test_a_quote_containing_the_name_is_accepted(self, quote: str) -> None:
        assert quote_names_the_party(quote, "Anthony Salerno")

    @pytest.mark.parametrize(
        "quote",
        [
            "Talk to your broker about modelling both before the lock date.",
            "Your broker can run the contribution scenarios against your census.",
            "I want to change my broker.",
        ],
    )
    def test_a_quote_naming_no_one_is_refused(self, quote: str) -> None:
        assert not quote_names_the_party(quote, "Anthony Salerno")

    def test_one_distinctive_word_is_enough(self) -> None:
        # A member says "my broker is Rossi" about an agency filed under its
        # full trading name. Demanding the whole string would discard it.
        assert quote_names_the_party("my broker is Rossi", "Rossi Benefits Group")

    def test_a_generic_word_alone_does_not_name_the_agency(self) -> None:
        assert not quote_names_the_party("my broker handles the benefits", "Rossi Benefits Group")

    def test_a_wholly_generic_name_must_appear_in_full(self) -> None:
        # Nothing distinctive to look for, so "the group" in any quote must not
        # evidence an agency filed as "The Benefits Group".
        assert not quote_names_the_party("my broker at the group", "The Benefits Group")
        assert quote_names_the_party("my broker is the Benefits Group", "The Benefits Group")

    def test_punctuation_and_case_do_not_hide_the_name(self) -> None:
        assert quote_names_the_party('my broker — "Whitfield" — said so', "Denise Whitfield")

    def test_a_blank_name_is_never_evidenced(self) -> None:
        assert not quote_names_the_party("my broker told me", "")


class TestOurOwnOrganisation:
    def test_the_administrator_is_not_a_broker(self) -> None:
        assert is_our_organisation("Choice Administrators", "Choice Administrators")

    def test_a_suffix_picked_up_from_the_greeting_does_not_evade_it(self) -> None:
        assert is_our_organisation("Choice Administrators TPA", "Choice Administrators")

    def test_case_and_punctuation_do_not_evade_it(self) -> None:
        assert is_our_organisation("choice administrators.", "Choice Administrators")

    def test_a_real_broker_is_unaffected(self) -> None:
        assert not is_our_organisation("Rossi Benefits", "Choice Administrators")

    def test_a_partial_match_is_not_the_administrator(self) -> None:
        # An agency genuinely called "Choice" is a different party, and must not
        # be discarded because it shares a word with us.
        assert not is_our_organisation("Choice Insurance Group", "Choice Administrators")

    def test_a_blank_setting_disables_the_check(self) -> None:
        assert not is_our_organisation("Choice Administrators", "")
        assert not is_our_organisation("Choice Administrators", None)
