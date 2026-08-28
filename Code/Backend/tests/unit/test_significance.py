"""Agents below the sample threshold are shown, but not tier-rated."""

from __future__ import annotations

import pytest

from domain.aggregation.significance import is_tier_rated, rate_agent
from domain.errors import ValidationError
from domain.value_objects.score import Score
from domain.value_objects.tier import Tier, TierThresholds

THRESHOLDS = TierThresholds(good=86, average=60)
MINIMUM = 5


@pytest.mark.parametrize(("calls", "expected"), [(0, False), (4, False), (5, True), (17, True)])
def test_significance_threshold_is_inclusive(calls: int, expected: bool) -> None:
    assert is_tier_rated(calls, MINIMUM) is expected


def test_an_unusable_threshold_is_rejected() -> None:
    with pytest.raises(ValidationError, match="at least 1"):
        is_tier_rated(10, 0)


def test_an_agent_with_enough_calls_is_rated() -> None:
    # Sarah: 17 calls, average 94.2.
    rating = rate_agent(
        average_score=Score(94), call_count=17, minimum=MINIMUM, thresholds=THRESHOLDS
    )

    assert rating.is_rated
    assert rating.tier is Tier.GOOD
    assert rating.note is None


def test_an_agent_below_the_threshold_is_not_rated_even_when_scoring_badly() -> None:
    # Kayla: 4 calls, average 40.2. The score is poor, but four calls is not
    # enough evidence to label a person — the volume is shown, the tier is not.
    rating = rate_agent(
        average_score=Score(40), call_count=4, minimum=MINIMUM, thresholds=THRESHOLDS
    )

    assert not rating.is_rated
    assert rating.tier is None
    assert rating.note == "Below n=5 significance threshold"


def test_the_rule_applies_equally_to_a_high_scoring_small_sample() -> None:
    # Priya: 2 calls, average 94.5. Withholding the tier must not be reserved
    # for agents who look bad.
    rating = rate_agent(
        average_score=Score(95), call_count=2, minimum=MINIMUM, thresholds=THRESHOLDS
    )

    assert not rating.is_rated
