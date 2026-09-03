"""Builds each registered provider and reports whether it is usable.

A provider that cannot even be constructed — a missing API key — is reported as
*not configured* rather than allowed to raise. Listing providers must never fail
because one of them is unconfigured; that is the normal state of a local-first
deployment where the cloud keys are deliberately blank.
"""

from __future__ import annotations

import asyncio

from application.use_cases.list_providers import (
    ProviderDescription,
    ProviderProbe,
    describe_from_status,
)
from domain.errors import ConfigurationError
from infrastructure.llm.registry import ProviderRegistry, is_billable, is_local


class RegistryProviderProbe(ProviderProbe):
    """Probes providers through the registry."""

    def __init__(
        self, registry: ProviderRegistry, default_name: str, timeout_seconds: float = 5.0
    ) -> None:
        self._registry = registry
        self._default = default_name
        self._timeout = timeout_seconds

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
                billable=is_billable(name),
                local=is_local(name),
                detail=exc.message,
            )

        try:
            status = await asyncio.wait_for(provider.status(), timeout=self._timeout)
        # asyncio.TimeoutError, not the builtin: they are only the same object
        # from Python 3.11, and this runs on 3.10.
        except asyncio.TimeoutError:
            # An unreachable host does not refuse a connection, it goes quiet, and
            # the socket waits far longer than anyone looking at a dropdown will.
            # Reported as unavailable with the reason rather than waited out.
            return ProviderDescription(
                name=name,
                model=self._registry.default_model_for(name),
                configured=True,
                reachable=False,
                implemented=True,
                is_default=name == self._default,
                billable=is_billable(name),
                local=is_local(name),
                detail=f"{name} did not answer within {self._timeout:g}s.",
            )
        finally:
            await provider.aclose()

        return describe_from_status(
            status,
            is_default=name == self._default,
            configured=True,
            billable=is_billable(name),
            local=is_local(name),
        )
