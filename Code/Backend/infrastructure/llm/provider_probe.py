"""Builds each registered provider and reports whether it is usable.

A provider that cannot even be constructed — a missing API key — is reported as
*not configured* rather than allowed to raise. Listing providers must never fail
because one of them is unconfigured; that is the normal state of a local-first
deployment where the cloud keys are deliberately blank.
"""

from __future__ import annotations

from application.use_cases.list_providers import (
    ProviderDescription,
    ProviderProbe,
    describe_from_status,
)
from domain.errors import ConfigurationError
from infrastructure.llm.registry import ProviderRegistry


class RegistryProviderProbe(ProviderProbe):
    """Probes providers through the registry."""

    def __init__(self, registry: ProviderRegistry, default_name: str) -> None:
        self._registry = registry
        self._default = default_name

    async def describe(self, name: str) -> ProviderDescription:
        try:
            provider = self._registry.create(name)
        except ConfigurationError as exc:
            return ProviderDescription(
                name=name,
                model=self._registry.default_model_for(name),
                configured=False,
                reachable=False,
                implemented=True,
                is_default=name == self._default,
                detail=exc.message,
            )

        try:
            status = await provider.status()
        finally:
            await provider.aclose()

        return describe_from_status(status, is_default=name == self._default, configured=True)
