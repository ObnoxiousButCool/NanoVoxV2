"""Every error leaves the API as an RFC 9457 problem document (D7).

Internal detail must never reach the client: a 500 carries a generic message and
the correlation ID, and nothing else.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from domain.errors import (
    ConfigurationError,
    DependencyUnavailableError,
    NanoVoxError,
    NotFoundError,
    ValidationError,
)
from frameworks_drivers.api.errors import GENERIC_ERROR_MESSAGE, PROBLEM_MEDIA_TYPE
from infrastructure.logging.correlation import CORRELATION_ID_HEADER

_INTERNAL_DETAIL = "internal connection detail that must never be disclosed"


class _UnmappedError(NanoVoxError):
    """A domain error with no entry in the status map."""

    code = "unmapped"


@pytest.fixture
def error_client(app: FastAPI) -> Iterator[TestClient]:
    """A client whose application exposes one route per failure mode."""

    @app.get("/boom/validation")
    async def _validation() -> None:
        raise ValidationError("Transcript must contain at least one speaker turn.")

    @app.get("/boom/not-found")
    async def _not_found() -> None:
        raise NotFoundError("Call 4242 does not exist.")

    @app.get("/boom/unavailable")
    async def _unavailable() -> None:
        raise DependencyUnavailableError("Model provider is unreachable.", detail="timeout")

    @app.get("/boom/configuration")
    async def _configuration() -> None:
        raise ConfigurationError("Bad configuration", detail=_INTERNAL_DETAIL)

    @app.get("/boom/unexpected")
    async def _unexpected() -> None:
        raise RuntimeError(_INTERNAL_DETAIL)

    @app.get("/boom/query")
    async def _query(count: int) -> int:
        return count

    @app.get("/boom/unmapped")
    async def _unmapped() -> None:
        raise _UnmappedError("Unknown to the status map.", detail=_INTERNAL_DETAIL)

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_validation_error_becomes_400(error_client: TestClient) -> None:
    response = error_client.get("/boom/validation")

    assert response.status_code == 400
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["title"] == "Transcript must contain at least one speaker turn."
    assert body["correlation_id"] == response.headers[CORRELATION_ID_HEADER]


def test_not_found_error_becomes_404(error_client: TestClient) -> None:
    response = error_client.get("/boom/not-found")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_dependency_error_becomes_503_and_keeps_its_detail(error_client: TestClient) -> None:
    response = error_client.get("/boom/unavailable")

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "dependency_unavailable"
    assert body["detail"] == "timeout"


def test_server_side_domain_error_does_not_leak_its_detail(error_client: TestClient) -> None:
    response = error_client.get("/boom/configuration")

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "configuration_error"
    assert _INTERNAL_DETAIL not in response.text
    assert "correlation ID" in body["detail"]


def test_unexpected_exception_is_answered_generically(error_client: TestClient) -> None:
    response = error_client.get("/boom/unexpected")

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "internal_error"
    assert _INTERNAL_DETAIL not in response.text
    assert body["correlation_id"] == response.headers[CORRELATION_ID_HEADER]


def test_request_validation_failure_becomes_422_with_the_offending_field(
    error_client: TestClient,
) -> None:
    response = error_client.get("/boom/query", params={"count": "not-a-number"})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "request_validation_error"
    assert body["detail"] is not None
    assert "count" in body["detail"]


def test_an_unmapped_domain_error_falls_back_to_a_generic_500(error_client: TestClient) -> None:
    response = error_client.get("/boom/unmapped")

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "unmapped"
    assert body["detail"] == GENERIC_ERROR_MESSAGE
    assert _INTERNAL_DETAIL not in response.text


def test_error_responses_still_carry_cors_headers(error_client: TestClient) -> None:
    # CORS is the outermost middleware precisely so the browser can read an error.
    response = error_client.get("/boom/unexpected", headers={"Origin": "http://127.0.0.1:5173"})

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert CORRELATION_ID_HEADER in response.headers["access-control-expose-headers"]
