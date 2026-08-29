"""Every dashboard figure, asserted against a fixture corpus.

This is the P4 exit criterion. The fixture in ``tests/support/corpus.py`` is
small enough that a reader can verify each expected number by hand from the
specs, which is the point: a dashboard test that recomputes the figure the same
way the code does proves nothing.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from itertools import pairwise
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from application.ports.read_models import CallFilters, CallSort
from application.use_cases.get_dashboard import (
    GetAgentPerformance,
    GetBrokerScorecard,
    GetOverview,
    GetSignalDistribution,
)
from domain.attribution_notes import quote_not_found_note
from domain.scoring.rubric import Rubric
from domain.taxonomy import Taxonomy
from domain.value_objects.resolution import Resolution
from domain.value_objects.severity import Severity
from domain.value_objects.tier import Tier
from infrastructure.config.dashboard_loader import DashboardConfig, load_dashboard_config
from infrastructure.config.paths import (
    DEFAULT_DASHBOARD_PATH,
    DEFAULT_RUBRIC_PATH,
    DEFAULT_TAXONOMY_PATH,
)
from infrastructure.config.rubric_loader import load_rubric
from infrastructure.config.taxonomy_loader import load_taxonomy
from infrastructure.persistence.engine import create_database_engine, create_session_factory
from infrastructure.persistence.models import Base
from infrastructure.persistence.repositories.analysis_repository import SqlAnalysisRepository
from infrastructure.persistence.repositories.read_models import SqlReadModelRepository
from infrastructure.persistence.tables import CallRow
from tests.support.corpus import (
    ESCALATED_COUNT,
    RESOLVED_COUNT,
    SCORES,
    TOTAL_CALLS,
    UNRESOLVED_COUNT,
    build_corpus,
)
from tests.support.settings import make_settings


@pytest.fixture(scope="module")
def taxonomy() -> Taxonomy:
    return load_taxonomy(DEFAULT_TAXONOMY_PATH)


@pytest.fixture(scope="module")
def rubric(taxonomy: Taxonomy) -> Rubric:
    return load_rubric(DEFAULT_RUBRIC_PATH, taxonomy)


@pytest.fixture(scope="module")
def dashboard_config() -> DashboardConfig:
    return load_dashboard_config(DEFAULT_DASHBOARD_PATH)


@pytest.fixture
async def session_factory(
    tmp_path: Path, taxonomy: Taxonomy
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine: AsyncEngine = create_database_engine(
        make_settings(database_url=f"sqlite+aiosqlite:///{(tmp_path / 'dash.db').as_posix()}")
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = create_session_factory(engine)
    repository = SqlAnalysisRepository(factory, taxonomy)
    for analysis in build_corpus(taxonomy):
        await repository.save(analysis)

    yield factory
    await engine.dispose()


@pytest.fixture
def read_models(session_factory: async_sessionmaker[AsyncSession]) -> SqlReadModelRepository:
    return SqlReadModelRepository(session_factory)


@pytest.fixture
def overview(
    read_models: SqlReadModelRepository, taxonomy: Taxonomy, dashboard_config: DashboardConfig
) -> GetOverview:
    return GetOverview(
        read_models, taxonomy, dashboard_config.histogram, dashboard_config.attention_rules
    )


class TestOverviewMetrics:
    async def test_total_calls(self, overview: GetOverview) -> None:
        assert (await overview.execute()).metrics.total_calls == TOTAL_CALLS

    async def test_median_and_mean_are_both_reported(self, overview: GetOverview) -> None:
        # Reporting one alone would hide the low cluster (plan §6.3).
        metrics = (await overview.execute()).metrics

        # Sorted: 25 30 40 50 55 [60] 70 88 90 95 96 -> median 60; mean 63.5
        assert metrics.median_score == 60
        assert metrics.mean_score == round(sum(SCORES) / len(SCORES), 1)
        assert metrics.median_score != metrics.mean_score

    async def test_first_contact_resolution_excludes_partial_resolutions(
        self, overview: GetOverview
    ) -> None:
        # 4 of 11 fully resolved = 36.4%. Counting the 2 partials would report
        # 54.5% and flatter the figure against the industry range beside it.
        metrics = (await overview.execute()).metrics

        assert metrics.first_contact_resolution_rate == round(RESOLVED_COUNT * 100 / TOTAL_CALLS, 1)
        assert metrics.first_contact_resolution_rate == 36.4

    async def test_escalation_and_unresolved_rates(self, overview: GetOverview) -> None:
        metrics = (await overview.execute()).metrics

        assert metrics.escalation_rate == round(ESCALATED_COUNT * 100 / TOTAL_CALLS, 1)
        assert metrics.unresolved_rate == round(UNRESOLVED_COUNT * 100 / TOTAL_CALLS, 1)

    async def test_broker_totals(self, overview: GetOverview) -> None:
        # Trent 3 signals + Nunez 2 = 5, across 2 brokers.
        metrics = (await overview.execute()).metrics

        assert metrics.broker_signal_count == 5
        assert metrics.distinct_broker_count == 2

    async def test_provisional_scores_are_counted(self, overview: GetOverview) -> None:
        assert (await overview.execute()).metrics.provisional_score_count == 1


class TestHistogram:
    async def test_every_call_lands_in_exactly_one_bin(self, overview: GetOverview) -> None:
        histogram = (await overview.execute()).histogram

        assert histogram.total == TOTAL_CALLS

    async def test_low_scores_are_marked_for_coaching(self, overview: GetOverview) -> None:
        # 25, 30, 40, 50, 55 are below the 60 threshold.
        histogram = (await overview.execute()).histogram

        assert histogram.below_threshold_count == 5

    async def test_bins_are_contiguous_and_cover_the_full_range(
        self, overview: GetOverview
    ) -> None:
        bins = (await overview.execute()).histogram.bins

        assert bins[0].lower == 0
        assert bins[-1].upper == 100
        for earlier, later in pairwise(bins):
            assert earlier.upper == later.lower


class TestCategories:
    async def test_every_configured_category_appears_even_with_no_calls(
        self, overview: GetOverview, taxonomy: Taxonomy
    ) -> None:
        # "Uncategorised shown honestly" — an absent bar would read as though the
        # category did not exist.
        categories = (await overview.execute()).categories

        assert len(categories) == len(taxonomy.categories)
        broker_attributed = next(item for item in categories if item.code == "broker_attributed")
        assert broker_attributed.count == 0

    async def test_counts_and_percentages(self, overview: GetOverview) -> None:
        categories = {item.code: item for item in (await overview.execute()).categories}

        assert categories["coverage_benefits"].count == 4
        assert categories["claims_eob"].count == 3
        assert categories["coverage_benefits"].percentage_of_total == round(4 * 100 / 11, 1)

    async def test_unresolved_is_tracked_per_category(self, overview: GetOverview) -> None:
        categories = {item.code: item for item in (await overview.execute()).categories}

        assert categories["coverage_benefits"].unresolved == 2


class TestAttentionQueue:
    async def test_the_clinical_risk_call_reaches_the_queue(self, overview: GetOverview) -> None:
        items = (await overview.execute()).attention

        clinical = next(item for item in items if item.rule_id == "clinical_risk_not_escalated")
        assert clinical.severity is Severity.CRITICAL
        assert clinical.count == 1
        assert clinical.owner == "Quality and Clinical"
        assert clinical.references == ("F0006",)

    async def test_the_queue_is_ranked_by_severity_then_volume(self, overview: GetOverview) -> None:
        items = (await overview.execute()).attention

        assert items[0].severity is Severity.CRITICAL
        ranks = [item.rank_key for item in items]
        assert ranks == sorted(ranks, reverse=True)

    async def test_a_broker_below_the_threshold_stays_off_the_queue(
        self, overview: GetOverview
    ) -> None:
        # Trent has 3 negatives and reaches it; Nunez has 0 and does not.
        items = (await overview.execute()).attention

        brokers = [item.subject for item in items if item.rule_id == "broker_conduct_pattern"]
        assert brokers == ["Marcus Trent"]

    async def test_narratives_are_filled_from_counts_not_written_by_a_model(
        self, overview: GetOverview
    ) -> None:
        items = (await overview.execute()).attention

        trent = next(item for item in items if item.subject == "Marcus Trent")
        assert "Marcus Trent in 3 calls" in trent.why

    async def test_every_item_names_an_owner(self, overview: GetOverview) -> None:
        # An item nobody owns will not get done.
        for item in (await overview.execute()).attention:
            assert item.owner


class TestAgentPerformance:
    @pytest.fixture
    def use_case(self, read_models: SqlReadModelRepository, rubric: Rubric) -> GetAgentPerformance:
        return GetAgentPerformance(read_models, rubric)

    async def test_aggregates_per_agent(self, use_case: GetAgentPerformance) -> None:
        agents = {row.agent_name: row for row in await use_case.execute()}

        sarah = agents["Sarah"]
        assert sarah.call_count == 5
        assert sarah.average_score == round((90 + 95 + 88 + 70 + 60) / 5, 1)
        assert sarah.min_score == 60
        assert sarah.max_score == 95
        assert sarah.escalated == 1
        assert sarah.unresolved == 0
        assert sarah.resolved == 3  # F0001, F0002, F0005
        assert sarah.partially_resolved == 1  # F0003

    async def test_the_four_outcomes_account_for_every_call(
        self, use_case: GetAgentPerformance
    ) -> None:
        # The bars are drawn as proportions; if these did not sum to the call
        # count the chart would silently under-report an outcome.
        for row in await use_case.execute():
            total = row.resolved + row.partially_resolved + row.escalated + row.unresolved
            assert total == row.call_count, row.agent_name

    async def test_unresolved_counts_are_attributed_correctly(
        self, use_case: GetAgentPerformance
    ) -> None:
        agents = {row.agent_name: row for row in await use_case.execute()}

        assert agents["Brad"].unresolved == 3
        assert agents["Brad"].average_score == 40.0

    async def test_an_agent_above_the_threshold_is_rated(
        self, use_case: GetAgentPerformance
    ) -> None:
        agents = {row.agent_name: row for row in await use_case.execute()}

        assert agents["Brad"].rating.is_rated
        assert agents["Brad"].rating.tier is Tier.POOR

    async def test_an_agent_below_the_threshold_is_shown_but_not_rated(
        self, use_case: GetAgentPerformance
    ) -> None:
        # Priya has one call and the best score in the corpus. Withholding the
        # tier must not be reserved for agents who look bad.
        agents = {row.agent_name: row for row in await use_case.execute()}

        priya = agents["Priya"]
        assert priya.call_count == 1
        assert priya.average_score == 96.0
        assert not priya.rating.is_rated
        assert priya.rating.tier is None
        assert priya.rating.note == "Below n=5 significance threshold"


class TestBrokerScorecard:
    @pytest.fixture
    def use_case(self, read_models: SqlReadModelRepository) -> GetBrokerScorecard:
        return GetBrokerScorecard(read_models)

    async def test_a_discarded_attribution_is_counted_but_not_scored(
        self,
        use_case: GetBrokerScorecard,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """The scorecard must admit what it is not showing.

        A rejected attribution never becomes a signal, so without this the
        broker's record silently under-reports and reads as complete.
        """
        async with session_factory() as session:
            call = await session.scalar(select(CallRow).limit(1))
            assert call is not None
            call.rejected_attribution_notes = [
                quote_not_found_note("Marcus Trent", 1, "words that were never said")
            ]
            await session.commit()

        brokers = {row.broker_name: row for row in await use_case.execute()}

        assert brokers["Marcus Trent"].discarded == 1
        # The count itself must be untouched: a discard is not a signal.
        assert brokers["Marcus Trent"].signals == 3
        assert brokers["Patricia Nunez"].discarded == 0

    async def test_signals_are_counted_per_broker(self, use_case: GetBrokerScorecard) -> None:
        brokers = {row.broker_name: row for row in await use_case.execute()}

        assert brokers["Marcus Trent"].signals == 3
        assert brokers["Marcus Trent"].negative == 3
        assert brokers["Marcus Trent"].positive == 0

    async def test_scoring_is_net_not_cumulative(self, use_case: GetBrokerScorecard) -> None:
        # A broker with positive signals is not a conduct case (plan §6.2).
        brokers = {row.broker_name: row for row in await use_case.execute()}

        assert brokers["Patricia Nunez"].positive == 2
        assert brokers["Patricia Nunez"].is_net_positive
        assert not brokers["Marcus Trent"].is_net_positive

    async def test_each_broker_links_to_the_calls_behind_the_signals(
        self, use_case: GetBrokerScorecard
    ) -> None:
        # Every signal must be traceable to the call that produced it.
        brokers = {row.broker_name: row for row in await use_case.execute()}

        assert brokers["Marcus Trent"].call_references == ("F0008", "F0009", "F0010")


class TestSignalDistribution:
    @pytest.fixture
    def use_case(
        self, read_models: SqlReadModelRepository, taxonomy: Taxonomy
    ) -> GetSignalDistribution:
        return GetSignalDistribution(read_models, taxonomy)

    async def test_l4_categories_count_calls_not_signals(
        self, use_case: GetSignalDistribution
    ) -> None:
        # F0008 raises two process_breakdown findings; it is one call with a
        # process problem, not two.
        entries, _ = await use_case.execute()
        by_code = {entry.code: entry for entry in entries}

        assert by_code["process_breakdown"].count == 3  # F0008, F0009, F0010

    async def test_a_category_with_no_signals_is_shown_with_zero(
        self, use_case: GetSignalDistribution
    ) -> None:
        # "Shown so the absence is visible rather than implied."
        entries, _ = await use_case.execute()
        by_code = {entry.code: entry for entry in entries}

        assert by_code["provider_performance"].count == 0
        assert by_code["provider_performance"].percentage_of_corpus == 0.0

    async def test_every_configured_category_is_returned(
        self, use_case: GetSignalDistribution, taxonomy: Taxonomy
    ) -> None:
        entries, _ = await use_case.execute()

        assert len(entries) == len(taxonomy.l4_categories)

    async def test_owners_carry_their_share(self, use_case: GetSignalDistribution) -> None:
        _, owners = await use_case.execute()
        by_owner = {load.owner: load.count for load in owners}

        assert by_owner["Operations"] == 3
        assert by_owner["Compliance"] == 2
        assert by_owner["Provider Relations"] == 0


class TestCallsList:
    async def test_calls_are_sorted_by_severity_not_date(
        self, read_models: SqlReadModelRepository
    ) -> None:
        # The withheld score outranks everything, then the lowest scores.
        page = await read_models.list_calls(CallFilters(), limit=5, offset=0)

        assert page.items[0].reference == "F0006"
        assert page.items[0].score_status == "provisional"
        # F0006 is items[0]; the rest follow by ascending score.
        assert [item.score for item in page.items[1:]] == [25, 40, 50, 55]

    async def test_the_total_reflects_the_filter_not_the_page(
        self, read_models: SqlReadModelRepository
    ) -> None:
        page = await read_models.list_calls(CallFilters(), limit=3, offset=0)

        assert len(page.items) == 3
        assert page.total == TOTAL_CALLS
        assert page.has_more

    async def test_filter_by_agent(self, read_models: SqlReadModelRepository) -> None:
        page = await read_models.list_calls(CallFilters(agent_name="Brad"), limit=50, offset=0)

        assert page.total == 5
        assert {item.agent_name for item in page.items} == {"Brad"}

    async def test_filter_by_resolution(self, read_models: SqlReadModelRepository) -> None:
        page = await read_models.list_calls(
            CallFilters(resolution=Resolution.UNRESOLVED.value), limit=50, offset=0
        )

        assert page.total == UNRESOLVED_COUNT

    async def test_filter_by_score_band(self, read_models: SqlReadModelRepository) -> None:
        page = await read_models.list_calls(CallFilters(max_score=59), limit=50, offset=0)

        assert page.total == 5
        assert all(item.score <= 59 for item in page.items)

    async def test_filter_by_signal(self, read_models: SqlReadModelRepository) -> None:
        page = await read_models.list_calls(
            CallFilters(signal_code="clinical_risk"), limit=50, offset=0
        )

        assert page.total == 1
        assert page.items[0].reference == "F0006"

    async def test_filter_by_broker_signal(self, read_models: SqlReadModelRepository) -> None:
        page = await read_models.list_calls(CallFilters(has_broker_signal=True), limit=50, offset=0)

        assert page.total == 5
        assert all(item.broker_names for item in page.items)

    async def test_excluding_broker_signals(self, read_models: SqlReadModelRepository) -> None:
        page = await read_models.list_calls(
            CallFilters(has_broker_signal=False), limit=50, offset=0
        )

        assert page.total == TOTAL_CALLS - 5

    async def test_sorting_by_reference(self, read_models: SqlReadModelRepository) -> None:
        page = await read_models.list_calls(
            CallFilters(), limit=50, offset=0, sort=CallSort.REFERENCE
        )

        references = [item.reference for item in page.items]
        assert references == sorted(references)

    async def test_sorting_descending_reverses_it(
        self, read_models: SqlReadModelRepository
    ) -> None:
        page = await read_models.list_calls(
            CallFilters(), limit=50, offset=0, sort=CallSort.REFERENCE, descending=True
        )

        references = [item.reference for item in page.items]
        assert references == sorted(references, reverse=True)

    async def test_sorting_by_score(self, read_models: SqlReadModelRepository) -> None:
        page = await read_models.list_calls(CallFilters(), limit=50, offset=0, sort=CallSort.SCORE)

        scores = [item.score for item in page.items]
        assert scores == sorted(scores)

    async def test_paging_never_repeats_or_drops_a_call(
        self, read_models: SqlReadModelRepository
    ) -> None:
        """The reason ordering ends with the call id.

        Rows tying on every sort column have no defined order between them, so
        without a unique final key a row can land on two pages while another
        lands on none. Sorting by resolution maximises the ties.
        """
        seen: list[str] = []
        for offset in range(0, TOTAL_CALLS, 4):
            page = await read_models.list_calls(
                CallFilters(), limit=4, offset=offset, sort=CallSort.RESOLUTION
            )
            seen.extend(item.reference for item in page.items)

        assert len(seen) == TOTAL_CALLS
        assert len(set(seen)) == TOTAL_CALLS

    async def test_calls_without_an_agent_sort_last_by_agent(
        self, read_models: SqlReadModelRepository
    ) -> None:
        # A block of dashes at the top is not what "sort by agent" means.
        page = await read_models.list_calls(CallFilters(), limit=50, offset=0, sort=CallSort.AGENT)

        named = [item.agent_name for item in page.items]
        assert named == sorted(named, key=lambda name: (name is None, name or ""))

    async def test_filter_by_broker_name(self, read_models: SqlReadModelRepository) -> None:
        # Marcus Trent is named on three calls; Patricia Nunez on the other two.
        page = await read_models.list_calls(
            CallFilters(broker_name="Marcus Trent"), limit=50, offset=0
        )

        assert page.total == 3
        assert all("Marcus Trent" in item.broker_names for item in page.items)

    async def test_an_unknown_broker_name_matches_nothing(
        self, read_models: SqlReadModelRepository
    ) -> None:
        # Not "every call": an unmatched filter must narrow to zero, not be ignored.
        page = await read_models.list_calls(
            CallFilters(broker_name="Nobody At All"), limit=50, offset=0
        )

        assert page.total == 0

    async def test_filters_combine(self, read_models: SqlReadModelRepository) -> None:
        page = await read_models.list_calls(
            CallFilters(agent_name="Brad", resolution=Resolution.UNRESOLVED.value),
            limit=50,
            offset=0,
        )

        assert page.total == 3

    async def test_search_matches_reference_and_title(
        self, read_models: SqlReadModelRepository
    ) -> None:
        page = await read_models.list_calls(CallFilters(search="F0011"), limit=50, offset=0)

        assert page.total == 1

    async def test_paging_walks_the_whole_set_without_repeats(
        self, read_models: SqlReadModelRepository
    ) -> None:
        seen: list[str] = []
        offset = 0
        while True:
            page = await read_models.list_calls(CallFilters(), limit=4, offset=offset)
            seen.extend(item.reference for item in page.items)
            if not page.has_more:
                break
            offset += page.limit

        assert len(seen) == TOTAL_CALLS
        assert len(set(seen)) == TOTAL_CALLS

    async def test_signals_and_brokers_travel_with_each_row(
        self, read_models: SqlReadModelRepository
    ) -> None:
        page = await read_models.list_calls(CallFilters(search="F0008"), limit=1, offset=0)

        row = page.items[0]
        assert row.signal_codes == ("compliance_disclosure_missing",)
        assert row.broker_names == ("Marcus Trent",)
