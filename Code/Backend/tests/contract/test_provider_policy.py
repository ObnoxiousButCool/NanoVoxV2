"""The retry / repair / audit policy shared by every provider."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

import pytest

from application.ports.llm_provider import LlmRequest, TokenUsage
from domain.errors import ProviderResponseError, ProviderUnavailableError
from infrastructure.llm.base import (
    OUTCOME_INVALID_SCHEMA,
    OUTCOME_OK,
    OUTCOME_UNAVAILABLE,
    StructuredProvider,
)
from infrastructure.logging.llm_audit import LLM_AUDIT_LOGGER_NAME, LlmAuditLog
from tests.support.llm import VALID_JSON, ScriptedProvider, Sentiment

REQUEST = LlmRequest(
    prompt="Classify: the agent quoted copays and ended the call.",
    response_model=Sentiment,
    prompt_id="provider_check",
    prompt_version="1.0.0",
)


def field(record: logging.LogRecord, name: str) -> Any:
    """Read a value supplied through ``extra=``; those live in the record's dict."""
    return record.__dict__[name]


MALFORMED = "I think it's negative, honestly."
WRONG_SHAPE = '{"sentiment": "NEGATIVE", "confidence": 5.0}'


@pytest.fixture(autouse=True)
def _no_backoff_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retries are exercised for behaviour, not for wall-clock backoff."""
    monkeypatch.setattr(
        ScriptedProvider, "_backoff", staticmethod(lambda attempt, retry_after=None: 0.0)
    )


class TestSuccess:
    async def test_a_valid_response_is_parsed_into_the_response_model(self) -> None:
        provider = ScriptedProvider([VALID_JSON])

        result = await provider.complete(REQUEST)

        assert isinstance(result.value, Sentiment)
        assert result.value.sentiment == "NEGATIVE"
        assert result.attempts == 1
        assert not result.repaired

    async def test_the_result_carries_the_provenance_needed_to_reproduce_it(self) -> None:
        # Every stored analysis must name the provider, model and prompt version
        # that produced it (DEC-01).
        result = await ScriptedProvider([VALID_JSON]).complete(REQUEST)

        assert result.provider == "scripted"
        assert result.model == "scripted-model"
        assert result.prompt_id == "provider_check"
        assert result.prompt_version == "1.0.0"
        assert result.latency_ms >= 0

    async def test_token_usage_is_reported(self) -> None:
        result = await ScriptedProvider([VALID_JSON]).complete(REQUEST)

        assert result.usage.total_tokens == 30
        assert result.usage.reported


class TestTransientFailures:
    async def test_a_transient_failure_is_retried(self) -> None:
        provider = ScriptedProvider([ProviderUnavailableError("timeout"), VALID_JSON])

        result = await provider.complete(REQUEST)

        assert result.attempts == 2

    async def test_retries_stop_at_the_configured_limit(self) -> None:
        provider = ScriptedProvider([ProviderUnavailableError("down")] * 3, max_retries=2)

        with pytest.raises(ProviderUnavailableError):
            await provider.complete(REQUEST)

        assert len(provider.calls) == 3

    async def test_a_persistent_outage_surfaces_rather_than_returning_empty(self) -> None:
        # Never invent a result: an unreachable provider must fail the analysis.
        provider = ScriptedProvider([ProviderUnavailableError("down")], max_retries=0)

        with pytest.raises(ProviderUnavailableError, match="down"):
            await provider.complete(REQUEST)


class TestSchemaRepair:
    async def test_malformed_output_is_repaired_once(self) -> None:
        provider = ScriptedProvider([MALFORMED, VALID_JSON])

        result = await provider.complete(REQUEST)

        assert result.repaired
        assert result.attempts == 2

    async def test_the_repair_attempt_feeds_the_validation_errors_back(self) -> None:
        provider = ScriptedProvider([WRONG_SHAPE, VALID_JSON])

        await provider.complete(REQUEST)

        correction = provider.calls[1]
        assert correction is not None
        assert "justification" in correction
        assert "confidence" in correction

    async def test_repair_is_attempted_only_once(self) -> None:
        # A model that ignored the correction will ignore it again; repeating
        # just spends money on the same mistake.
        provider = ScriptedProvider([MALFORMED, MALFORMED, VALID_JSON])

        with pytest.raises(ProviderResponseError):
            await provider.complete(REQUEST)

        assert len(provider.calls) == 2

    async def test_the_failure_names_the_model_that_could_not_comply(self) -> None:
        provider = ScriptedProvider([MALFORMED, MALFORMED])

        with pytest.raises(ProviderResponseError) as exc_info:
            await provider.complete(REQUEST)

        assert "Sentiment" in exc_info.value.message
        assert exc_info.value.detail is not None

    async def test_a_transient_failure_does_not_consume_the_repair_attempt(self) -> None:
        provider = ScriptedProvider(
            [ProviderUnavailableError("blip"), MALFORMED, VALID_JSON], max_retries=2
        )

        result = await provider.complete(REQUEST)

        assert result.repaired
        assert result.attempts == 3


class TestAuditLog:
    @pytest.fixture
    def audit_records(self) -> Iterator[list[logging.LogRecord]]:
        logger = logging.getLogger(LLM_AUDIT_LOGGER_NAME)
        captured: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(record)

        handler = _Capture()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            yield captured
        finally:
            logger.removeHandler(handler)

    async def test_every_attempt_is_audited(self, audit_records: list[logging.LogRecord]) -> None:
        provider = ScriptedProvider([ProviderUnavailableError("blip"), MALFORMED, VALID_JSON])

        await provider.complete(REQUEST)

        outcomes = [field(record, "outcome") for record in audit_records]
        assert outcomes == [OUTCOME_UNAVAILABLE, OUTCOME_INVALID_SCHEMA, OUTCOME_OK]

    async def test_the_audit_record_carries_cost_and_provenance(
        self, audit_records: list[logging.LogRecord]
    ) -> None:
        await ScriptedProvider([VALID_JSON]).complete(REQUEST)

        record = audit_records[-1]
        assert field(record, "provider") == "scripted"
        assert field(record, "model") == "scripted-model"
        assert field(record, "prompt_version") == "1.0.0"
        assert field(record, "input_tokens") == 10
        assert field(record, "output_tokens") == 20
        assert field(record, "usage_reported") is True

    async def test_prompts_are_not_logged_by_default(
        self, audit_records: list[logging.LogRecord]
    ) -> None:
        # Transcripts are member conversations; an audit log is not where they
        # should accumulate.
        await ScriptedProvider([VALID_JSON]).complete(REQUEST)

        assert not hasattr(audit_records[-1], "prompt")
        assert not hasattr(audit_records[-1], "response")

    async def test_prompts_are_logged_when_explicitly_enabled(
        self, audit_records: list[logging.LogRecord]
    ) -> None:
        provider = ScriptedProvider([VALID_JSON], audit=LlmAuditLog(include_bodies=True))

        await provider.complete(REQUEST)

        assert field(audit_records[-1], "prompt") == REQUEST.prompt
        assert json.loads(field(audit_records[-1], "response"))["sentiment"] == "NEGATIVE"

    async def test_unreported_usage_is_marked_rather_than_shown_as_zero_cost(
        self, audit_records: list[logging.LogRecord]
    ) -> None:
        provider = ScriptedProvider([VALID_JSON], usage=TokenUsage.unreported())

        await provider.complete(REQUEST)

        assert field(audit_records[-1], "usage_reported") is False

    async def test_the_providers_own_reason_reaches_the_audit_record(
        self, audit_records: list[logging.LogRecord]
    ) -> None:
        """A 429 meaning "out of credit" must be tellable from one meaning "slow down"."""
        provider = ScriptedProvider(
            [
                ProviderUnavailableError(
                    "OpenAI returned HTTP 429.",
                    detail="rate_limit_exceeded: tokens per min (TPM): Limit 30000",
                ),
                VALID_JSON,
            ]
        )

        await provider.complete(REQUEST)

        unavailable = [
            record for record in audit_records if field(record, "outcome") == OUTCOME_UNAVAILABLE
        ]
        assert len(unavailable) == 1
        detail = field(unavailable[0], "detail")
        assert "429" in detail
        assert "Limit 30000" in detail


class TestBackoffSchedule:
    """The wait between transport attempts.

    Measured on :class:`StructuredProvider` itself: the autouse fixture above
    stubs the delay out on ``ScriptedProvider``, which is what every other test
    in this file wants and what this one must avoid.
    """

    def test_blind_backoff_grows_and_is_capped(self) -> None:
        backoff = StructuredProvider._backoff
        assert [backoff(n) for n in (1, 2, 3, 4, 5, 6)] == [0.5, 1.0, 2.0, 4.0, 8.0, 8.0]

    def test_a_providers_retry_after_overrides_a_shorter_schedule(self) -> None:
        # A token bucket needing 18s is not served by waiting 0.5s and failing again.
        assert StructuredProvider._backoff(1, 17.931) == pytest.approx(17.931)

    def test_a_retry_after_shorter_than_the_schedule_does_not_shorten_it(self) -> None:
        assert StructuredProvider._backoff(3, 0.1) == 2.0

    def test_an_absurd_retry_after_is_capped(self) -> None:
        # Better to fail the run and resume later than hold a worker for an hour.
        assert StructuredProvider._backoff(1, 3600.0) == 60.0
