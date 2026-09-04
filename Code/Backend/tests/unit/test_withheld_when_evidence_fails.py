"""A score with no surviving evidence behind it is not a confirmed score.

The failure this guards against is silent and flattering. When a transcript does
not parse into turns, every marker the model raised cites a turn that is not
there, all of them are refused, and the arithmetic runs over an empty list — so
no penalty is applied and the base score comes through untouched. The call then
reads as the best on the dashboard on the strength of nothing at all.

Observed on a real pair: the same conversation scored 90 from the corpus and 100
pasted, because the paste arrived on one line and its five markers all pointed
at turns 1, 5, 8, 9 and 10 of a one-turn transcript.

The parser recovers that particular paste now, but this rule is the backstop
rather than the fix. Evidence can fail to locate for reasons parsing cannot
reach — a transcript labelled with bare names and pasted flat, a model citing
an index it invented — and the score must not read as settled in any of them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.entities.score_marker import ScoreMarker
from domain.parsing import parse_transcript
from domain.scoring.marker_validation import MarkerValidator
from domain.scoring.rubric_engine import RubricEngine
from domain.value_objects.polarity import Polarity
from domain.value_objects.score import ScoreStatus
from infrastructure.config.rubric_loader import load_rubric

# Bare names on one line: the shape the parser deliberately does not split,
# because mid-line it will only trust a recognised role. Two turns are found —
# the opening label and nothing after it — so an index past them has nothing to
# point at, which is the condition this rule exists for.
FLATTENED = "Sarah: Thank you for calling. Why do I owe $340? Let me check that for you."


@pytest.fixture
def rubric():
    return load_rubric(Path("config/rubric.yaml"))


@pytest.fixture
def engine(rubric):
    return RubricEngine(rubric)


def _marker(dimension: str, turn: int) -> ScoreMarker:
    return ScoreMarker(
        polarity=Polarity.NEGATIVE,
        dimension=dimension,
        description="Did not confirm the member understood.",
        evidence_turn_seq=turn,
        quote="unlocatable",
    )


class TestEvidenceAllRejected:
    def test_a_bare_name_paste_still_collapses(self) -> None:
        # The cause, stated as a test so the rest of the file has a reason. A
        # recognised role mid-line is recovered; a bare name is not, so this
        # remains reachable and the rule below remains necessary.
        assert parse_transcript(FLATTENED).turn_count == 1

    def test_markers_citing_absent_turns_are_all_refused(self, rubric) -> None:
        transcript = parse_transcript(FLATTENED)
        dimension = next(iter(rubric.dimensions))

        validation = MarkerValidator(rubric, transcript).validate(
            [_marker(dimension, turn) for turn in (1, 5, 8, 9, 10)]
        )

        assert validation.accepted == ()
        assert len(validation.rejected) == 5
        assert validation.evidence_all_rejected

    def test_the_score_is_withheld_rather_than_confirmed(self, rubric, engine) -> None:
        transcript = parse_transcript(FLATTENED)
        dimension = next(iter(rubric.dimensions))
        validation = MarkerValidator(rubric, transcript).validate(
            [_marker(dimension, turn) for turn in (1, 5, 8, 9, 10)]
        )

        result = engine.score(
            validation.accepted, evidence_all_rejected=validation.evidence_all_rejected
        )

        # The number is still the base — nothing was deducted because nothing
        # survived — but it is no longer presented as settled.
        assert result.score.value == rubric.base_score
        assert result.status is ScoreStatus.PROVISIONAL

    def test_a_quiet_call_is_still_confirmed(self, rubric, engine) -> None:
        # Nothing proposed is not the same as nothing surviving. A call the model
        # read and had no criticism of is a real result, and withholding it would
        # make the withheld count meaningless.
        transcript = parse_transcript(FLATTENED)
        validation = MarkerValidator(rubric, transcript).validate([])

        assert not validation.evidence_all_rejected
        result = engine.score(
            validation.accepted, evidence_all_rejected=validation.evidence_all_rejected
        )
        assert result.status is ScoreStatus.CONFIRMED

    def test_one_surviving_marker_is_enough_to_confirm(self, rubric, engine) -> None:
        # Partial rejection already had a home: the notes record it and the
        # score stands on what was left.
        transcript = parse_transcript(FLATTENED)
        dimension = next(iter(rubric.dimensions))
        markers = [
            ScoreMarker(
                polarity=Polarity.NEGATIVE,
                dimension=dimension,
                description="Opened without identifying the plan.",
                evidence_turn_seq=0,
                quote="Thank you for calling",
            ),
            _marker(dimension, 7),
        ]

        validation = MarkerValidator(rubric, transcript).validate(markers)

        assert len(validation.accepted) == 1
        assert not validation.evidence_all_rejected
        result = engine.score(
            validation.accepted, evidence_all_rejected=validation.evidence_all_rejected
        )
        assert result.status is ScoreStatus.CONFIRMED
        assert result.score.value < rubric.base_score
