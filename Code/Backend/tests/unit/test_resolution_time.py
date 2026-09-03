"""How long it takes to resolve a member's problem."""

from __future__ import annotations

import pytest

from domain.aggregation.resolution_time import (
    DurationBandSettings,
    resolution_time,
)
from domain.errors import ValidationError

BANDS = DurationBandSettings(lower_bounds=(0, 10, 20))
LABELS = {"pharmacy": "Pharmacy", "claims": "Claims", "appeals": "Appeals"}


def summarise(durations: dict[str, tuple[int, ...]], total: int = 10) -> object:
    return resolution_time(durations, labels=LABELS, total_calls=total, settings=BANDS)


class TestBandSettings:
    def test_bands_must_start_at_zero(self) -> None:
        # Starting at 5 would silently drop every call shorter than five minutes.
        with pytest.raises(ValidationError, match="must start at 0"):
            DurationBandSettings(lower_bounds=(5, 10, 20))

    def test_bands_must_ascend(self) -> None:
        with pytest.raises(ValidationError, match="ascend"):
            DurationBandSettings(lower_bounds=(0, 20, 10))

    def test_one_bound_is_not_a_distribution(self) -> None:
        with pytest.raises(ValidationError, match="at least two"):
            DurationBandSettings(lower_bounds=(0,))


class TestBands:
    def test_bands_are_half_open_like_the_score_bins(self) -> None:
        # The boundary has to fall one way, and this matches the histogram: a
        # 10-minute call sits in 10-20, not in both. Getting it wrong here moves
        # a third of this corpus between bars.
        result = summarise({"pharmacy": (9, 10, 19, 20)})
        counts = {band.label: band.count for band in result.bands}

        assert counts == {"0-10": 1, "10-20": 2, "20+": 1}

    def test_the_last_band_is_open_ended(self) -> None:
        result = summarise({"pharmacy": (20, 45, 200)})
        last = result.bands[-1]

        assert (last.label, last.upper, last.count) == ("20+", None, 3)

    def test_an_empty_band_is_kept(self) -> None:
        # An absent bar reads as "this does not happen" rather than "this did
        # not happen here".
        result = summarise({"pharmacy": (5, 5)})

        assert [band.count for band in result.bands] == [2, 0, 0]
        assert len(result.bands) == 3


class TestCategories:
    def test_the_slowest_category_comes_first(self) -> None:
        result = summarise({"pharmacy": (5,), "claims": (30,)})

        assert [entry.label for entry in result.categories][:2] == ["Claims", "Pharmacy"]

    def test_a_category_that_has_resolved_nothing_is_still_listed(self) -> None:
        # The most interesting row on the chart is the work that never reaches a
        # resolution, so it must not be the row that disappears.
        result = summarise({"pharmacy": (10,)})
        by_code = {entry.code: entry for entry in result.categories}

        assert by_code["appeals"].resolved_calls == 0
        assert by_code["appeals"].median_minutes == 0.0
        assert by_code["appeals"].longest_minutes == 0

    def test_each_category_reports_its_own_median_and_worst_case(self) -> None:
        result = summarise({"claims": (10, 20, 60)})
        claims = next(entry for entry in result.categories if entry.code == "claims")

        assert (claims.resolved_calls, claims.median_minutes, claims.longest_minutes) == (
            3,
            20.0,
            60,
        )

    def test_a_category_outside_the_taxonomy_gets_no_row(self) -> None:
        # Only configured categories are listed, so a retired code cannot appear
        # on the chart under its raw database value.
        result = summarise({"retired_code": (10,)})

        assert {entry.code for entry in result.categories} == set(LABELS)

    def test_the_rows_need_not_sum_to_the_headline(self) -> None:
        # Deliberate, and pinned so nobody "fixes" it the wrong way round: the
        # headline counts every resolved call, while the rows cover configured
        # categories only. A call in a retired category is therefore in the
        # total and in no row. Dropping it from the total instead would
        # understate how much work the centre actually resolved; the Overview's
        # taxonomy-coverage figure is what tells a reader the gap exists.
        result = summarise({"pharmacy": (10,), "retired_code": (10,)})

        assert result.resolved_calls == 2
        assert sum(entry.resolved_calls for entry in result.categories) == 1

    def test_categories_with_equal_medians_fall_back_to_their_label(self) -> None:
        # Something has to order them, or the chart would reshuffle between
        # runs on the same data.
        result = summarise({})

        assert [entry.label for entry in result.categories] == ["Appeals", "Claims", "Pharmacy"]


class TestOverall:
    def test_the_median_is_taken_across_every_resolved_call(self) -> None:
        result = summarise({"pharmacy": (10,), "claims": (20, 30)})

        assert result.resolved_calls == 3
        assert result.median_minutes == 20.0
        assert result.longest_minutes == 30

    def test_the_total_is_carried_through_for_context(self) -> None:
        # Without it a reader cannot tell whether the median describes the whole
        # corpus or a third of it.
        result = summarise({"pharmacy": (10,)}, total=100)

        assert (result.resolved_calls, result.total_calls) == (1, 100)

    def test_nothing_resolved_reports_zeroes_rather_than_failing(self) -> None:
        result = summarise({}, total=40)

        assert result.resolved_calls == 0
        assert result.median_minutes == 0.0
        assert result.longest_minutes == 0
        # The bands are still drawn, all empty.
        assert [band.count for band in result.bands] == [0, 0, 0]
        assert len(result.categories) == len(LABELS)
