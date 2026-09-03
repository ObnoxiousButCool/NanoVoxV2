"""Reading the authored corpus files.

The parser is the input side of DEC-01, so its failure modes matter as much as
its successes: a file it silently mis-reads becomes a model call spent on
nonsense, and a panel it invents becomes a fidelity comparison against fiction.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from domain.errors import ConfigurationError
from infrastructure.corpus.markdown_corpus import (
    MarkdownCorpusSource,
    parse_corpus_file,
    reference_for,
)

CALL_FILE = """# Call #89 — Member Describes Symptoms — Agent Fails to Recognise Urgency

- **Agent:** Brad
- **Tier:** POOR
- **Score:** 36/100
- **Sentiment Arc:** WORRIED → DISMISSED
- **Resolution:** UNRESOLVED
- **Duration:** ~6 min
- **Topics:** urgency cue missed, triage, patient safety

**Member context:** Constance Bell, 68, CalChoice HMO

## Transcript

Agent Brad: Choice Administrators, Brad.
Member: What is my emergency room copay?

## AI Insights Panel — NanoVox 5-Layer Output

L1 — Transcription: UNRECOGNISED CLINICAL EMERGENCY.
L3 — Agent Score: 36/100.
"""


# The timestamped corpus, converted by scripts/convert_corpus_pdf.py. It states
# four things the older files do not: handle time to the second, the date, the
# clock times, and which kind of caller rang.
TIMESTAMPED_FILE = """# Call #14 - Filing a Life Insurance Claim After a Spouse's Death

- **Agent:** Danielle
- **Caller:** MEMBER
- **Tier:** GOOD
- **Score:** 97/100
- **Sentiment Arc:** GRIEVING -> SUPPORTED
- **Resolution:** RESOLVED
- **Date:** 2026-09-07
- **Start:** 09:46:45
- **End:** 09:58:15
- **AHT:** 11m 30s
- **Duration:** ~12 min
- **Topics:** life insurance, beneficiary claim, bereavement

**Member context:** Harold Brennan, 71, Assurity Life via ChoiceBuilder

## Transcript

Agent Danielle: Choice Administrators, this is Danielle.
 Caller: My wife passed away three weeks ago. Member ID CB-6672290.

## AI Insights Panel - NanoVox 5-Layer Output

