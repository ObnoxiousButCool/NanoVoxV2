"""Model provider port.

The application asks for a *validated object*, never for text. A provider takes a
prompt plus the pydantic model the answer must conform to, and returns an
instance of it — so a caller cannot accidentally consume unparsed output, and the
"did the model return the right shape?" question is answered in one place.

Concrete adapters live in ``infrastructure/llm/providers``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel

TModel = TypeVar("TModel", bound=BaseModel)


@dataclass(frozen=True)
class TokenUsage:
    """Tokens consumed by one request.

    Zero means "the provider did not report it", not "free". The audit log keeps
    the distinction visible so cost figures are never quietly understated.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    reported: bool = True

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @classmethod
    def unreported(cls) -> TokenUsage:
        return cls(input_tokens=0, output_tokens=0, reported=False)


@dataclass(frozen=True)
class LlmRequest(Generic[TModel]):
    """One structured completion request."""

    prompt: str
    response_model: type[TModel]
    system: str | None = None
    prompt_version: str = "unversioned"
    prompt_id: str = "ad-hoc"
    max_output_tokens: int | None = None


@dataclass(frozen=True)
class StructuredResult(Generic[TModel]):
    """A validated answer, with the provenance needed to reproduce it."""

    value: TModel
    provider: str
    model: str
    prompt_id: str
    prompt_version: str
    usage: TokenUsage
    latency_ms: float
    attempts: int
    repaired: bool = False


@dataclass(frozen=True)
class ProviderStatus:
    """Whether a provider is configured and reachable right now."""

    name: str
    model: str
    reachable: bool
    detail: str | None = None
    implemented: bool = True


class LLMProvider(ABC):
    """A model provider capable of returning schema-validated output."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Registry name, e.g. ``ollama``."""

    @property
    @abstractmethod
    def model(self) -> str:
        """The model this instance will call."""

    @abstractmethod
    async def complete(self, request: LlmRequest[TModel]) -> StructuredResult[TModel]:
        """Run the request and return a validated instance of its response model.

        Raises:
            ProviderUnavailableError: the provider could not be reached.
            ProviderResponseError: the provider answered, but never with a
                response matching the schema — including after the repair attempt.
        """

    @abstractmethod
    async def status(self) -> ProviderStatus:
        """Report reachability. Must not raise; an outage is a status, not an error."""

    async def aclose(self) -> None:
        """Release any held connections. Safe to call more than once."""
        return None
