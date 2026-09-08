"""The corpus-document parser, against the shapes that have actually broken it.

Every case here is a real defect from a real corpus version, written as a test
so the next version cannot reintroduce it. The synthetic documents are built
from the text layer rather than from a PDF, because what breaks is the parsing
of extracted text and a fixture PDF would only add a dependency on pypdf to a
test about grammar.
"""

from __future__ import annotations

import pytest

from domain.errors import ValidationError
from infrastructure.corpus.pdf_document import extract_calls, format_transcript, render

# The v6 header, which is also the awkward one: a single time rather than a
# range, and a queue name after the handle time.
V6_CALL = """\
Call #1 — Enrollment Form Submitted Twice, Neither Processed
Tue 01 Sep 2026 · 08:52:00 · AHT 5m 31s · Platform & Forms
EMPLOYER | POOR · 36/100 | UNRESOLVED | NEUTRAL → FRUSTRATED | Agent: Tiffany
Context: Pacific Garden Supply · 29 employees · Owner Lucy Wong · GRP-388120
Topics: form submission · processing failure · no confirmation
Agent Tiffany: Choice Administrators, Tiffany speaking.
 Caller: Lucy Wong, group GRP-388120.
AI insights panel
L1 Understanding: an employer chasing a submission.
"""


def one(text: str):
    calls = extract_calls(text)
    assert len(calls) == 1
    return calls[0]


class TestV6Header:
    def test_reads_every_stated_field(self) -> None:
        call = one(V6_CALL)

        assert call.number == 1
        assert call.title == "Enrollment Form Submitted Twice, Neither Processed"
        assert call.caller == "EMPLOYER"
        assert call.tier == "POOR"
        assert call.score == 36
        assert call.resolution == "UNRESOLVED"
        assert call.agent == "Tiffany"
        assert call.queue == "Platform & Forms"
        assert call.handle_seconds == 331
        assert "Lucy Wong" in (call.context or "")
        assert "form submission" in (call.topics or "")

    def test_derives_the_end_time_the_document_stopped_stating(self) -> None:
        # v6 dropped the end time and kept handle time, so the end is
        # recoverable exactly. "When in the day did this sit" is answered from
        # the pair, and an absent end would silently drop the call out of the
        # hourly analysis.
        call = one(V6_CALL)

        assert call.start == "08:52:00"
        assert call.end == "08:57:31"

    def test_keeps_an_end_time_the_document_does_state(self) -> None:
        stated = V6_CALL.replace("08:52:00 · AHT", "08:52:00 – 09:00:00 · AHT")

        assert one(stated).end == "09:00:00"

    def test_reads_a_multi_word_resolution(self) -> None:
        # "PARTIALLY RESOLVED" is two words. A pattern matching \\w+ skips the
        # whole call rather than just that field.
        partial = V6_CALL.replace("| UNRESOLVED |", "| PARTIALLY RESOLVED |")

        assert one(partial).resolution == "PARTIALLY RESOLVED"

    def test_reads_a_churn_state_as_the_end_of_the_arc(self) -> None:
        churn = V6_CALL.replace("NEUTRAL → FRUSTRATED", "FRUSTRATED → CHURN RISK")
        call = one(churn)

        assert (call.start_mood, call.end_mood) == ("FRUSTRATED", "CHURN RISK")


class TestThingsThatWrap:
    def test_recovers_a_title_split_across_two_lines(self) -> None:
        # Three of v6's hundred titles wrap. The second line is not a field, so
        # it has to continue the title rather than be discarded.
        wrapped = V6_CALL.replace(
            "Call #1 — Enrollment Form Submitted Twice, Neither Processed\n",
            "Call #1 — Enrollment Form Submitted Twice, Neither\nProcessed\n",
        )

        assert one(wrapped).title == "Enrollment Form Submitted Twice, Neither Processed"

    def test_recovers_a_broker_signal_split_across_two_lines(self) -> None:
        wrapped = V6_CALL.replace(
            "Topics:",
            "BROKER SIGNAL — Anthony Salerno: Unresponsive to the group for three weeks\n"
            "on a billing correction.\nTopics:",
        )

        assert one(wrapped).broker == (
            "Anthony Salerno: Unresponsive to the group for three weeks "
            "on a billing correction."
        )

    def test_ignores_page_furniture_landing_inside_a_header(self) -> None:
        # The running head and a page number appear between a call's own lines
        # wherever a page breaks. Read as field values they corrupt whichever
        # field they interrupt.
        broken = V6_CALL.replace(
            "Context:",
            "Choice Administrators — Call Corpus v6\n11\nContext:",
        )
        call = one(broken)

        assert call.context is not None
        assert "Call Corpus" not in call.context
        assert "Pacific Garden Supply" in call.context


