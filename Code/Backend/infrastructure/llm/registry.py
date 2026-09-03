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

# Whether calling this provider costs money per token. A property of the adapter,
# not of configuration: Ollama runs on the machine in front of you, and no .env
# value can make an OpenAI call free. It gates the corpus run's cost guard, which
# is why it is stated once here rather than inferred from a name at each use.
BILLABLE_PROVIDERS: frozenset[str] = frozenset(
    {
        openai_provider.PROVIDER_NAME,
        anthropic_provider.PROVIDER_NAME,
        azure_foundry.PROVIDER_NAME,
    }
)


# Whether a provider runs inside this environment. A property of where the model
# executes, not of what it costs — modelled separately from BILLABLE_PROVIDERS on
# purpose. The two happen to coincide today, and reading one as the other is how
# a privacy claim ends up attached to a provider that never earned it.
LOCAL_PROVIDERS: frozenset[str] = frozenset({ollama.PROVIDER_NAME})


def is_local(name: str) -> bool:
    """Whether transcripts stay inside this environment when using this provider.

    An unknown name counts as *not* local. The claim being made here is a privacy
    guarantee about member health conversations, so the safe direction to be
    wrong in is the one that promises less.
    """
    return name.strip().lower() in LOCAL_PROVIDERS


def is_billable(name: str) -> bool:
    """Whether a run against this provider would be charged for.

    An unknown name counts as billable. Guessing "free" for something we do not
    recognise is the expensive direction to be wrong in.
    """
    resolved = name.strip().lower()
    return resolved not in FACTORIES or resolved in BILLABLE_PROVIDERS


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
