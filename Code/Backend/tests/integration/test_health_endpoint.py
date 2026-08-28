"""End-to-end checks on the health endpoint, against a real SQLite database."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.ports.clock import Clock
from application.ports.health_probe import HealthProbe
from application.use_cases.get_health import GetHealth
from domain.value_objects.health import ComponentHealth, ComponentStatus
from frameworks_drivers.api.dependencies import get_health_use_case
from frameworks_drivers.api.errors import PROBLEM_MEDIA_TYPE
from infrastructure.logging.correlation import CORRELATION_ID_HEADER

HEALTH_URL = "/api/v1/health"


class _FixedClock(Clock):
    def now(self) -> datetime:
        return datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


class _DownProbe(HealthProbe):
    @property
    def name(self) -> str:
        return "database"

    async def check(self) -> ComponentHealth:
        return ComponentHealth(self.name, ComponentStatus.DOWN, detail="OperationalError")


def test_health_reports_the_real_database_as_up(client: TestClient) -> None:
    response = client.get(HEALTH_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "up"
    assert body["application"] == "NanoVox"
    assert body["environment"] == "local"
    assert [component["name"] for component in body["components"]] == ["database"]
    assert body["components"][0]["status"] == "up"


def test_health_response_carries_a_correlation_id(client: TestClient) -> None:
    response = client.get(HEALTH_URL)

    assert response.headers[CORRELATION_ID_HEADER]


def test_an_inbound_correlation_id_is_echoed_back(client: TestClient) -> None:
    response = client.get(HEALTH_URL, headers={CORRELATION_ID_HEADER: "trace-me"})

    assert response.headers[CORRELATION_ID_HEADER] == "trace-me"


def test_an_overlong_inbound_correlation_id_is_truncated(client: TestClient) -> None:
    response = client.get(HEALTH_URL, headers={CORRELATION_ID_HEADER: "x" * 500})

    assert response.headers[CORRELATION_ID_HEADER] == "x" * 64


def test_health_answers_503_when_a_component_is_down(app: FastAPI) -> None:
    app.dependency_overrides[get_health_use_case] = lambda: GetHealth(
        probes=[_DownProbe()], clock=_FixedClock()
    )

    with TestClient(app) as client:
        response = client.get(HEALTH_URL)

    assert response.status_code == 503
    assert response.json()["status"] == "down"
    assert response.json()["components"][0]["detail"] == "OperationalError"


def test_unknown_route_returns_a_problem_document(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    body = response.json()
    assert body["code"] == "http_404"
    assert body["status"] == 404
    assert body["correlation_id"] == response.headers[CORRELATION_ID_HEADER]


def test_openapi_document_is_available_outside_production(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert HEALTH_URL in response.json()["paths"]
