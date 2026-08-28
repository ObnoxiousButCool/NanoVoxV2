"""Test doubles for model providers.

The fake provider is what every non-provider test uses: analysis behaviour must
be testable without a model, a network, or a bill.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, Field

from application.ports.llm_provider import (
    LLMProvider,
    LlmRequest,
    ProviderStatus,
    StructuredResult,
    TModel,
    TokenUsage,
)
from domain.errors import ProviderUnavailableError
from infrastructure.llm.base import RawCompletion, StructuredProvider
from infrastructure.logging.llm_audit import LlmAuditLog


class Sentiment(BaseModel):
    """A small response model used across the provider tests."""

    sentiment: str
    justification: str
    confidence: float = Field(ge=0.0, le=1.0)


VALID_JSON = (
    '{"sentiment": "NEGATIVE", "justification": "Cost was prioritised.", "confidence": 0.9}'
)


class ScriptedProvider(StructuredProvider):
    """A provider whose transport is a scripted list of outcomes.

    Each entry is either raw text to return or an exception to raise, letting the
    contract suite drive retry, repair and failure paths without a network.
    """

    def __init__(
        self,
        script: Sequence[str | Exception],
        *,
        max_retries: int = 2,
        audit: LlmAuditLog | None = None,
        usage: TokenUsage | None = None,
    ) -> None:
        super().__init__(
            model="scripted-model",
            timeout_seconds=1.0,
            max_retries=max_retries,
            max_output_tokens=256,
            audit=audit or LlmAuditLog(),
        )
        self._script = list(script)
        self._usage = usage or TokenUsage(input_tokens=10, output_tokens=20)
        self.calls: list[str | None] = []

    @property
    def name(self) -> str:
        return "scripted"

    async def _generate(self, request: LlmRequest[TModel], correction: str | None) -> RawCompletion:
        self.calls.append(correction)
        if not self._script:
            raise AssertionError("ScriptedProvider ran out of scripted responses.")
        step = self._script.pop(0)
        if isinstance(step, Exception):
            raise step
        return RawCompletion(text=step, usage=self._usage)

    async def status(self) -> ProviderStatus:
        return ProviderStatus(name=self.name, model=self.model, reachable=True)


class FakeProvider(LLMProvider):
    """Returns a prepared value. The default double for tests that need a provider."""

    def __init__(self, value: BaseModel, *, name: str = "fake", model: str = "fake-model") -> None:
        self._value = value
        self._name = name
        self._model = model
        self.requests: list[LlmRequest[BaseModel]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, request: LlmRequest[TModel]) -> StructuredResult[TModel]:
        self.requests.append(request)  # type: ignore[arg-type]
        value = request.response_model.model_validate(self._value.model_dump())
        return StructuredResult(
            value=value,
            provider=self._name,
            model=self._model,
            prompt_id=request.prompt_id,
            prompt_version=request.prompt_version,
            usage=TokenUsage(input_tokens=1, output_tokens=1),
            latency_ms=0.1,
            attempts=1,
        )

    async def status(self) -> ProviderStatus:
        return ProviderStatus(name=self._name, model=self._model, reachable=True)


class UnavailableProvider(LLMProvider):
    """A provider that is always down."""

    @property
    def name(self) -> str:
        return "unavailable"

    @property
    def model(self) -> str:
        return "none"

    async def complete(self, request: LlmRequest[TModel]) -> StructuredResult[TModel]:
        raise ProviderUnavailableError("The provider is down.")

    async def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name, model=self.model, reachable=False, detail="ConnectError"
        )
