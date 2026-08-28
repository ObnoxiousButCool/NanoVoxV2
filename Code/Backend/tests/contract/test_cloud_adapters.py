"""OpenAI, Anthropic and the Azure stub.

These adapters have no live smoke test in this build (no credentials are
configured), so their request shaping and error translation are pinned here with
stub clients instead.
"""

from __future__ import annotations

from typing import Any

import anthropic
import httpx as openai_httpx
import httpx2
import openai
import pytest

from application.ports.llm_provider import LlmRequest
from domain.errors import (
    ProviderNotImplementedError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from infrastructure.llm.providers.anthropic_provider import AnthropicProvider
from infrastructure.llm.providers.azure_foundry import AzureFoundryProvider
from infrastructure.llm.providers.openai_provider import OpenAIProvider, _strict_schema
from infrastructure.logging.llm_audit import LlmAuditLog
from tests.support.llm import VALID_JSON, Sentiment

REQUEST = LlmRequest(prompt="Classify this.", response_model=Sentiment)


class _Recorder:
    """Captures the keyword arguments of the call under test."""

    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.args: tuple[Any, ...] = ()
        self.kwargs: dict[str, Any] = {}

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        # models.retrieve takes the model as a positional argument; the chat and
        # messages calls are keyword-only.
        self.args = args
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self.result


class _Block:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _Usage:
    def __init__(self, **fields: int) -> None:
        for key, value in fields.items():
            setattr(self, key, value)


class _AnthropicResponse:
    def __init__(self, text: str) -> None:
        self.content = [_Block(text)]
        self.usage = _Usage(input_tokens=12, output_tokens=8)


class _OpenAIMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _OpenAIChoice:
    def __init__(self, content: str) -> None:
        self.message = _OpenAIMessage(content)


class _OpenAIResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_OpenAIChoice(content)]
        self.usage = _Usage(prompt_tokens=21, completion_tokens=9)


def anthropic_provider(recorder: _Recorder, monkeypatch: pytest.MonkeyPatch) -> AnthropicProvider:
    client = anthropic.AsyncAnthropic(api_key="test-key", max_retries=0)
    monkeypatch.setattr(client.messages, "parse", recorder)
    return AnthropicProvider(
        api_key="test-key",
        model="claude-opus-5",
        timeout_seconds=5.0,
        max_retries=0,
        max_output_tokens=512,
        audit=LlmAuditLog(),
        client=client,
    )


def openai_provider(recorder: _Recorder, monkeypatch: pytest.MonkeyPatch) -> OpenAIProvider:
    client = openai.AsyncOpenAI(api_key="test-key", max_retries=0)
    monkeypatch.setattr(client.chat.completions, "create", recorder)
    return OpenAIProvider(
        api_key="test-key",
        model="gpt-4o-mini",
        timeout_seconds=5.0,
        max_retries=0,
        max_output_tokens=512,
        audit=LlmAuditLog(),
        client=client,
    )


