"""Storing and reloading an analysis against a real SQLite database."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from application.use_cases.analyze_transcript import AnalyzeTranscriptCommand
from domain.entities.analysis import CallAnalysis, Layer
from domain.entities.assist_event import AssistOutcome
from domain.errors import NotFoundError
from domain.taxonomy import Taxonomy
from domain.value_objects.resolution import Resolution
from domain.value_objects.score import ScoreStatus
from domain.value_objects.tier import Tier
from infrastructure.config.paths import DEFAULT_RUBRIC_PATH, DEFAULT_TAXONOMY_PATH
from infrastructure.config.rubric_loader import load_rubric
from infrastructure.config.taxonomy_loader import load_taxonomy
from infrastructure.persistence.engine import create_database_engine, create_session_factory
from infrastructure.persistence.models import Base
from infrastructure.persistence.repositories.analysis_repository import SqlAnalysisRepository
from tests.integration.test_analyze_transcript import CALL_89, build
from tests.support.analysis import ScriptedLayerProvider
from tests.support.settings import make_settings


@pytest.fixture
def taxonomy() -> Taxonomy:
    return load_taxonomy(DEFAULT_TAXONOMY_PATH)


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    subject = create_database_engine(
        make_settings(database_url=f"sqlite+aiosqlite:///{(tmp_path / 'calls.db').as_posix()}")
    )
    async with subject.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield subject
    await subject.dispose()


@pytest.fixture
async def analysis(taxonomy: Taxonomy) -> CallAnalysis:
    rubric = load_rubric(DEFAULT_RUBRIC_PATH, taxonomy)
    provider = ScriptedLayerProvider()
    use_case, _ = build(taxonomy, rubric, provider)
    stored = await use_case.execute(AnalyzeTranscriptCommand(transcript=CALL_89), provider)
    return stored.analysis


@pytest.fixture
def repository(engine: AsyncEngine, taxonomy: Taxonomy) -> SqlAnalysisRepository:
    return SqlAnalysisRepository(create_session_factory(engine), taxonomy)


class TestRoundTrip:
    async def test_an_analysis_survives_a_save_and_load(
        self, repository: SqlAnalysisRepository, analysis: CallAnalysis
    ) -> None:
        call_id = await repository.save(analysis)

        loaded = await repository.get(call_id)

        assert loaded is not None
        assert loaded.reference == analysis.reference
        assert loaded.title == analysis.title
        assert loaded.category.code == "coverage_benefits"
        assert loaded.resolution is Resolution.UNRESOLVED
        assert str(loaded.sentiment) == "WORRIED → DISMISSED"

    async def test_the_score_and_its_suspension_survive(
        self, repository: SqlAnalysisRepository, analysis: CallAnalysis
    ) -> None:
        call_id = await repository.save(analysis)

        loaded = await repository.get(call_id)

        assert loaded is not None
        assert loaded.score.score.value == 27
        assert loaded.score.status is ScoreStatus.PROVISIONAL
        assert loaded.score.tier is Tier.POOR
        assert loaded.score.messages == ("Score withheld pending clinical review.",)

    async def test_the_transcript_and_its_turn_indices_survive(
        self, repository: SqlAnalysisRepository, analysis: CallAnalysis
    ) -> None:
        # Evidence highlighting is driven by these indices; drifting them would
        # point every quote at the wrong line.
        call_id = await repository.save(analysis)

        loaded = await repository.get(call_id)

        assert loaded is not None
        assert loaded.transcript.turn_count == analysis.transcript.turn_count
        assert [turn.seq for turn in loaded.transcript.turns] == [
            turn.seq for turn in analysis.transcript.turns
        ]

    async def test_markers_survive_with_their_evidence(
        self, repository: SqlAnalysisRepository, analysis: CallAnalysis
    ) -> None:
        call_id = await repository.save(analysis)

        loaded = await repository.get(call_id)

        assert loaded is not None
        assert len(loaded.accepted_markers) == 6
        for marker in loaded.accepted_markers:
            turn = loaded.transcript.turn(marker.evidence_turn_seq)
            assert turn is not None
            assert turn.contains(marker.quote)

    async def test_findings_and_layers_survive(
        self, repository: SqlAnalysisRepository, analysis: CallAnalysis
    ) -> None:
        call_id = await repository.save(analysis)

        loaded = await repository.get(call_id)

        assert loaded is not None
        assert loaded.l4_signals[0].owner_name == "Compliance"
        assert loaded.assist_events[0].outcome is AssistOutcome.SHOULD_HAVE_FIRED
        assert len(loaded.assist_gaps) == 1
        assert {layer.layer for layer in loaded.layers} == set(Layer)

    async def test_provenance_survives(
        self, repository: SqlAnalysisRepository, analysis: CallAnalysis
    ) -> None:
        call_id = await repository.save(analysis)

        loaded = await repository.get(call_id)

        assert loaded is not None
        assert loaded.provenance.provider == "scripted"
        assert loaded.provenance.total_input_tokens == 500
        assert loaded.provenance.rubric_version == analysis.provenance.rubric_version


class TestLookup:
    async def test_an_unknown_id_returns_none(self, repository: SqlAnalysisRepository) -> None:
        assert await repository.get(4242) is None

    async def test_a_call_can_be_found_by_its_reference(
        self, repository: SqlAnalysisRepository, analysis: CallAnalysis
    ) -> None:
        await repository.save(analysis)

        found = await repository.get_by_reference(analysis.reference)

        assert found is not None
        assert found.title == analysis.title

    async def test_an_unknown_reference_returns_none(
        self, repository: SqlAnalysisRepository
    ) -> None:
        assert await repository.get_by_reference("C9999") is None


class TestReferences:
    async def test_references_are_sequential(
        self, repository: SqlAnalysisRepository, analysis: CallAnalysis
    ) -> None:
        assert await repository.next_reference() == "C0001"

        await repository.save(analysis)

        assert await repository.next_reference() == "C0002"


class TestTaxonomyDrift:
    async def test_a_stored_code_missing_from_the_taxonomy_fails_loudly(
        self, engine: AsyncEngine, analysis: CallAnalysis, taxonomy: Taxonomy
    ) -> None:
        # Editing the taxonomy without re-classifying is a real mistake. Reading
        # such a call must say so rather than render a mystery string.
        session_factory = create_session_factory(engine)
        await SqlAnalysisRepository(session_factory, taxonomy).save(analysis)

        narrowed = Taxonomy(
            categories=(taxonomy.category("pharmacy"),),
            l4_categories=taxonomy.l4_categories,
            signal_types=taxonomy.signal_types,
            sentiment_states=taxonomy.sentiment_states,
        )

        with pytest.raises(NotFoundError, match="Unknown call category"):
            await SqlAnalysisRepository(session_factory, narrowed).get(1)
