"""POST /api/v1/analyses — the contract the Analyze and Call detail screens use."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.dto.analysis_schemas import build_analysis_schemas
from application.ports.redaction import NoRedaction
from application.use_cases.analyze_transcript import AnalyzeTranscript
from domain.errors import ProviderUnavailableError
from frameworks_drivers.api.dependencies import get_analyze_transcript_use_case
from frameworks_drivers.container import Container
from infrastructure.config.paths import DEFAULT_RUBRIC_PATH, DEFAULT_TAXONOMY_PATH
from infrastructure.config.rubric_loader import load_rubric
from infrastructure.config.taxonomy_loader import load_taxonomy
from tests.integration.test_analyze_transcript import CALL_89
from tests.support.analysis import (
    InMemoryAnalysisRepository,
    ScriptedLayerProvider,
    StubPromptSource,
)
from tests.support.clock import FixedClock

ANALYSES_URL = "/api/v1/analyses"


@pytest.fixture
def scripted(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> Iterator[ScriptedLayerProvider]:
    """Wire the endpoint to a scripted provider and an in-memory store."""
    taxonomy = load_taxonomy(DEFAULT_TAXONOMY_PATH)
    rubric = load_rubric(DEFAULT_RUBRIC_PATH, taxonomy)
    provider = ScriptedLayerProvider()

    app.dependency_overrides[get_analyze_transcript_use_case] = lambda: AnalyzeTranscript(
        prompts=StubPromptSource(),
        schemas=build_analysis_schemas(taxonomy, rubric),
        taxonomy=taxonomy,
        rubric=rubric,
        redaction=NoRedaction(),
        repository=InMemoryAnalysisRepository(),
        clock=FixedClock(),
    )
    monkeypatch.setattr(Container, "create_provider", lambda *_args, **_kwargs: provider)
    yield provider


def post(client: TestClient, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"transcript": CALL_89}
    payload.update(overrides)
    response = client.post(ANALYSES_URL, json=payload)
    assert response.status_code == 201, response.text
    return dict(response.json())


class TestSuccessfulAnalysis:
    def test_the_response_carries_the_whole_analysis(
        self, app: FastAPI, scripted: ScriptedLayerProvider
    ) -> None:
        with TestClient(app) as client:
            body = post(client)

        assert body["title"] == "ER copay question that was a cardiac presentation"
        assert body["category"] == "coverage_benefits"
        assert body["category_label"] == "Coverage & Benefits"
        assert body["resolution"] == "UNRESOLVED"
        assert len(body["layers"]) == 5

    def test_the_score_is_reported_as_provisional_with_its_reason(
        self, app: FastAPI, scripted: ScriptedLayerProvider
    ) -> None:
        with TestClient(app) as client:
            body = post(client)

        score = body["score"]
        assert score["value"] == 27
        assert score["status"] == "provisional"
        assert score["tier"] == "POOR"
        assert score["gate_messages"] == ["Score withheld pending clinical review."]

    def test_evidence_travels_with_every_marker(
        self, app: FastAPI, scripted: ScriptedLayerProvider
    ) -> None:
        # The UI highlights transcript text from these indices rather than
        # searching for the quote in the browser.
        with TestClient(app) as client:
            body = post(client)

        turns = {turn["seq"]: turn["text"] for turn in body["transcript"]}
        assert body["markers"]
        for marker in body["markers"]:
            assert marker["quote"]
            assert marker["evidence_turn_seq"] in turns

    def test_findings_carry_their_owner_and_gap_status(
        self, app: FastAPI, scripted: ScriptedLayerProvider
    ) -> None:
        with TestClient(app) as client:
            body = post(client)

        assert body["l4_signals"][0]["owner"] == "Compliance"
        assert body["assist_events"][0]["is_gap"] is True

    def test_provenance_is_returned(self, app: FastAPI, scripted: ScriptedLayerProvider) -> None:
        with TestClient(app) as client:
            body = post(client)

        provenance = body["provenance"]
        assert provenance["provider"] == "scripted"
        assert provenance["rubric_version"]
        assert provenance["input_tokens"] == 500


class TestFailures:
    def test_text_without_speaker_prefixes_is_rejected_with_guidance(
        self, app: FastAPI, scripted: ScriptedLayerProvider
    ) -> None:
        with TestClient(app) as client:
            response = client.post(ANALYSES_URL, json={"transcript": "a wall of text"})

        assert response.status_code == 400
        body = response.json()
        assert body["code"] == "validation_error"
        assert "Agent Sarah:" in body["detail"]

    def test_an_empty_transcript_is_rejected_by_request_validation(
        self, app: FastAPI, scripted: ScriptedLayerProvider
    ) -> None:
        with TestClient(app) as client:
            response = client.post(ANALYSES_URL, json={"transcript": ""})

        assert response.status_code == 422

    def test_an_unreachable_provider_answers_503_rather_than_a_partial_result(
        self, app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        taxonomy = load_taxonomy(DEFAULT_TAXONOMY_PATH)
        rubric = load_rubric(DEFAULT_RUBRIC_PATH, taxonomy)
        provider = ScriptedLayerProvider(
            failures={"l1_understanding": ProviderUnavailableError("Ollama is not running.")}
        )
        app.dependency_overrides[get_analyze_transcript_use_case] = lambda: AnalyzeTranscript(
            prompts=StubPromptSource(),
            schemas=build_analysis_schemas(taxonomy, rubric),
            taxonomy=taxonomy,
            rubric=rubric,
            redaction=NoRedaction(),
            repository=InMemoryAnalysisRepository(),
            clock=FixedClock(),
        )
        monkeypatch.setattr(Container, "create_provider", lambda *_a, **_k: provider)

        with TestClient(app) as client:
            response = client.post(ANALYSES_URL, json={"transcript": CALL_89})

        assert response.status_code == 503
        assert response.json()["code"] == "provider_unavailable"
