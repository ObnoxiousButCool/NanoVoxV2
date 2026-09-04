"""Whether members leave better off than they arrived.

The arc was stored on every call from the beginning and read by nothing. These
tests pin the two decisions that make it reportable: direction rather than
distance, and an unrecognised label counted rather than assumed flat.
"""

from __future__ import annotations

import pytest

from domain.aggregation.sentiment_movement import (
    ArcDirection,
    SentimentArc,
    band_of,
    direction_of,
    sentiment_movement,
    unknown_states,
)
from infrastructure.config.paths import DEFAULT_TAXONOMY_PATH
from infrastructure.config.taxonomy_loader import load_taxonomy


def arc(start: str | None, end: str | None) -> SentimentArc:
    return SentimentArc(start=start, end=end)


class TestDirection:
    @pytest.mark.parametrize(
        ("start", "end"),
        [
            ("WORRIED", "SATISFIED"),
            ("FRUSTRATED", "NEUTRAL"),
            ("CONFUSED", "INFORMED"),
            ("ANGRY", "FRUSTRATED"),
        ],
    )
    def test_moving_up_a_band_is_an_improvement(self, start: str, end: str) -> None:
        assert direction_of(arc(start, end)) is ArcDirection.IMPROVED

    @pytest.mark.parametrize(
        ("start", "end"),
        [
            ("NEUTRAL", "FRUSTRATED"),
            ("SATISFIED", "ANGRY"),
            ("CURIOUS", "DISMISSED"),
        ],
    )
    def test_moving_down_a_band_is_a_worsening(self, start: str, end: str) -> None:
        assert direction_of(arc(start, end)) is ArcDirection.WORSENED

    def test_moving_within_a_band_is_no_movement(self) -> None:
        # CURIOUS and NEUTRAL are two words for the same place. Counting that as
        # an improvement would inflate the figure with vocabulary.
        assert direction_of(arc("CURIOUS", "NEUTRAL")) is ArcDirection.UNCHANGED

    def test_the_same_state_is_no_movement(self) -> None:
        assert direction_of(arc("WORRIED", "WORRIED")) is ArcDirection.UNCHANGED

    def test_case_and_padding_do_not_decide_the_band(self) -> None:
        assert band_of("  satisfied ") == band_of("SATISFIED")


class TestWhatIsNotRecognised:
    @pytest.mark.parametrize(
        ("start", "end"),
        [
            ("WORRIED", "EUPHORIC"),
            ("EUPHORIC", "SATISFIED"),
            (None, "SATISFIED"),
            ("WORRIED", None),
        ],
    )
    def test_an_unknown_or_missing_state_is_unclassified(
        self, start: str | None, end: str | None
    ) -> None:
        assert direction_of(arc(start, end)) is ArcDirection.UNCLASSIFIED

    def test_it_is_counted_rather_than_folded_into_unchanged(self) -> None:
        # Folding it in would make a vocabulary that outgrew this module look
        # like a run of calls that did not move anybody.
        result = sentiment_movement([arc("WORRIED", "EUPHORIC"), arc("WORRIED", "WORRIED")])

        assert result.unclassified == 1
        assert result.unchanged == 1

    def test_the_rate_is_measured_over_what_could_be_classified(self) -> None:
        # Otherwise a label falling out of the vocabulary reads as satisfaction
        # falling, which is a different and much more alarming thing.
        result = sentiment_movement(
            [
                arc("WORRIED", "SATISFIED"),
                arc("WORRIED", "SATISFIED"),
                arc("WORRIED", "EUPHORIC"),
                arc("WORRIED", "EUPHORIC"),
            ]
        )

        assert result.classified == 2
        assert result.improved_rate == 100.0

    def test_nothing_classified_is_zero_rather_than_a_division_error(self) -> None:
        result = sentiment_movement([arc("EUPHORIC", "EUPHORIC")])

        assert result.classified == 0
        assert result.improved_rate == 0.0


class TestCounting:
    def test_a_body_of_calls_is_split_three_ways(self) -> None:
        result = sentiment_movement(
            [
                arc("WORRIED", "SATISFIED"),
                arc("CONFUSED", "SATISFIED"),
                arc("NEUTRAL", "CURIOUS"),
                arc("SATISFIED", "FRUSTRATED"),
            ]
        )

        assert (result.improved, result.unchanged, result.worsened) == (2, 1, 1)
        assert result.improved_rate == 50.0

    def test_no_calls_is_not_an_error(self) -> None:
        result = sentiment_movement([])

        assert result.classified == 0
        assert result.improved_rate == 0.0


def test_every_configured_sentiment_has_a_band() -> None:
    """A state added to the taxonomy and not here would silently go unread.

    The failure would be invisible: calls carrying the new label would simply
    stop being counted, and the improvement rate would keep reporting a number.
    """
    taxonomy = load_taxonomy(DEFAULT_TAXONOMY_PATH)

    assert unknown_states(list(taxonomy.sentiment_states)) == ()
