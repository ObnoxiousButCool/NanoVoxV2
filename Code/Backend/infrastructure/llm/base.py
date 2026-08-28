"""Shared behaviour for every model provider.

Retry, schema validation, the repair attempt and the audit record live here, not
in the adapters. An adapter's only job is to make one call and translate its own
failures into this module's vocabulary — which is why the contract test suite can
run identically against all of them, and why adding a provider cannot
accidentally come with different retry semantics.

Two failure kinds are treated very differently:

* **Transient** (network, timeout, 429, 5xx) — the request never produced an
  answer, so it is retried with exponential backoff.
* **Schema violation** — the model answered, but not in the required shape. That
  is retried exactly once, with the validation errors fed back as a correction.
  Retrying it further just spends money on the same mistake.
"""

from __future__ import annotations

import asyncio
import time
from abc import abstractmethod
from dataclasses import dataclass

from pydantic import ValidationError as PydanticValidationError

from application.ports.llm_provider import (
    LLMProvider,
    LlmRequest,
    StructuredResult,
    TModel,
    TokenUsage,
)
from domain.errors import ProviderResponseError, ProviderUnavailableError
from infrastructure.logging.llm_audit import LlmAuditLog

# Deterministic decoding is a requirement, not a preference: DEC-03 promises the
# same transcript yields the same analysis. Providers whose current models reject
# sampling parameters simply omit it.
DETERMINISTIC_TEMPERATURE = 0.0

_BACKOFF_BASE_SECONDS = 0.5
_BACKOFF_CAP_SECONDS = 8.0

OUTCOME_OK = "ok"
OUTCOME_INVALID_SCHEMA = "invalid_schema"
OUTCOME_UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class RawCompletion:
    """What an adapter returns: the model's JSON text plus whatever usage it reported."""

    text: str
    usage: TokenUsage


class StructuredProvider(LLMProvider):
    """Base class implementing the retry, repair and audit policy."""

    def __init__(
        self,
        *,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        max_output_tokens: int,
        audit: LlmAuditLog,
    ) -> None:
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max(0, max_retries)
        self._max_output_tokens = max_output_tokens
        self._audit = audit

    @property
    def model(self) -> str:
        return self._model

    @abstractmethod
    async def _generate(self, request: LlmRequest[TModel], correction: str | None) -> RawCompletion:
        """Make one call.

        ``correction`` is set on the repair attempt and carries the validation
        errors from the previous response; adapters append it to the prompt.

        Must raise :class:`ProviderUnavailableError` for transient failures.
        """

    async def complete(self, request: LlmRequest[TModel]) -> StructuredResult[TModel]:
        correction: str | None = None
        attempts = 0
        repair_used = False
        last_error: str = "no attempt was made"

        # One transport attempt per retry, plus one extra pass for the repair.
        max_attempts = self._max_retries + 2

        while attempts < max_attempts:
            attempts += 1
            started = time.perf_counter()

            try:
                raw = await self._generate(request, correction)
            except ProviderUnavailableError as exc:
                last_error = exc.message
                self._record(
                    request,
                    attempts,
                    OUTCOME_UNAVAILABLE,
                    started,
                    TokenUsage.unreported(),
                    exc.message,
                )
                if attempts > self._max_retries:
                    raise
                await asyncio.sleep(self._backoff(attempts))
                continue

            try:
                value = request.response_model.model_validate_json(raw.text)
            except PydanticValidationError as exc:
                last_error = _summarise(exc)
                self._record(
                    request,
                    attempts,
                    OUTCOME_INVALID_SCHEMA,
                    started,
                    raw.usage,
                    last_error,
                    raw.text,
                )
                if repair_used:
                    # The correction was already supplied once and did not help.
                    break
                repair_used = True
                correction = _correction_prompt(last_error)
                continue

            self._record(request, attempts, OUTCOME_OK, started, raw.usage, None, raw.text)
            return StructuredResult(
                value=value,
                provider=self.name,
                model=self._model,
                prompt_id=request.prompt_id,
                prompt_version=request.prompt_version,
                usage=raw.usage,
                latency_ms=(time.perf_counter() - started) * 1000,
                attempts=attempts,
                repaired=repair_used,
            )

        raise ProviderResponseError(
            f"{self.name} did not return output matching "
            f"{request.response_model.__name__} after {attempts} attempts.",
            detail=last_error,
        )

    def _record(
        self,
        request: LlmRequest[TModel],
        attempt: int,
        outcome: str,
        started: float,
        usage: TokenUsage,
        detail: str | None,
        response: str | None = None,
    ) -> None:
        self._audit.attempt(
            provider=self.name,
            model=self._model,
            prompt_id=request.prompt_id,
            prompt_version=request.prompt_version,
            attempt=attempt,
            outcome=outcome,
            latency_ms=(time.perf_counter() - started) * 1000,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            usage_reported=usage.reported,
            detail=detail,
            prompt=request.prompt,
            response=response,
        )

    @staticmethod
    def _backoff(attempt: int) -> float:
        return float(min(_BACKOFF_BASE_SECONDS * 2.0 ** (attempt - 1), _BACKOFF_CAP_SECONDS))

    def output_token_budget(self, request: LlmRequest[TModel]) -> int:
        return request.max_output_tokens or self._max_output_tokens


def _summarise(error: PydanticValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}" for item in error.errors()
    )


def _correction_prompt(errors: str) -> str:
    return (
        "Your previous response did not match the required schema. "
        f"These fields were wrong: {errors}. "
        "Return only a single JSON object matching the schema exactly, with no "
        "commentary, markdown fences, or trailing text."
    )
