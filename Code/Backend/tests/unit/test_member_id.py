"""Recovering the member's identifier from what was said.

This column exists so that one member's calls can be seen as one member's calls.
Every test here defends that: a member spelled three ways is one member, and an
identifier attributed to the wrong person is worse than none, because a wrong
identifier does not look wrong.
"""

from __future__ import annotations

import pytest

from domain.entities.transcript import Transcript
from domain.entities.turn import Turn
from domain.member_id import compile_member_id_pattern, find_member_id
from domain.value_objects.speaker import SpeakerRole

PATTERN = compile_member_id_pattern(r"\bCHM[-\s]?\d{6,}\b")


def transcript(*turns: tuple[SpeakerRole, str]) -> Transcript:
    return Transcript(
        tuple(Turn(seq=index, role=role, text=text) for index, (role, text) in enumerate(turns))
    )


def member_said(text: str) -> Transcript:
    return transcript((SpeakerRole.AGENT, "Choice Administrators."), (SpeakerRole.MEMBER, text))


class TestFindingIt:
    def test_an_identifier_the_member_states_is_found(self) -> None:
        found = find_member_id(member_said("Hi, this is CHM-6672290 calling."), PATTERN)

        assert found == "CHM6672290"

    def test_it_is_found_mid_sentence(self) -> None:
        found = find_member_id(
            member_said("Hi. I want to change my broker. Member ID CHM-6672290. I've lost trust."),
            PATTERN,
        )

        assert found == "CHM6672290"

    def test_a_call_that_never_states_one_records_none(self) -> None:
        """A real call in the corpus: the agent asks, the member never answers.

        Absence is a fact about the call. Inventing an identifier would attach
        this call to a member who was never on it.
        """
        found = find_member_id(
            transcript(
                (SpeakerRole.AGENT, "Can I get your member ID? The number on your card."),
                (SpeakerRole.MEMBER, "I have paper from you. I don't understand."),
            ),
            PATTERN,
        )

        assert found is None


class TestOneMemberIsOneMember:
    @pytest.mark.parametrize(
        "spoken",
        ["CHM-6672290", "CHM 6672290", "chm6672290", "Member ID CHM-6672290.", "chm 6672290"],
    )
    def test_every_spelling_collapses_to_one_identifier(self, spoken: str) -> None:
        # Transcription is inconsistent. Three spellings of one member would read
        # as three members, and the repeat-contact count would be zero.
        assert find_member_id(member_said(spoken), PATTERN) == "CHM6672290"

    def test_two_members_stay_two_members(self) -> None:
        first = find_member_id(member_said("CHM-1111111"), PATTERN)
        second = find_member_id(member_said("CHM-2222222"), PATTERN)

        assert first != second


class TestWhoseIdentifierItIs:
    def test_the_members_own_words_win(self) -> None:
        """An agent handles many members a day; the member is on one call.

        When both state a number, the member's is the identifier of record — an
        agent reading back a wrong one must not reassign the call.
        """
        found = find_member_id(
            transcript(
                (SpeakerRole.AGENT, "I have CHM-9999999 on file."),
                (SpeakerRole.MEMBER, "That's not me — mine is CHM-1234567."),
            ),
            PATTERN,
        )

        assert found == "CHM1234567"

    def test_the_agent_is_used_when_the_member_gives_none(self) -> None:
        found = find_member_id(
            transcript(
                (SpeakerRole.AGENT, "I've pulled up CHM-1112223."),
                (SpeakerRole.MEMBER, "Yes, that's right."),
            ),
            PATTERN,
        )

        assert found == "CHM1112223"

    def test_the_first_of_several_is_taken_rather_than_guessing(self) -> None:
        # A call naming two identifiers is a genuine ambiguity. Choosing between
        # them would attribute one member's history to another.
        found = find_member_id(
            member_said("Mine is CHM-1111111, my wife's is CHM-2222222."), PATTERN
        )

        assert found == "CHM1111111"


class TestTheConfiguredPattern:
    def test_a_different_administrators_format_works(self) -> None:
        # The point of the pattern being configuration: another plan issues
        # another format, and that is not a code change.
        other = compile_member_id_pattern(r"\bMBR/\d{4}/[A-Z]{2}\b")

        assert find_member_id(member_said("It's MBR/2026/QX."), other) == "MBR2026QX"

    def test_a_capture_group_narrows_what_is_stored(self) -> None:
        # The pattern may match surrounding words while naming just the id.
        labelled = compile_member_id_pattern(r"member\s+id\s+(CHM\d{6,})")

        assert find_member_id(member_said("My member id CHM6672290 please."), labelled) == (
            "CHM6672290"
        )

    def test_matching_is_case_insensitive(self) -> None:
        assert find_member_id(member_said("chm-6672290"), PATTERN) == "CHM6672290"
