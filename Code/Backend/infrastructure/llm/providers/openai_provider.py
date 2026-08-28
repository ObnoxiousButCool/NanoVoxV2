"""OpenAI adapter.

Uses the official ``openai`` SDK with native structured outputs: a JSON Schema in
``response_format`` with ``strict: true``, which constrains decoding rather than
merely requesting JSON.

``additionalProperties: false`` is required on every object for strict mode, and
pydantic does not emit it — :func:`_strict_schema` adds it throughout. Without
that the API rejects the schema outright.
"""

from __future__ import annotations

from typing import Any

import openai
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from application.ports.llm_provider import LlmRequest, ProviderStatus, TModel, TokenUsage
from domain.errors import ProviderUnavailableError
from infrastructure.llm.base import DETERMINISTIC_TEMPERATURE, RawCompletion, StructuredProvider
from infrastructure.logging.llm_audit import LlmAuditLog

PROVIDER_NAME = "openai"
DEFAULT_MODEL = "gpt-4o-mini"

_SCHEMA_NAME = "nanovox_response"


class OpenAIProvider(StructuredProvider):
    """Structured completion against the OpenAI Chat Completions API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        max_output_tokens: int,
        audit: LlmAuditLog,
        base_url: str | None = None,
        client: AsyncOpenAI | None = None,
    ) -> None:
        super().__init__(
            model=model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
            audit=audit,
        )
        # Retries disabled for the same reason as the Anthropic adapter: the base
        # class owns retry policy, and every attempt must reach the audit log.
        self._client = client or AsyncOpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
            base_url=base_url,
        )

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    async def _generate(self, request: LlmRequest[TModel], correction: str | None) -> RawCompletion:
        messages: list[ChatCompletionMessageParam] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        if correction:
            messages.append({"role": "user", "content": correction})

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=DETERMINISTIC_TEMPERATURE,
                max_tokens=self.output_token_budget(request),
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": _SCHEMA_NAME,
                        "strict": True,
                        "schema": _strict_schema(request.response_model.model_json_schema()),
                    },
                },
            )
        except openai.APIStatusError as exc:
            raise ProviderUnavailableError(
                f"OpenAI returned HTTP {exc.status_code}.", detail=str(exc)
            ) from exc
        except openai.APIConnectionError as exc:
            raise ProviderUnavailableError(
                "The OpenAI API could not be reached.", detail=str(exc)
            ) from exc

        return RawCompletion(text=_content_of(response), usage=_usage_of(response))

    async def status(self) -> ProviderStatus:
        try:
            await self._client.models.retrieve(self._model)
        except openai.AuthenticationError:
            return ProviderStatus(
                name=self.name,
                model=self._model,
                reachable=False,
                detail="OPENAI_API_KEY was rejected.",
            )
        except openai.NotFoundError:
            return ProviderStatus(
                name=self.name,
                model=self._model,
                reachable=False,
                detail=f"Model {self._model!r} is not available to this account.",
            )
        except openai.APIError as exc:
            return ProviderStatus(
                name=self.name, model=self._model, reachable=False, detail=type(exc).__name__
            )
        return ProviderStatus(name=self.name, model=self._model, reachable=True)

    async def aclose(self) -> None:
        await self._client.close()


def _strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Add ``additionalProperties: false`` to every object in a JSON Schema.

    Strict mode requires it on each object; pydantic emits it on none. Applied
    recursively so nested models and ``$defs`` are covered.
    """
    if schema.get("type") == "object" or "properties" in schema:
        schema["additionalProperties"] = False

    for key in ("properties", "$defs", "definitions"):
        nested = schema.get(key)
        if isinstance(nested, dict):
            for value in nested.values():
                if isinstance(value, dict):
                    _strict_schema(value)

    for key in ("items", "additionalItems"):
        nested_item = schema.get(key)
        if isinstance(nested_item, dict):
            _strict_schema(nested_item)

    for key in ("anyOf", "oneOf", "allOf"):
        variants = schema.get(key)
        if isinstance(variants, list):
            for variant in variants:
                if isinstance(variant, dict):
                    _strict_schema(variant)

    return schema


def _content_of(response: object) -> str:
    choices = getattr(response, "choices", None)
    if isinstance(choices, list) and choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
    return ""


def _usage_of(response: object) -> TokenUsage:
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None)
    completion_tokens = getattr(usage, "completion_tokens", None)
    if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
        return TokenUsage(input_tokens=prompt_tokens, output_tokens=completion_tokens)
    return TokenUsage.unreported()
