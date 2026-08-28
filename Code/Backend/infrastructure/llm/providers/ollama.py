"""Ollama adapter — the local, on-premise path.

This is the default provider, and the one the privacy claim in the UI rests on:
inference runs inside this environment and no transcript leaves it.

Ollama supports schema-constrained decoding by passing a JSON Schema as the
``format`` field, which is far more reliable with small local models than asking
for JSON in the prompt and hoping. The repair loop in the base class remains the
safety net.

Called over plain HTTP rather than through an SDK: it is a single POST to a local
server, and the local path should not carry an extra dependency.
"""

from __future__ import annotations

from typing import Any

import httpx2 as httpx

from application.ports.llm_provider import LlmRequest, ProviderStatus, TModel, TokenUsage
from domain.errors import ProviderUnavailableError
from infrastructure.llm.base import DETERMINISTIC_TEMPERATURE, RawCompletion, StructuredProvider
from infrastructure.logging.llm_audit import LlmAuditLog

PROVIDER_NAME = "ollama"

_CHAT_PATH = "/api/chat"
_TAGS_PATH = "/api/tags"


class OllamaProvider(StructuredProvider):
    """Structured completion against a local Ollama server."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        max_output_tokens: int,
        audit: LlmAuditLog,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            model=model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
            audit=audit,
        )
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    async def _generate(self, request: LlmRequest[TModel], correction: str | None) -> RawCompletion:
        messages: list[dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        if correction:
            messages.append({"role": "user", "content": correction})

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            # Schema-constrained decoding: the server enforces the shape.
            "format": request.response_model.model_json_schema(),
            "options": {
                "temperature": DETERMINISTIC_TEMPERATURE,
                "num_predict": self.output_token_budget(request),
            },
        }

        try:
            response = await self._client.post(f"{self._base_url}{_CHAT_PATH}", json=payload)
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            raise ProviderUnavailableError(
                f"Ollama returned HTTP {exc.response.status_code}.",
                detail=_body_excerpt(exc.response),
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                f"Ollama at {self._base_url} could not be reached.", detail=str(exc)
            ) from exc

        return RawCompletion(text=_content_of(body), usage=_usage_of(body))

    async def status(self) -> ProviderStatus:
        try:
            response = await self._client.get(f"{self._base_url}{_TAGS_PATH}")
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPError as exc:
            return ProviderStatus(
                name=self.name,
                model=self._model,
                reachable=False,
                detail=f"Ollama at {self._base_url} could not be reached: {type(exc).__name__}",
            )

        installed = _model_names(body)
        if self._model not in installed:
            # Reachable but unusable: naming the fix is more useful than "down".
            return ProviderStatus(
                name=self.name,
                model=self._model,
                reachable=False,
                detail=f"Model not installed. Run: ollama pull {self._model}",
            )
        return ProviderStatus(name=self.name, model=self._model, reachable=True)

    async def aclose(self) -> None:
        await self._client.aclose()


def _content_of(body: object) -> str:
    if isinstance(body, dict):
        message = body.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content
    return ""


def _usage_of(body: object) -> TokenUsage:
    if not isinstance(body, dict):
        return TokenUsage.unreported()
    prompt_count = body.get("prompt_eval_count")
    output_count = body.get("eval_count")
    if isinstance(prompt_count, int) and isinstance(output_count, int):
        return TokenUsage(input_tokens=prompt_count, output_tokens=output_count)
    return TokenUsage.unreported()


def _model_names(body: object) -> set[str]:
    if not isinstance(body, dict):
        return set()
    models = body.get("models")
    if not isinstance(models, list):
        return set()
    names: set[str] = set()
    for entry in models:
        if isinstance(entry, dict):
            name = entry.get("name")
            if isinstance(name, str):
                names.add(name)
    return names


def _body_excerpt(response: httpx.Response, limit: int = 200) -> str:
    try:
        return response.text[:limit]
    except (UnicodeDecodeError, RuntimeError):  # pragma: no cover - defensive
        return "<unreadable response body>"
