"""Audit trail for every model call.

One line per attempt, in its own file, recording provider, model, prompt id and
version, tokens, latency and outcome. This is what answers "which model produced
this score, and what did it cost?" months later — the provenance DEC-01 depends
on, since every figure on the dashboard is model-derived.

Prompt and response bodies are written **only** when ``LOG_LLM_PROMPTS`` is true.
The default is false: transcripts are member conversations, and an audit log is
not the place to accumulate them.
"""

from __future__ import annotations

import logging

LLM_AUDIT_LOGGER_NAME = "nanovox.llm"

logger = logging.getLogger(LLM_AUDIT_LOGGER_NAME)


class LlmAuditLog:
    """Writes structured audit records for model calls."""

    def __init__(self, *, include_bodies: bool = False) -> None:
        self._include_bodies = include_bodies

    def attempt(
        self,
        *,
        provider: str,
        model: str,
        prompt_id: str,
        prompt_version: str,
        attempt: int,
        outcome: str,
        latency_ms: float,
        input_tokens: int,
        output_tokens: int,
        usage_reported: bool,
        detail: str | None = None,
        prompt: str | None = None,
        response: str | None = None,
    ) -> None:
        """Record one attempt, successful or not."""
        record: dict[str, object] = {
            "provider": provider,
            "model": model,
            "prompt_id": prompt_id,
            "prompt_version": prompt_version,
            "attempt": attempt,
            "outcome": outcome,
            "latency_ms": round(latency_ms, 2),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "usage_reported": usage_reported,
        }
        if detail is not None:
            record["detail"] = detail
        if self._include_bodies:
            if prompt is not None:
                record["prompt"] = prompt
            if response is not None:
                record["response"] = response

        logger.info("llm call", extra=record)
