"""Azure AI Foundry — registered, not implemented (DEC-05).

This exists so that Azure appears in the provider list as an explicit "not in
this build" rather than as a silent absence, and so that selecting it fails
immediately with an actionable message.

It must never fall back to another provider. A caller who asked for Azure and
quietly received OpenAI output would have no way to know their governance
requirement was not met.
"""

from __future__ import annotations

from application.ports.llm_provider import (
    LLMProvider,
    LlmRequest,
    ProviderStatus,
    StructuredResult,
    TModel,
)
from domain.errors import ProviderNotImplementedError

PROVIDER_NAME = "azure_foundry"

_MESSAGE = (
    "Azure AI Foundry is registered but not implemented in this build. "
    "Choose 'ollama', 'openai' or 'anthropic'."
)


class AzureFoundryProvider(LLMProvider):
    """Placeholder that fails fast and explicitly."""

    def __init__(self, model: str = "not-configured") -> None:
        self._model = model

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, request: LlmRequest[TModel]) -> StructuredResult[TModel]:
        raise ProviderNotImplementedError(
            _MESSAGE,
            detail="Implementing it means adding an adapter; the port is unchanged.",
        )

    async def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            model=self._model,
            reachable=False,
            detail=_MESSAGE,
            implemented=False,
        )