L1 - Transcription: Bereavement claim.
"""


def write(directory: Path, name: str, text: str) -> Path:
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


class TestOneFile:
    def test_the_transcript_is_taken_without_the_panel(self) -> None:
        # The authored panel is the answer key. Feeding it to the model would
        # make every fidelity figure meaningless.
        call = parse_corpus_file(CALL_FILE, "call_089")

        assert "Choice Administrators, Brad." in call.transcript
        assert "UNRECOGNISED CLINICAL EMERGENCY" not in call.transcript
        assert "Agent Score" not in call.transcript

    def test_the_call_number_becomes_a_stable_reference(self) -> None:
        call = parse_corpus_file(CALL_FILE, "call_089")

        assert call.reference == "C0089"
        assert call.sequence == 89
        assert call.source_id == "call_089"

    def test_the_title_survives_a_second_dash(self) -> None:
        call = parse_corpus_file(CALL_FILE, "call_089")

        assert call.title == "Member Describes Symptoms — Agent Fails to Recognise Urgency"

    def test_the_authored_panel_is_kept_apart_from_the_transcript(self) -> None:
        call = parse_corpus_file(CALL_FILE, "call_089")

        assert call.ground_truth is not None
        assert "UNRECOGNISED CLINICAL EMERGENCY" in call.ground_truth.panel_text

    def test_authored_figures_are_read(self) -> None:
        truth = parse_corpus_file(CALL_FILE, "call_089").ground_truth

        assert truth is not None
        assert truth.agent_name == "Brad"
        assert truth.tier == "POOR"
        assert truth.score == 36
        assert truth.resolution == "UNRESOLVED"
        assert truth.sentiment_start == "WORRIED"
        assert truth.sentiment_end == "DISMISSED"
        assert truth.topics == ("urgency cue missed", "triage", "patient safety")
        assert truth.member_context == "Constance Bell, 68, CalChoice HMO"

    def test_the_stated_duration_is_read(self) -> None:
        # It is in the header, so it never needs estimating from the words. The
        # model's estimate was landing on six round values across a hundred
        # calls, against the fifteen the corpus actually contains.
        call = parse_corpus_file(CALL_FILE, "call_089")

        assert call.duration_minutes == 6

    @pytest.mark.parametrize(
        ("stated", "expected"),
        [
            ("~11 min", 11),
            ("11 min", 11),
            ("11 minutes", 11),
            ("~4 mins", 4),
            # A zero is not a measurement. Absent, so it cannot drag a median
            # down or make a call look instantly resolved.
            ("0 min", None),
            ("unknown", None),
            ("", None),
        ],
    )
    def test_the_duration_is_read_however_it_is_written(
        self, stated: str, expected: int | None
    ) -> None:
        call = parse_corpus_file(
            CALL_FILE.replace("- **Duration:** ~6 min", f"- **Duration:** {stated}"), "call_089"
        )

        assert call.duration_minutes == expected

    def test_every_named_broker_is_kept(self) -> None:
        # Recall against these names is the measure most likely to catch a model
        # inventing an attribution, so dropping one would hide exactly that.
        text = CALL_FILE.replace(
            "- **Duration:** ~6 min",
            "- **Broker Signal:** Marcus Trent: never explained the referral rule\n"
            "- **Broker Signal:** Denise Whitfield: no renewal outreach",
        )

        truth = parse_corpus_file(text, "call_089").ground_truth

        assert truth is not None
        assert truth.broker_names == ("Marcus Trent", "Denise Whitfield")


class TestTimestampedCorpus:
    """The fields the timestamped corpus adds."""

    def test_the_handle_time_is_kept_to_the_second(self) -> None:
        # Rounding to whole minutes loses 30 seconds on a five-minute call,
        # which is a tenth of it.
        call = parse_corpus_file(TIMESTAMPED_FILE, "call_014")

        assert call.duration_seconds == 690
        assert call.duration_minutes == 12

    def test_the_start_and_end_become_moments(self) -> None:
        # Naive: the corpus states local wall-clock times, and the parser must
        # not invent a timezone the source never gave.
        call = parse_corpus_file(TIMESTAMPED_FILE, "call_014")

        assert call.started_at == datetime(2026, 9, 7, 9, 46, 45)  # noqa: DTZ001
        assert call.ended_at == datetime(2026, 9, 7, 9, 58, 15)  # noqa: DTZ001

    def test_the_caller_type_is_read(self) -> None:
        # An employer's HR director and a broker reach the same queue. Counting
        # either as a member would inflate every per-member figure.
        call = parse_corpus_file(TIMESTAMPED_FILE, "call_014")

        assert call.caller_type == "MEMBER"

    @pytest.mark.parametrize(
        ("stated", "expected"),
        [("11m 30s", 690), ("9m", 540), ("45s", 45), ("0m 0s", None), ("", None), ("soon", None)],
    )
    def test_handle_time_is_read_however_it_is_written(
        self, stated: str, expected: int | None
    ) -> None:
        call = parse_corpus_file(
            TIMESTAMPED_FILE.replace("- **AHT:** 11m 30s", f"- **AHT:** {stated}"), "call_014"
        )

        assert call.duration_seconds == expected

    def test_a_time_without_its_date_is_not_a_moment(self) -> None:
        # A midnight standing in for "unknown" would sort as a real call at the
        # start of the day and skew every time-of-day figure.
        call = parse_corpus_file(
            TIMESTAMPED_FILE.replace("- **Date:** 2026-09-07\n", ""), "call_014"
        )

        assert call.started_at is None
        assert call.ended_at is None

    def test_an_unreadable_date_is_absent_rather_than_guessed(self) -> None:
        call = parse_corpus_file(TIMESTAMPED_FILE.replace("2026-09-07", "07/09/2026"), "call_014")

        assert call.started_at is None

    def test_the_older_files_still_parse_without_these_fields(self) -> None:
        # The previous corpus states none of them. Absent, not zero: a caller
        # type guessed from the transcript would be invented data.
        call = parse_corpus_file(CALL_FILE, "call_089")

        assert call.duration_seconds is None
        assert call.started_at is None
        assert call.ended_at is None
        assert call.caller_type is None
        # ...while what it does state is still read.
        assert call.duration_minutes == 6


class TestMissingInformation:
    def test_a_file_with_no_transcript_is_rejected(self) -> None:
        # Unusable, and spending a model call on it would produce a confident
        # analysis of nothing.
        with pytest.raises(ConfigurationError, match="no transcript"):
            parse_corpus_file("# Call #4 — Something\n\nNo sections here.", "call_004")

    def test_an_empty_transcript_section_is_rejected(self) -> None:
        text = "# Call #4 — Something\n\n## Transcript\n\n## AI Insights Panel\n\nL1 — ...\n"

        with pytest.raises(ValueError, match="empty transcript"):
            parse_corpus_file(text, "call_004")

    def test_a_missing_panel_leaves_the_call_analysable(self) -> None:
        text = "# Call #4 — Something\n\n## Transcript\n\nAgent: Hello.\n"

        call = parse_corpus_file(text, "call_004")

        assert call.transcript == "Agent: Hello."
        assert call.ground_truth is not None
        assert call.ground_truth.is_empty

    def test_a_missing_field_is_absent_rather_than_guessed(self) -> None:
        text = "# Call #4 — Something\n\n- **Agent:** Ruth\n\n## Transcript\n\nAgent: Hello.\n"

        truth = parse_corpus_file(text, "call_004").ground_truth

        assert truth is not None
        assert truth.agent_name == "Ruth"
        assert truth.score is None
        assert truth.tier is None

    def test_a_file_with_no_duration_line_stays_analysable(self) -> None:
        # One missing figure, not a reason to fail a hundred-call run. The
        # analysis then falls back to the model's estimate.
        call = parse_corpus_file(CALL_FILE.replace("- **Duration:** ~6 min\n", ""), "call_089")

        assert call.duration_minutes is None
        assert call.transcript

    def test_an_unparseable_score_is_absent_rather_than_zero(self) -> None:
        # Zero is a POOR call. "Not stated" is not.
        text = CALL_FILE.replace("- **Score:** 36/100", "- **Score:** pending review")

        truth = parse_corpus_file(text, "call_089").ground_truth

        assert truth is not None
        assert truth.score is None

    def test_the_filename_carries_the_number_when_the_heading_does_not(self) -> None:
        text = "# Untitled\n\n## Transcript\n\nAgent: Hello.\n"

        call = parse_corpus_file(text, "call_012")

        assert call.reference == "C0012"

    def test_a_file_with_no_number_anywhere_is_rejected(self) -> None:
        with pytest.raises(ConfigurationError, match="no call number"):
            parse_corpus_file("# Untitled\n\n## Transcript\n\nAgent: Hello.\n", "notes")


class TestDirectory:
    def test_calls_come_back_in_corpus_order(self, tmp_path: Path) -> None:
        for number in (10, 2, 1):
            write(
                tmp_path,
                f"call_{number:03d}.md",
                f"# Call #{number} — Test\n\n## Transcript\n\nAgent: Hello.\n",
            )

        calls = MarkdownCorpusSource(tmp_path, "call_*.md").load()

        assert [call.sequence for call in calls] == [1, 2, 10]

    def test_files_outside_the_pattern_are_left_alone(self, tmp_path: Path) -> None:
        # A README beside the corpus must not be sent to a model.
        write(tmp_path, "call_001.md", "# Call #1 — Test\n\n## Transcript\n\nAgent: Hello.\n")
        write(tmp_path, "README.md", "Notes about the corpus.")

        calls = MarkdownCorpusSource(tmp_path, "call_*.md").load()

        assert len(calls) == 1

    def test_a_missing_directory_says_which_setting_is_wrong(self, tmp_path: Path) -> None:
        source = MarkdownCorpusSource(tmp_path / "nowhere", "call_*.md")

        with pytest.raises(ConfigurationError) as raised:
            source.load()

        # Naming the setting is the difference between a fixable error and a
        # confusing one.
        assert "CORPUS_PATH" in (raised.value.detail or "")

    def test_an_empty_directory_is_an_error_not_an_empty_run(self, tmp_path: Path) -> None:
        # A run that found nothing would otherwise report success having done
        # nothing at all.
        with pytest.raises(ConfigurationError, match="corpus is empty"):
            MarkdownCorpusSource(tmp_path, "call_*.md").load()

    def test_two_files_claiming_one_call_number_are_refused(self, tmp_path: Path) -> None:
        # Otherwise one of them is silently never analysed.
        body = "## Transcript\n\nAgent: Hello.\n"
        write(tmp_path, "call_007.md", f"# Call #7 — First\n\n{body}")
        write(tmp_path, "call_007b.md", f"# Call #7 — Second\n\n{body}")

        with pytest.raises(ConfigurationError, match="C0007"):
            MarkdownCorpusSource(tmp_path, "call_*.md").load()

    def test_the_location_is_reportable(self, tmp_path: Path) -> None:
        assert "call_*.md" in MarkdownCorpusSource(tmp_path, "call_*.md").describe()


def test_references_are_zero_padded_to_four_digits() -> None:
    assert reference_for(1) == "C0001"
    assert reference_for(100) == "C0100"
