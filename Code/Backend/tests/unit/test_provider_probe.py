"""A provider that never answers must not hold the picker open.

An unreachable host does not refuse the connection, it goes quiet, and the socket
waits far longer than anyone looking at a dropdown will. Before this bound, an
Ollama box that had gone away left the corpus screen showing "Checking which
providers…" for as long as the connect took — with no way to pick a provider that
was working perfectly well.
"""

from __future__ import annotations

import asyncio

import pytest

from application.ports.llm_provider import ProviderStatus
from infrastructure.llm.provider_probe import RegistryProviderProbe
from infrastructure.llm.registry import ProviderRegistry
from infrastructure.logging.llm_audit import LlmAuditLog
from tests.support.settings import make_settings

PROBE_TIMEOUT = 0.05


class _SilentProvider:
    """Answers `status()` only after longer than anyone will wait."""

    def __init__(self) -> None:
        self.closed = False

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return "qwen2.5:7b-instruct"

    async def status(self) -> ProviderStatus:
        await asyncio.sleep(60)
        raise AssertionError("the probe should have given up long before this")

    async def aclose(self) -> None:
        self.closed = True


class _StubRegistry(ProviderRegistry):
    def __init__(self, provider: _SilentProvider) -> None:
        super().__init__(make_settings(), LlmAuditLog())
        self._provider = provider

    def create(self, name: str | None = None, model: str | None = None) -> object:  # type: ignore[override]
        return self._provider


@pytest.fixture
def silent() -> _SilentProvider:
    return _SilentProvider()


async def test_a_silent_provider_is_reported_unavailable_rather_than_waited_for(
    silent: _SilentProvider,
) -> None:
    probe = RegistryProviderProbe(_StubRegistry(silent), "ollama", PROBE_TIMEOUT)

    started = asyncio.get_running_loop().time()
    description = await probe.describe("ollama")
    elapsed = asyncio.get_running_loop().time() - started

    assert elapsed < 1.0
    assert not description.reachable
    assert not description.selectable


async def test_the_reason_names_the_timeout_rather_than_saying_nothing(
    silent: _SilentProvider,
) -> None:
    # "unavailable" with no reason sends someone hunting through logs.
    probe = RegistryProviderProbe(_StubRegistry(silent), "ollama", PROBE_TIMEOUT)

    description = await probe.describe("ollama")

    assert description.detail is not None
    assert "did not answer" in description.detail


async def test_the_abandoned_client_is_still_closed(silent: _SilentProvider) -> None:
    # A timeout must not leak the connection it gave up on.
    probe = RegistryProviderProbe(_StubRegistry(silent), "ollama", PROBE_TIMEOUT)

    await probe.describe("ollama")

    assert silent.closed
