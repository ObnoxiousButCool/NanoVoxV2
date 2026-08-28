"""The provider picker must show why a provider cannot be used, not just hide it."""

from __future__ import annotations

from typing import Any

import httpx2 as httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.use_cases.list_providers import (
    ListProviders,
    ProviderDescription,
    ProviderProbe,
)
from frameworks_drivers.api.dependencies import get_list_providers_use_case

PROVIDERS_URL = "/api/v1/providers"


class _StubProbe(ProviderProbe):
    def __init__(self, descriptions: dict[str, ProviderDescription]) -> None:
        self._descriptions = descriptions

    async def describe(self, name: str) -> ProviderDescription:
        return self._descriptions[name]


def _description(name: str, **overrides: Any) -> ProviderDescription:
    defaults: dict[str, Any] = {
        "name": name,
        "model": f"{name}-model",
        "configured": True,
        "reachable": True,
        "implemented": True,
        "is_default": False,
        "detail": None,
    }
    defaults.update(overrides)
    return ProviderDescription(**defaults)


@pytest.fixture
def providers_client(app: FastAPI) -> TestClient:
    descriptions = {
        "ollama": _description("ollama", is_default=True),
        "openai": _description(
            "openai", configured=False, reachable=False, detail="OPENAI_API_KEY is not set."
        ),
        "azure_foundry": _description(
            "azure_foundry",
            implemented=False,
            reachable=False,
            detail="Registered but not implemented in this build.",
        ),
    }
    app.dependency_overrides[get_list_providers_use_case] = lambda: ListProviders(
        probe=_StubProbe(descriptions), names=tuple(descriptions), default_name="ollama"
    )
    return TestClient(app)


def test_every_provider_is_listed_including_unusable_ones(providers_client: TestClient) -> None:
    body = providers_client.get(PROVIDERS_URL).json()

    assert body["default"] == "ollama"
    assert [entry["name"] for entry in body["providers"]] == ["ollama", "openai", "azure_foundry"]


def test_a_usable_provider_is_selectable(providers_client: TestClient) -> None:
    body = providers_client.get(PROVIDERS_URL).json()

    ollama = body["providers"][0]
    assert ollama["selectable"] is True
    assert ollama["is_default"] is True


def test_an_unconfigured_provider_is_shown_with_the_reason(providers_client: TestClient) -> None:
    # Hiding it would leave the user with no idea why their choice is absent.
    body = providers_client.get(PROVIDERS_URL).json()

    openai = body["providers"][1]
    assert openai["selectable"] is False
    assert openai["configured"] is False
    assert "OPENAI_API_KEY" in openai["detail"]


def test_an_unimplemented_provider_is_marked_as_such(providers_client: TestClient) -> None:
    body = providers_client.get(PROVIDERS_URL).json()

    azure = body["providers"][2]
    assert azure["implemented"] is False
    assert azure["selectable"] is False


def test_the_endpoint_works_against_the_real_registry(client: TestClient) -> None:
    # No stub: exercises the real probe, with no cloud keys configured and
    # whatever Ollama state the machine happens to be in.
    response = client.get(PROVIDERS_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["default"] == "ollama"
    names = {entry["name"] for entry in body["providers"]}
    assert names == {"ollama", "openai", "anthropic", "azure_foundry"}

    by_name = {entry["name"]: entry for entry in body["providers"]}
    assert by_name["openai"]["configured"] is False
    assert by_name["azure_foundry"]["implemented"] is False


def test_listing_providers_survives_an_unreachable_ollama(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A local server that is simply not running is the normal case on a fresh
    # machine; the list must still render.
    def refuse(*_args: object, **_kwargs: object) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "get", refuse)

    with TestClient(app) as client:
        body = client.get(PROVIDERS_URL).json()

    ollama = next(entry for entry in body["providers"] if entry["name"] == "ollama")
    assert ollama["reachable"] is False
    assert ollama["selectable"] is False
