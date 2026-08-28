"""Provider registry.

Turns a provider name plus configuration into a live adapter. This is where a
missing API key becomes a clear error, and it is the only place that knows which
providers exist — adding one is a single entry here plus an adapter.

Selection never falls back. If the requested provider cannot be constructed, the
call fails; substituting a different model would invalidate the provenance
recorded against every stored analysis.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from application.ports.llm_provider import LLMProvider
from domain.errors import ConfigurationError, NotFoundError
from infrastructure.config.settings import Settings
from infrastructure.llm.providers import anthropic_provider, azure_foundry, ollama, openai_provider
from infrastructure.logging.llm_audit import LlmAuditLog

ProviderFactory = Callable[[Settings, str | None, LlmAuditLog], LLMProvider]


def _require(value: str | None, *, setting: str, provider: str) -> str:
    if not value or not value.strip():
        raise ConfigurationError(
            f"Provider {provider!r} was selected but {setting} is not set.",
            detail=f"Set {setting} in Code/Backend/.env, or choose a different provider.",
        )
    return value


def _build_ollama(settings: Settings, model: str | None, audit: LlmAuditLog) -> LLMProvider:
    return ollama.OllamaProvider(
        base_url=settings.ollama_base_url,
        model=model or settings.ollama_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        max_output_tokens=settings.llm_max_output_tokens,
        audit=audit,
    )


def _build_openai(settings: Settings, model: str | None, audit: LlmAuditLog) -> LLMProvider:
    return openai_provider.OpenAIProvider(
        api_key=_require(
            settings.openai_api_key,
            setting="OPENAI_API_KEY",
            provider=openai_provider.PROVIDER_NAME,
        ),
        model=model or settings.openai_model,
        base_url=settings.openai_base_url or None,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        max_output_tokens=settings.llm_max_output_tokens,
        audit=audit,
    )


def _build_anthropic(settings: Settings, model: str | None, audit: LlmAuditLog) -> LLMProvider:
    return anthropic_provider.AnthropicProvider(
        api_key=_require(
            settings.anthropic_api_key,
            setting="ANTHROPIC_API_KEY",
            provider=anthropic_provider.PROVIDER_NAME,
        ),
        model=model or settings.anthropic_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        max_output_tokens=settings.llm_max_output_tokens,
        audit=audit,
    )


def _build_azure(settings: Settings, model: str | None, audit: LlmAuditLog) -> LLMProvider:
    return azure_foundry.AzureFoundryProvider()


FACTORIES: Mapping[str, ProviderFactory] = {
    ollama.PROVIDER_NAME: _build_ollama,
    openai_provider.PROVIDER_NAME: _build_openai,
    anthropic_provider.PROVIDER_NAME: _build_anthropic,
    azure_foundry.PROVIDER_NAME: _build_azure,
}

PROVIDER_NAMES: tuple[str, ...] = tuple(FACTORIES)


class ProviderRegistry:
    """Creates provider adapters by name."""

    def __init__(self, settings: Settings, audit: LlmAuditLog) -> None:
        self._settings = settings
        self._audit = audit

    @property
    def names(self) -> tuple[str, ...]:
        return PROVIDER_NAMES

    def create(self, name: str | None = None, model: str | None = None) -> LLMProvider:
        """Build the named provider, or the configured default."""
        resolved = (name or self._settings.llm_provider).strip().lower()
        factory = FACTORIES.get(resolved)
        if factory is None:
            raise NotFoundError(
                f"Unknown model provider: {resolved!r}.",
                detail=f"Known providers: {', '.join(PROVIDER_NAMES)}",
            )
        return factory(self._settings, model, self._audit)

    def default_model_for(self, name: str) -> str:
        """The model this provider would use with no override."""
        defaults = {
            ollama.PROVIDER_NAME: self._settings.ollama_model,
            openai_provider.PROVIDER_NAME: self._settings.openai_model,
            anthropic_provider.PROVIDER_NAME: self._settings.anthropic_model,
            azure_foundry.PROVIDER_NAME: "not-configured",
        }
        return defaults.get(name, "unknown")