class TestBrokerNames:
    def test_gives_a_colonless_signal_the_colon_everything_downstream_needs(self) -> None:
        # Eighteen of v6's twenty-six are phrased this way. The name is read as
        # the text before the colon, so left alone the Brokers screen lists a
        # broker called "Marcus Trent named aloud by the caller" — and the same
        # person again, correctly, from the eight that do carry one.
        text = V6_CALL.replace(
            "Topics:", "BROKER SIGNAL — Marcus Trent named aloud by the caller\nTopics:"
        )

        assert one(text).broker == "Marcus Trent: named aloud by the caller"

    def test_leaves_a_signal_that_already_names_its_broker_alone(self) -> None:
        text = V6_CALL.replace(
            "Topics:", "BROKER SIGNAL — Denise Whitfield: Enrolled the wrong tier\nTopics:"
        )

        assert one(text).broker == "Denise Whitfield: Enrolled the wrong tier"

    def test_does_not_invent_a_name_out_of_a_sentence(self) -> None:
        # "Positive signal" is not a person. A leading capitalised run followed
        # by a lower-case word is the test, and this fails it at "signal".
        text = V6_CALL.replace(
            "Topics:", "BROKER SIGNAL — Positive signal, broker had it right\nTopics:"
        )

        assert one(text).broker == "Positive signal, broker had it right"


class TestRefusals:
    def test_refuses_a_document_with_no_calls_in_it(self) -> None:
        with pytest.raises(ValidationError, match="No call headings"):
            extract_calls("Choice Administrators — Call Corpus v6\nSome front matter.\n")

    def test_refuses_a_heading_that_yielded_no_transcript(self) -> None:
        # The failure this whole parser exists to prevent: a call that is
        # counted but empty, converted without complaint, analysed
        # successfully, and missing from the dashboard.
        header_only = V6_CALL.split("Agent Tiffany:")[0]

        with pytest.raises(ValidationError, match="no transcript"):
            extract_calls(header_only + "Call #2 — Another\n" + V6_CALL.split("\n", 1)[1])

    def test_refuses_two_calls_claiming_one_number(self) -> None:
        with pytest.raises(ValidationError, match="numbers two calls the same"):
            extract_calls(V6_CALL + V6_CALL)


class TestRendering:
    def test_writes_only_the_fields_the_document_stated(self) -> None:
        # An absent line is better than an invented one: the markdown parser
        # reads a missing field as "not stated", and a placeholder would be
        # indistinguishable from data.
        markdown = render(one(V6_CALL.replace(" · Platform & Forms", "")))

        assert "**Queue:**" not in markdown
        assert "**Agent:** Tiffany" in markdown

    def test_writes_the_bullets_the_corpus_parser_reads(self) -> None:
        markdown = render(one(V6_CALL))

        for expected in (
            "# Call #1 — Enrollment Form Submitted Twice, Neither Processed",
            "- **Agent:** Tiffany",
            "- **Caller:** EMPLOYER",
            "- **Score:** 36/100",
            "- **Sentiment Arc:** NEUTRAL → FRUSTRATED",
            "- **Date:** 2026-09-01",
            "- **AHT:** 5m 31s",
            "**Member context:**",
            "## Transcript",
            "## AI Insights Panel",
        ):
            assert expected in markdown

    def test_round_trips_through_the_corpus_parser(self) -> None:
        # The two parsers have to agree: this one writes the files that one
        # reads, and a field written in a shape it cannot read is a field lost
        # between them.
        from infrastructure.corpus.markdown_corpus import parse_corpus_file

        call = parse_corpus_file(render(one(V6_CALL)), "call_001")

        assert call.reference == "C0001"
        assert call.caller_type == "EMPLOYER"
        assert call.duration_seconds == 331
        assert call.ground_truth.score == 36
        assert call.ground_truth.agent_name == "Tiffany"
        assert call.started_at is not None
        assert call.ended_at is not None


class TestTranscriptFormatting:
    """The file has to be readable, not only parseable."""

    def test_rejoins_a_turn_the_pdf_wrapped_mid_sentence(self) -> None:
        wrapped = "Agent Tiffany: Can I take your name and\ngroup number?"

        assert format_transcript(wrapped) == (
            "Agent Tiffany: Can I take your name and group number?"
        )

    def test_separates_turns_by_a_blank_line(self) -> None:
        # A single newline is not a line break in markdown, so without this the
        # whole call renders as one paragraph with the agent and the member run
        # together — which is what a reader opening the file actually sees.
        formatted = format_transcript(
            "Agent Tiffany: Go ahead.\n Caller: I submitted it twice.\nAgent Tiffany: I see."
        )

        assert formatted == (
            "Agent Tiffany: Go ahead.\n\n"
            "Caller: I submitted it twice.\n\n"
            "Agent Tiffany: I see."
        )

    def test_leaves_the_turns_the_pipeline_reads_exactly_as_they_were(self) -> None:
        # Why this is safe to do at all: parse_transcript already joins wrapped
        # continuations with a single space, so formatting writes down what the
        # pipeline was computing anyway. Stored quotes are matched against that
        # text, so a change here would invalidate every stored offset.
        from domain.parsing import parse_transcript

        raw = (
            "Agent Tiffany: Can I take your name and\ngroup number?\n"
            " Caller: Lucy Wong, group GRP-388120."
        )

        before = [(turn.role, turn.text) for turn in parse_transcript(raw).turns]
        after = [(turn.role, turn.text) for turn in parse_transcript(format_transcript(raw)).turns]

        assert before == after
