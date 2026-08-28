"""Anthropic adapter.

Uses the official ``anthropic`` SDK, and its structured-output support
(``messages.parse`` with ``output_format``) rather than the tool-use trick the
plan originally named — structured outputs are the current mechanism for exactly
this job, and they guarantee the response parses.

Two details that are easy to get wrong and would fail only at runtime:

* **No sampling parameters.** ``temperature`` / ``top_p`` / ``top_k`` are removed
  on current Claude models and are rejected with a 400. Determinism comes from
  the schema constraint and a directive prompt, not from ``temperature=0``.
* **No date suffix on model IDs.** ``claude-opus-5`` is complete as written.
"""

from __future__ import annotations

import anthropic
from anthropic import AsyncAnthropic

from application.ports.llm_provider import LlmRequest, ProviderStatus, TModel, TokenUsage
from domain.errors import ProviderUnavailableError
from infrastructure.llm.base import RawCompletion, StructuredProvider
from infrastructure.logging.llm_audit import LlmAuditLog

PROVIDER_NAME = "anthropic"
DEFAULT_MODEL = "claude-opus-5"

# A trivial call used only to prove credentials and connectivity.
_STATUS_MAX_TOKENS = 1


class AnthropicProvider(StructuredProvider):
    """Structured completion against the Anthropic Messages API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        max_output_tokens: int,
        audit: LlmAuditLog,
        client: AsyncAnthropic | None = None,
    ) -> None:
        super().__init__(
            model=model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
            audit=audit,
        )
        # The SDK retries transport failures itself; retries are disabled here so
        # that the base class owns retry policy and the audit log sees every
        # attempt. Two independent retry loops would multiply, not add.
        self._client = client or AsyncAnthropic(
            api_key=api_key, timeout=timeout_seconds, max_retries=0
        )

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    async def _generate(self, request: LlmRequest[TModel], correction: str | None) -> RawCompletion:
        prompt = request.prompt if correction is None else f"{request.prompt}\n\n{correction}"

        try:
            response = await self._client.messages.parse(
                model=self._model,
                max_tokens=self.output_token_budget(request),
                system=request.system if request.system else anthropic.omit,
                messages=[{"role": "user", "content": prompt}],
                output_format=request.response_model,
            )
        except anthropic.APIStatusError as exc:
            raise ProviderUnavailableError(
                f"Anthropic returned HTTP {exc.status_code}.", detail=str(exc)
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderUnavailableError(
                "The Anthropic API could not be reached.", detail=str(exc)
            ) from exc

        return RawCompletion(text=_json_text(response), usage=_usage_of(response))

    async def status(self) -> ProviderStatus:
        try:
            await self._client.messages.create(
                model=self._model,
                max_tokens=_STATUS_MAX_TOKENS,
                messages=[{"role": "user", "content": "ping"}],
            )
        except anthropic.AuthenticationError:
            return ProviderStatus(
                name=self.name,
                model=self._model,
                reachable=False,
                detail="ANTHROPIC_API_KEY was rejected.",
            )
        except anthropic.APIError as exc:
            return ProviderStatus(
                name=self.name, model=self._model, reachable=False, detail=type(exc).__name__
            )
        return ProviderStatus(name=self.name, model=self._model, reachable=True)

    async def aclose(self) -> None:
        await self._client.close()


def _json_text(response: object) -> str:
    """The JSON payload of a structured response.

    ``output_format`` guarantees the first text block is valid JSON for the
    schema; the parsed instance is not used directly so that the base class
    remains the single place where validation happens and failures are audited.
    """
    content = getattr(response, "content", None)
    if isinstance(content, list):
        for block in content:
            if getattr(block, "type", None) == "text":
                text = getattr(block, "text", None)
                if isinstance(text, str):
                    return text
    return ""


def _usage_of(response: object) -> TokenUsage:
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    if isinstance(input_tokens, int) and isinstance(output_tokens, int):
        return TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens)
    return TokenUsage.unreported()