class TestAnthropicAdapter:
    async def test_no_sampling_parameters_are_sent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # temperature / top_p / top_k are removed on current Claude models and
        # are rejected with a 400. This would only fail at runtime.
        recorder = _Recorder(result=_AnthropicResponse(VALID_JSON))

        await anthropic_provider(recorder, monkeypatch).complete(REQUEST)

        assert "temperature" not in recorder.kwargs
        assert "top_p" not in recorder.kwargs
        assert "top_k" not in recorder.kwargs

    async def test_the_model_id_carries_no_date_suffix(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorder = _Recorder(result=_AnthropicResponse(VALID_JSON))

        await anthropic_provider(recorder, monkeypatch).complete(REQUEST)

        assert recorder.kwargs["model"] == "claude-opus-5"

    async def test_the_response_schema_is_passed_as_the_output_format(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorder = _Recorder(result=_AnthropicResponse(VALID_JSON))

        result = await anthropic_provider(recorder, monkeypatch).complete(REQUEST)

        assert recorder.kwargs["output_format"] is Sentiment
        assert result.value.sentiment == "NEGATIVE"
        assert result.usage.input_tokens == 12

    async def test_an_absent_system_prompt_is_omitted_not_sent_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorder = _Recorder(result=_AnthropicResponse(VALID_JSON))

        await anthropic_provider(recorder, monkeypatch).complete(REQUEST)

        assert recorder.kwargs["system"] is anthropic.omit

    async def test_a_status_error_becomes_a_provider_outage(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        error = anthropic.APIStatusError(
            "rate limited",
            response=httpx2.Response(
                429, request=httpx2.Request("POST", "https://api.anthropic.test/v1/messages")
            ),
            body=None,
        )
        recorder = _Recorder(error=error)

        with pytest.raises(ProviderUnavailableError, match="HTTP 429"):
            await anthropic_provider(recorder, monkeypatch).complete(REQUEST)


class TestOpenAIAdapter:
    async def test_strict_structured_output_is_requested(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorder = _Recorder(result=_OpenAIResponse(VALID_JSON))

        await openai_provider(recorder, monkeypatch).complete(REQUEST)

        response_format = recorder.kwargs["response_format"]
        assert response_format["type"] == "json_schema"
        assert response_format["json_schema"]["strict"] is True

    async def test_decoding_is_deterministic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        recorder = _Recorder(result=_OpenAIResponse(VALID_JSON))

        await openai_provider(recorder, monkeypatch).complete(REQUEST)

        assert recorder.kwargs["temperature"] == 0.0

    async def test_a_connection_error_becomes_a_provider_outage(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorder = _Recorder(
            error=openai.APIConnectionError(
                request=openai_httpx.Request("POST", "https://api.openai.test/v1/chat")
            )
        )

        with pytest.raises(ProviderUnavailableError, match="could not be reached"):
            await openai_provider(recorder, monkeypatch).complete(REQUEST)


class TestStrictSchema:
    def test_additional_properties_is_closed_on_every_object(self) -> None:
        # Strict mode rejects a schema that omits this; pydantic never emits it.
        schema = _strict_schema(
            {
                "type": "object",
                "properties": {
                    "nested": {"type": "object", "properties": {"a": {"type": "string"}}}
                },
                "$defs": {"Other": {"type": "object", "properties": {}}},
            }
        )

        assert schema["additionalProperties"] is False
        assert schema["properties"]["nested"]["additionalProperties"] is False
        assert schema["$defs"]["Other"]["additionalProperties"] is False

    def test_objects_inside_arrays_and_unions_are_covered(self) -> None:
        schema = _strict_schema(
            {
                "type": "object",
                "properties": {
                    "items": {"type": "array", "items": {"type": "object", "properties": {}}},
                    "either": {"anyOf": [{"type": "object", "properties": {}}, {"type": "null"}]},
                },
            }
        )

        assert schema["properties"]["items"]["items"]["additionalProperties"] is False
        assert schema["properties"]["either"]["anyOf"][0]["additionalProperties"] is False

    def test_a_real_pydantic_schema_passes_through(self) -> None:
        schema = _strict_schema(Sentiment.model_json_schema())

        assert schema["additionalProperties"] is False


class TestAzureStub:
    async def test_selecting_azure_fails_immediately_and_explicitly(self) -> None:
        # It must never quietly answer with a different provider: a caller who
        # asked for Azure and got OpenAI would have no way to know.
        with pytest.raises(ProviderNotImplementedError, match="not implemented in this build"):
            await AzureFoundryProvider().complete(REQUEST)

    async def test_it_is_listed_as_registered_but_unimplemented(self) -> None:
        status = await AzureFoundryProvider().status()

        assert not status.implemented
        assert not status.reachable
        assert status.detail is not None
        assert "ollama" in status.detail


class TestCloudStatusReporting:
    """`status()` must classify failures, since its text is what the picker shows."""

    async def test_anthropic_reports_a_rejected_key_specifically(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        error = anthropic.AuthenticationError(
            "bad key",
            response=httpx2.Response(
                401, request=httpx2.Request("POST", "https://api.anthropic.test/v1/messages")
            ),
            body=None,
        )
        provider = anthropic_provider(_Recorder(), monkeypatch)
        monkeypatch.setattr(provider._client.messages, "create", _Recorder(error=error))

        status = await provider.status()

        assert not status.reachable
        assert status.detail == "ANTHROPIC_API_KEY was rejected."

    async def test_anthropic_reports_other_failures_without_raising(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        error = anthropic.APIConnectionError(
            request=httpx2.Request("POST", "https://api.anthropic.test/v1/messages")
        )
        provider = anthropic_provider(_Recorder(), monkeypatch)
        monkeypatch.setattr(provider._client.messages, "create", _Recorder(error=error))

        status = await provider.status()

        assert not status.reachable
        assert status.detail == "APIConnectionError"

    async def test_anthropic_is_reachable_when_the_probe_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        provider = anthropic_provider(_Recorder(), monkeypatch)
        monkeypatch.setattr(provider._client.messages, "create", _Recorder(result=object()))

        assert (await provider.status()).reachable

    async def test_openai_reports_a_rejected_key_specifically(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        error = openai.AuthenticationError(
            "bad key",
            response=openai_httpx.Response(
                401, request=openai_httpx.Request("GET", "https://api.openai.test/v1/models")
            ),
            body=None,
        )
        provider = openai_provider(_Recorder(), monkeypatch)
        monkeypatch.setattr(provider._client.models, "retrieve", _Recorder(error=error))

        status = await provider.status()

        assert status.detail == "OPENAI_API_KEY was rejected."

    async def test_openai_reports_an_unavailable_model_by_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A key that works but a model the account cannot use is a different
        # problem, and needs a different message.
        error = openai.NotFoundError(
            "no such model",
            response=openai_httpx.Response(
                404, request=openai_httpx.Request("GET", "https://api.openai.test/v1/models")
            ),
            body=None,
        )
        provider = openai_provider(_Recorder(), monkeypatch)
        monkeypatch.setattr(provider._client.models, "retrieve", _Recorder(error=error))

        status = await provider.status()

        assert status.detail is not None
        assert "gpt-4o-mini" in status.detail

    async def test_openai_is_reachable_when_the_model_resolves(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        provider = openai_provider(_Recorder(), monkeypatch)
        monkeypatch.setattr(provider._client.models, "retrieve", _Recorder(result=object()))

        assert (await provider.status()).reachable


class TestResponseParsingEdgeCases:
    async def test_anthropic_usage_absent_is_reported_as_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _NoUsage:
            def __init__(self) -> None:
                self.content = [_Block(VALID_JSON)]

        recorder = _Recorder(result=_NoUsage())

        result = await anthropic_provider(recorder, monkeypatch).complete(REQUEST)

        assert not result.usage.reported

    async def test_a_response_with_no_text_block_fails_validation_not_silently(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _Empty:
            def __init__(self) -> None:
                self.content: list[object] = []

        recorder = _Recorder(result=_Empty())

        with pytest.raises(ProviderResponseError):
            await anthropic_provider(recorder, monkeypatch).complete(REQUEST)

    async def test_openai_usage_absent_is_reported_as_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _NoUsage:
            def __init__(self) -> None:
                self.choices = [_OpenAIChoice(VALID_JSON)]

        recorder = _Recorder(result=_NoUsage())

        result = await openai_provider(recorder, monkeypatch).complete(REQUEST)

        assert not result.usage.reported

    async def test_an_openai_response_with_no_choices_fails_validation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _Empty:
            def __init__(self) -> None:
                self.choices: list[object] = []

        recorder = _Recorder(result=_Empty())

        with pytest.raises(ProviderResponseError):
            await openai_provider(recorder, monkeypatch).complete(REQUEST)
