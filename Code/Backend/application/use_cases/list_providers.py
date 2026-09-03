"""Report which model providers are configured, and which are actually usable.

The end user chooses the provider and model at analysis time (D3), so the UI has
to show more than a list of names: an Ollama server that is running but does not
have the model pulled, or a cloud provider with no key, must be visibly
unavailable *before* someone pastes a transcript and waits.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from application.ports.llm_provider import ProviderStatus


@dataclass(frozen=True)
class ProviderDescription:
    """One provider as presented to the user."""

    name: str
    model: str
    configured: bool
    reachable: bool
    implemented: bool
    is_default: bool
    # Whether choosing this provider spends money. The corpus screen needs it to
    # warn before a hundred calls go to a paid API.
    billable: bool = False
    # Whether transcripts stay inside this environment. Surfaced because the UI
    # states a privacy guarantee, and a guarantee must follow the configuration
    # rather than being written into the page.
    local: bool = False
    detail: str | None = None

    @property
    def selectable(self) -> bool:
        return self.implemented and self.configured and self.reachable


class ProviderProbe:
    """Builds a provider and reports its status, without raising."""

    async def describe(self, name: str) -> ProviderDescription:  # pragma: no cover - interface
        raise NotImplementedError


class ListProviders:
    """Lists every registered provider with its current status."""

    def __init__(self, probe: ProviderProbe, names: Sequence[str], default_name: str) -> None:
        self._probe = probe
        self._names = tuple(names)
        self._default = default_name

    async def execute(self) -> tuple[ProviderDescription, ...]:
        """Describe every provider, probing them at the same time.

        Serially, the screen waits for the sum of every probe, so one
        unreachable host makes the whole picker unusable rather than making one
        row unavailable. Concurrently it waits for the slowest.
        """
        return tuple(await asyncio.gather(*(self._probe.describe(name) for name in self._names)))

    @property
    def default_name(self) -> str:
        return self._default


def describe_from_status(
    status: ProviderStatus,
    *,
    is_default: bool,
    configured: bool,
    billable: bool,
    local: bool,
) -> ProviderDescription:
    return ProviderDescription(
        name=status.name,
        model=status.model,
        configured=configured,
        reachable=status.reachable,
        implemented=status.implemented,
        is_default=is_default,
        billable=billable,
        local=local,
        detail=status.detail,
    )
