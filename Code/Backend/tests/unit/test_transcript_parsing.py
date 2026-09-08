"""Parsing pasted text into turns — the step every quote later depends on."""

from __future__ import annotations

import pytest

from domain.errors import ValidationError
from domain.parsing import count_turns, parse_transcript
from domain.value_objects.speaker import SpeakerRole

CORPUS_EXTRACT = """Agent Brad: Choice Administrators, Brad.
Member: Hello. I wanted to ask what my emergency room copay is. Member ID CHM-2208814.
Agent Brad: ER copay is $250, waived if you're admitted.
"""


class TestSpeakerRoles:
    def test_a_named_agent_is_recognised_and_named(self) -> None:
        transcript = parse_transcript("Agent Sarah: Thank you for calling.")

        assert transcript.turns[0].role is SpeakerRole.AGENT
        assert transcript.turns[0].speaker_name == "Sarah"

    def test_the_member_is_recognised(self) -> None:
        transcript = parse_transcript("Member: I have a question.")

        assert transcript.turns[0].role is SpeakerRole.MEMBER
        assert transcript.turns[0].speaker_name is None

    @pytest.mark.parametrize("word", ["Member", "Caller", "Customer", "Patient"])
    def test_member_synonyms_are_recognised(self, word: str) -> None:
        assert parse_transcript(f"{word}: Hello.").turns[0].role is SpeakerRole.MEMBER

    @pytest.mark.parametrize("word", ["System", "IVR", "Hold", "Recording"])
    def test_system_lines_are_not_attributed_to_a_participant(self, word: str) -> None:
        # A hold message scored as the agent's words would be nonsense.
        assert parse_transcript(f"{word}: Please hold.").turns[0].role is SpeakerRole.SYSTEM

    def test_a_bare_name_is_treated_as_the_agent(self) -> None:
        # The corpus names only the agent and writes the member as "Member";
        # guessing the other way would attribute member words to the agent's score.
        transcript = parse_transcript("Nicole: Choice Administrators.")

        assert transcript.turns[0].role is SpeakerRole.AGENT
        assert transcript.turns[0].speaker_name == "Nicole"

    def test_a_bare_agent_prefix_has_no_name(self) -> None:
        transcript = parse_transcript("Agent: How can I help?")

        assert transcript.turns[0].role is SpeakerRole.AGENT
        assert transcript.turns[0].speaker_name is None

    def test_role_matching_ignores_case(self) -> None:
        assert parse_transcript("MEMBER: Hi.").turns[0].role is SpeakerRole.MEMBER


class TestWrappedLines:
    def test_a_continuation_line_joins_the_turn_above(self) -> None:
        # The corpus transcripts are hard-wrapped mid-sentence. Treating each
        # line as a turn would shred them, and a quote spanning the wrap would
        # then never validate against any single turn.
        transcript = parse_transcript(
            "Member: I've had this pressure in my chest since last night\n"
            "and my daughter thinks I should go in."
        )

        assert transcript.turn_count == 1
        assert "since last night and my daughter" in transcript.turns[0].text

    def test_a_wrapped_quote_validates_against_the_joined_turn(self) -> None:
        transcript = parse_transcript(
            "Member: I've had this pressure\nin my chest since last night."
        )

        assert transcript.turns[0].contains("pressure in my chest")

    def test_blank_lines_are_ignored(self) -> None:
        assert parse_transcript("Agent: One.\n\n\nMember: Two.").turn_count == 2


class TestSequencing:
    def test_turns_are_numbered_from_zero_and_contiguous(self) -> None:
        transcript = parse_transcript(CORPUS_EXTRACT)

        assert [turn.seq for turn in transcript.turns] == [0, 1, 2]

    def test_an_empty_turn_does_not_leave_a_gap_in_the_numbering(self) -> None:
        # A prefix with nothing after it carries no evidence; keeping it would
        # shift every later index and break every quote citation.
        transcript = parse_transcript("Agent: One.\nMember:\nAgent: Three.")

        assert [turn.seq for turn in transcript.turns] == [0, 1]
        assert transcript.turns[1].text == "Three."


