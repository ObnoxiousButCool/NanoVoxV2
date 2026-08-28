"""Ollama adapter, driven through a stubbed HTTP transport.

Exercises the real adapter code — request shaping, error translation, status
reporting — without a running server.
"""

from __future__ import annotations

import json
from typing import Any

import httpx2 as httpx
import pytest

from application.ports.llm_provider import LlmRequest
from domain.errors import ProviderUnavailableError
from infrastructure.llm.providers.ollama import OllamaProvider
from infrastructure.logging.llm_audit import LlmAuditLog
from tests.support.llm import VALID_JSON, Sentiment

BASE_URL = "http://localhost:11434"
REQUEST = LlmRequest(prompt="Classify this.", response_model=Sentiment)


def provider_with(handler: httpx.MockTransport) -> OllamaProvider:
    return OllamaProvider(
        base_url=BASE_URL,
        model="qwen2.5:7b-instruct",
        timeout_seconds=5.0,
        max_retries=0,
        max_output_tokens=512,
        audit=LlmAuditLog(),
        client=httpx.AsyncClient(transport=handler),
    )


def chat_response(content: str, **extra: Any) -> dict[str, Any]:
    return {"message": {"role": "assistant", "content": content}, **extra}


class TestRequestShaping:
    async def test_the_response_schema_is_sent_for_constrained_decoding(self) -> None:
        # Asking a small local model for JSON in the prompt is unreliable;
        # constraining the decoder is what makes it dependable.
        sent: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            sent.update(json.loads(request.content))
            return httpx.Response(200, json=chat_response(VALID_JSON))

        provider = provider_with(httpx.MockTransport(handler))
        await provider.complete(REQUEST)
        await provider.aclose()

        assert sent["format"]["properties"].keys() >= {"sentiment", "confidence"}
        assert sent["stream"] is False
        assert sent["options"]["temperature"] == 0.0

    async def test_a_system_prompt_is_sent_as_a_system_message(self) -> None:
        sent: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            sent.update(json.loads(request.content))
            return httpx.Response(200, json=chat_response(VALID_JSON))

        provider = provider_with(httpx.MockTransport(handler))
        await provider.complete(
            LlmRequest(prompt="Classify.", response_model=Sentiment, system="Be terse.")
        )
        await provider.aclose()

        assert sent["messages"][0] == {"role": "system", "content": "Be terse."}

    async def test_usage_is_taken_from_the_eval_counts(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json=chat_response(VALID_JSON, prompt_eval_count=31, eval_count=17)
            )

        provider = provider_with(httpx.MockTransport(handler))
        result = await provider.complete(REQUEST)
        await provider.aclose()

        assert result.usage.input_tokens == 31
        assert result.usage.output_tokens == 17

    async def test_missing_counts_are_reported_as_unknown_not_as_zero(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=chat_response(VALID_JSON))

        provider = provider_with(httpx.MockTransport(handler))
        result = await provider.complete(REQUEST)
        await provider.aclose()

        assert not result.usage.reported


class TestFailureTranslation:
    async def test_an_http_error_becomes_a_provider_outage(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="model runner crashed")

        provider = provider_with(httpx.MockTransport(handler))

        with pytest.raises(ProviderUnavailableError) as exc_info:
            await provider.complete(REQUEST)
        await provider.aclose()

        assert "HTTP 500" in exc_info.value.message
        assert exc_info.value.detail is not None
        assert "crashed" in exc_info.value.detail

    async def test_a_connection_failure_names_the_address_that_was_tried(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        provider = provider_with(httpx.MockTransport(handler))

        with pytest.raises(ProviderUnavailableError) as exc_info:
            await provider.complete(REQUEST)
        await provider.aclose()

        assert BASE_URL in exc_info.value.message


class TestStatus:
    async def test_reachable_when_the_model_is_installed(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b-instruct"}]})

        provider = provider_with(httpx.MockTransport(handler))
        status = await provider.status()
        await provider.aclose()

        assert status.reachable

    async def test_a_running_server_missing_the_model_names_the_fix(self) -> None:
        # "Unreachable" would be misleading and unactionable here.
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"models": [{"name": "llama3.2:1b"}]})

        provider = provider_with(httpx.MockTransport(handler))
        status = await provider.status()
        await provider.aclose()

        assert not status.reachable
        assert status.detail is not None
        assert "ollama pull qwen2.5:7b-instruct" in status.detail

    async def test_status_reports_an_outage_rather_than_raising(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        provider = provider_with(httpx.MockTransport(handler))
        status = await provider.status()
        await provider.aclose()

        assert not status.reachable
        assert status.detail is not None
