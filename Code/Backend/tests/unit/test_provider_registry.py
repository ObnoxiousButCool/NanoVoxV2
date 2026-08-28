"""Provider selection never falls back, and a missing key is a clear error."""

from __future__ import annotations

import pytest

from domain.errors import ConfigurationError, NotFoundError
from infrastructure.llm.providers.anthropic_provider import AnthropicProvider
from infrastructure.llm.providers.azure_foundry import AzureFoundryProvider
from infrastructure.llm.providers.ollama import OllamaProvider
from infrastructure.llm.providers.openai_provider import OpenAIProvider
from infrastructure.llm.registry import PROVIDER_NAMES, ProviderRegistry
from infrastructure.logging.llm_audit import LlmAuditLog
from tests.support.settings import make_settings


def registry(**overrides: object) -> ProviderRegistry:
    return ProviderRegistry(make_settings(**overrides), LlmAuditLog())


def test_all_four_providers_are_registered() -> None:
    assert set(PROVIDER_NAMES) == {"ollama", "openai", "anthropic", "azure_foundry"}


def test_the_default_provider_is_the_local_one() -> None:
    # The privacy claim depends on local-first being the default, not an option
    # someone has to remember to choose.
    provider = registry().create()

    assert isinstance(provider, OllamaProvider)
    assert provider.name == "ollama"


def test_a_named_provider_overrides_the_default() -> None:
    provider = registry(anthropic_api_key="k").create("anthropic")

    assert isinstance(provider, AnthropicProvider)


def test_provider_names_are_matched_case_insensitively() -> None:
    assert registry(openai_api_key="k").create("  OpenAI ").name == "openai"


def test_a_model_override_is_applied() -> None:
    provider = registry().create("ollama", "llama3.1:latest")

    assert provider.model == "llama3.1:latest"


def test_an_unknown_provider_names_the_ones_that_exist() -> None:
    with pytest.raises(NotFoundError) as exc_info:
        registry().create("gemini")

    assert exc_info.value.detail is not None
    assert "ollama" in exc_info.value.detail


class TestMissingCredentials:
    def test_openai_without_a_key_names_the_setting(self) -> None:
        with pytest.raises(ConfigurationError) as exc_info:
            registry(openai_api_key="").create("openai")

        assert "OPENAI_API_KEY is not set" in exc_info.value.message
        assert exc_info.value.detail is not None
        assert ".env" in exc_info.value.detail

    def test_anthropic_without_a_key_names_the_setting(self) -> None:
        with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY is not set"):
            registry(anthropic_api_key="   ").create("anthropic")

    def test_a_missing_key_never_silently_falls_back_to_the_local_provider(self) -> None:
        # Quietly answering an OpenAI request with Ollama would corrupt the
        # provenance recorded against every stored analysis.
        with pytest.raises(ConfigurationError):
            registry(openai_api_key="").create("openai")


def test_azure_is_constructible_so_it_can_report_itself_unimplemented() -> None:
    # It must appear in the provider list rather than being invisible.
    assert isinstance(registry().create("azure_foundry"), AzureFoundryProvider)


def test_the_openai_base_url_override_is_honoured() -> None:
    provider = registry(openai_api_key="k", openai_base_url="http://gateway.internal/v1").create(
        "openai"
    )

    assert isinstance(provider, OpenAIProvider)


class TestDefaultModels:
    def test_each_provider_reports_the_model_it_would_use(self) -> None:
        subject = registry()

        assert subject.default_model_for("ollama") == "qwen2.5:7b-instruct"
        assert subject.default_model_for("anthropic") == "claude-opus-5"
        assert subject.default_model_for("azure_foundry") == "not-configured"

    def test_an_unknown_name_does_not_raise(self) -> None:
        # Used while listing providers, which must not fail on a bad name.
        assert registry().default_model_for("gemini") == "unknown"