class TestRejection:
    def test_text_with_no_prefixes_is_rejected_with_guidance(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            parse_transcript("Just a wall of text with no speaker prefixes at all.")

        assert exc_info.value.detail is not None
        assert "Agent Sarah:" in exc_info.value.detail

    def test_empty_input_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="empty"):
            parse_transcript("   \n  ")

    def test_a_long_sentence_containing_a_colon_is_not_a_speaker(self) -> None:
        # The prefix is length-bounded so prose does not masquerade as a turn.
        long_line = "Agent: " + "and then I explained the whole policy in detail: it was long."
        transcript = parse_transcript(long_line)

        assert transcript.turn_count == 1


class TestCounting:
    def test_counts_turns_for_the_live_indicator(self) -> None:
        assert count_turns(CORPUS_EXTRACT) == 3

    def test_unparseable_text_counts_zero_rather_than_raising(self) -> None:
        # Drives a UI counter on every keystroke; it must never throw.
        assert count_turns("no prefixes here") == 0


class TestLabelsInsideALine:
    """A transcript pasted with its line breaks stripped.

    Copying out of a document or a chat window flattens the newlines, and the
    line-based rule then finds one prefix and attributes the whole conversation
    to whoever spoke first. Every corpus transcript recovers identically —
    turns, roles and text — when flattened this way.
    """

    def test_a_flattened_conversation_recovers_its_turns(self) -> None:
        flat = (
            "Agent Sarah: Thank you for calling. Caller: Why do I owe $340? "
            "Agent Sarah: Let me check."
        )

        transcript = parse_transcript(flat)

        assert transcript.turn_count == 3
        assert [turn.role for turn in transcript.turns] == [
            SpeakerRole.AGENT,
            SpeakerRole.MEMBER,
            SpeakerRole.AGENT,
        ]

    def test_the_full_stop_stays_on_the_turn_it_ended(self) -> None:
        # The boundary belongs to the sentence that closed, not to the one
        # opening. A quote validated against "Thank you" must still find it.
        transcript = parse_transcript("Agent Sarah: Thank you. Caller: Why?")

        assert [turn.text for turn in transcript.turns] == ["Thank you.", "Why?"]

    def test_a_label_recovers_after_a_question_or_a_quote(self) -> None:
        assert parse_transcript("Agent Sarah: Can I help? Caller: Yes.").turn_count == 2
        assert parse_transcript('Agent Sarah: She said "call back." Caller: I did.').turn_count == 2

    def test_a_colon_inside_speech_does_not_open_a_turn(self) -> None:
        # Five of the corpus's 758 turns contain one of these. None of them is
        # a speaker, and reading one as a speaker would split a sentence in two.
        for speech in (
            "And one thing worth knowing: the dentist cannot change it.",
            "Three things: the date, the code, and the amount.",
            "Please note: your deductible resets in January.",
        ):
            assert parse_transcript(f"Agent Brad: {speech}").turn_count == 1

    def test_a_role_word_mid_sentence_does_not_open_a_turn(self) -> None:
        # The reason an inline label has to follow a closed sentence.
        transcript = parse_transcript("Agent Brad: I told the member: it was already paid.")

        assert transcript.turn_count == 1
        assert transcript.turns[0].role is SpeakerRole.AGENT

    def test_a_time_is_not_a_speaker(self) -> None:
        assert parse_transcript("Caller: I called at 3:30 and nobody answered.").turn_count == 1

    def test_a_bare_name_is_not_trusted_mid_line(self) -> None:
        # Deliberate asymmetry. At the start of a line a bare name is a speaker,
        # because somebody put it there; mid-line it is far more likely to be
        # prose, and guessing wrong splits a sentence and misattributes it.
        assert parse_transcript("Brad: Hello there.").turn_count == 1
        assert parse_transcript("Agent Brad: Hello. Sarah: Hi.").turn_count == 1


class TestAWrappedLineIsNotASpeaker:
    def test_a_continuation_carrying_an_early_colon_joins_the_turn_above(self) -> None:
        # Line 6 of call_017 in the shipped corpus. Before the label had to look
        # like a label, this produced a turn spoken by an agent named "new
        # enrollments effective the 1st".
        text = (
            "Agent Sarah: We processed four\n"
            "new enrollments effective the 1st: two dental only, two dental and vision."
        )

        transcript = parse_transcript(text)

        assert transcript.turn_count == 1
        assert transcript.turns[0].speaker_name == "Sarah"
        assert "new enrollments" in transcript.turns[0].text
