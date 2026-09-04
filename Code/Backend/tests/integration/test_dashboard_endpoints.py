"""The dashboard and calls endpoints, against a seeded database."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from infrastructure.config.settings import Settings
from infrastructure.config.taxonomy_loader import load_taxonomy
from infrastructure.persistence.engine import create_database_engine, create_session_factory
from infrastructure.persistence.repositories.analysis_repository import SqlAnalysisRepository
from tests.support.corpus import TOTAL_CALLS, build_corpus


@pytest.fixture
def seeded(app: FastAPI, settings: Settings) -> Iterator[TestClient]:
    """A started application whose database already holds the fixture corpus.

    Seeded on its own engine before the application starts, so the write never
    shares an event loop with the running app.
    """
    taxonomy = load_taxonomy(settings.taxonomy_path)

    async def seed() -> None:
        engine = create_database_engine(settings)
        try:
            repository = SqlAnalysisRepository(create_session_factory(engine), taxonomy)
            for analysis in build_corpus(taxonomy):
                await repository.save(analysis)
        finally:
            await engine.dispose()

    asyncio.run(seed())

    with TestClient(app) as client:
        yield client


def get(client: TestClient, path: str, **params: Any) -> dict[str, Any]:
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    body = response.json()
    return body if isinstance(body, dict) else {"items": body}


class TestOverviewEndpoint:
    def test_returns_metrics_histogram_categories_and_attention(self, seeded: TestClient) -> None:
        body = get(seeded, "/api/v1/dashboard/overview")

        assert body["metrics"]["total_calls"] == TOTAL_CALLS
        assert body["histogram"]["total"] == TOTAL_CALLS
        assert body["categories"]
        assert body["attention"]

    def test_the_attention_queue_leads_with_the_most_severe_item(self, seeded: TestClient) -> None:
        body = get(seeded, "/api/v1/dashboard/overview")

        assert body["attention"][0]["severity"] == "CRITICAL"
        assert body["attention"][0]["owner"]

    def test_taxonomy_coverage_is_reported(self, seeded: TestClient) -> None:
        # Below 90% means the categories need revising, not the chart.
        body = get(seeded, "/api/v1/dashboard/overview")

        assert body["taxonomy_coverage"] == 100.0


class TestAgentsEndpoint:
    def test_unrated_agents_are_returned_with_a_null_tier_and_a_note(
        self, seeded: TestClient
    ) -> None:
        rows = seeded.get("/api/v1/dashboard/agents").json()
        by_name = {row["agent_name"]: row for row in rows}

        assert by_name["Priya"]["tier"] is None
        assert "significance threshold" in by_name["Priya"]["note"]
        assert by_name["Brad"]["tier"] == "POOR"
        assert by_name["Brad"]["note"] is None


class TestBrokersEndpoint:
    def test_net_positive_is_reported_per_broker(self, seeded: TestClient) -> None:
        rows = seeded.get("/api/v1/dashboard/brokers").json()
        by_name = {row["broker_name"]: row for row in rows}

        assert by_name["Patricia Nunez"]["is_net_positive"] is True
        assert by_name["Marcus Trent"]["is_net_positive"] is False
        assert by_name["Marcus Trent"]["call_references"] == ["F0008", "F0009", "F0010"]


class TestSignalsEndpoint:
    def test_categories_with_no_signals_are_returned_with_zero(self, seeded: TestClient) -> None:
        body = seeded.get("/api/v1/dashboard/signals").json()
        by_code = {row["code"]: row for row in body["categories"]}

        assert by_code["provider_performance"]["count"] == 0
        assert by_code["process_breakdown"]["count"] == 3

    def test_owners_are_listed_with_their_load(self, seeded: TestClient) -> None:
        body = seeded.get("/api/v1/dashboard/signals").json()
        by_owner = {row["owner"]: row["count"] for row in body["owners"]}

        assert by_owner["Operations"] == 3
        assert by_owner["Provider Relations"] == 0


class TestPulseEndpoint:
    """The only figure on the dashboard that says which way anything is going."""

    def test_it_returns_a_week_per_point(self, seeded: TestClient) -> None:
        body = seeded.get("/api/v1/dashboard/pulse").json()

        assert [point["label"] for point in body["points"]] == ["27 Jul", "3 Aug", "10 Aug"]
        assert sum(point["calls"] for point in body["points"]) == TOTAL_CALLS
        assert body["undated_calls"] == 0

    def test_the_delta_compares_the_last_two_weeks_with_calls(self, seeded: TestClient) -> None:
        body = seeded.get("/api/v1/dashboard/pulse").json()

        assert body["latest"]["label"] == "10 Aug"
        assert body["previous"]["label"] == "3 Aug"
        assert body["delta"]["resolution_rate"] == pytest.approx(
            body["latest"]["resolution_rate"] - body["previous"]["resolution_rate"], abs=0.1
        )

    def test_the_sentiment_arc_is_reported_beside_it(self, seeded: TestClient) -> None:
        body = seeded.get("/api/v1/dashboard/pulse").json()
        sentiment = body["sentiment"]

        assert (
            sentiment["improved"]
            + sentiment["unchanged"]
            + sentiment["worsened"]
            + sentiment["unclassified"]
            == TOTAL_CALLS
        )
        assert 0 <= sentiment["improved_rate"] <= 100


class TestWorkMixEndpoint:
    def test_every_configured_caller_gets_a_row(self, seeded: TestClient) -> None:
        # Including the ones nobody called, which is the more interesting row.
        body = seeded.get("/api/v1/dashboard/work-mix").json()

        assert {row["caller_type"] for row in body["callers"]} == {
            "MEMBER",
            "EMPLOYER",
            "BROKER",
        }

    def test_the_populations_are_measured_separately(self, seeded: TestClient) -> None:
        body = seeded.get("/api/v1/dashboard/work-mix").json()
        by_type = {row["caller_type"]: row for row in body["callers"]}

        assert by_type["EMPLOYER"]["calls"] == 1
        assert by_type["BROKER"]["calls"] == 1
        assert by_type["MEMBER"]["calls"] == TOTAL_CALLS - 2

    def test_hours_carry_a_thin_evidence_flag(self, seeded: TestClient) -> None:
        body = seeded.get("/api/v1/dashboard/work-mix").json()

        assert body["hours"]
        assert all("is_thin" in hour for hour in body["hours"])
        assert body["busiest_hour"] is not None


class TestCallsEndpoint:
    def test_lists_calls_with_a_total_and_paging(self, seeded: TestClient) -> None:
        body = get(seeded, "/api/v1/calls", limit=4)

        assert len(body["items"]) == 4
        assert body["total"] == TOTAL_CALLS
        assert body["has_more"] is True

    def test_filters_narrow_the_total(self, seeded: TestClient) -> None:
        body = get(seeded, "/api/v1/calls", agent="Brad", resolution="UNRESOLVED")

        assert body["total"] == 3

    def test_filter_by_signal(self, seeded: TestClient) -> None:
        body = get(seeded, "/api/v1/calls", signal="clinical_risk")

        assert body["total"] == 1
        assert body["items"][0]["reference"] == "F0006"

    def test_an_out_of_range_limit_is_rejected(self, seeded: TestClient) -> None:
        response = seeded.get("/api/v1/calls", params={"limit": 500})

        assert response.status_code == 422

    def test_one_call_is_returned_in_full(self, seeded: TestClient) -> None:
        listing = get(seeded, "/api/v1/calls", search="F0006")
        call_id = listing["items"][0]["id"]

        body = get(seeded, f"/api/v1/calls/{call_id}")

        assert body["reference"] == "F0006"
        assert body["score"]["status"] == "provisional"
        assert body["transcript"]
        assert body["provenance"]["provider"] == "fixture"

    def test_an_unknown_call_is_a_404_problem_document(self, seeded: TestClient) -> None:
        response = seeded.get("/api/v1/calls/9999")

        assert response.status_code == 404
        assert response.json()["code"] == "not_found"


class TestTaxonomyEndpoint:
    def test_the_frontend_can_render_filters_without_hard_coding_a_vocabulary(
        self, client: TestClient
    ) -> None:
        body = client.get("/api/v1/taxonomy").json()

        assert len(body["categories"]) == 7
        assert len(body["l4_categories"]) == 6
        assert "UNRESOLVED" in body["resolutions"]
        assert body["tiers"]["good"] == 86
        assert body["tiers"]["min_calls_for_tier_rating"] == 5
        assert body["rubric_version"]


class TestEmptyDatabase:
    def test_the_dashboard_renders_before_any_call_is_analyzed(self, client: TestClient) -> None:
        # A fresh install must not crash or show misleading zeros-as-percentages.
        body = client.get("/api/v1/dashboard/overview").json()

        assert body["metrics"]["total_calls"] == 0
        assert body["metrics"]["median_score"] == 0
        assert body["metrics"]["first_contact_resolution_rate"] == 0
        assert body["attention"] == []
        assert body["histogram"]["total"] == 0
        # Categories are still listed so the chart has its shape.
        assert len(body["categories"]) == 7

    def test_agents_and_brokers_are_empty_lists_not_errors(self, client: TestClient) -> None:
        assert client.get("/api/v1/dashboard/agents").json() == []
        assert client.get("/api/v1/dashboard/brokers").json() == []
