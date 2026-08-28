"""Provider smoke check.

Answers "is this provider actually going to work?" before someone pastes a
transcript and waits. Lists every registered provider's status, and with
``--call`` makes one real structured request so the whole path — schema in,
validated object out, audit line written — is proven end to end.

Run from ``Code/Backend``::

    python -m frameworks_drivers.cli.smoke
    python -m frameworks_drivers.cli.smoke --call
    python -m frameworks_drivers.cli.smoke --call --provider ollama --model llama3.1:latest
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from pydantic import BaseModel, Field

from application.ports.llm_provider import LlmRequest
from domain.errors import NanoVoxError
from infrastructure.config.settings import Settings, get_settings
from infrastructure.llm.prompts import PromptLibrary
from infrastructure.llm.provider_probe import RegistryProviderProbe
from infrastructure.llm.registry import ProviderRegistry
from infrastructure.logging.llm_audit import LlmAuditLog
from infrastructure.logging.setup import configure_logging

PROMPT_ID = "provider_check"
_SENTENCE = (
    "I've had this pressure in my chest since last night, but I told her I'd check the cost first."
)

EXIT_OK = 0
EXIT_FAILED = 1


class SentimentProbe(BaseModel):
    """The shape the probe demands back."""

    sentiment: str = Field(description="POSITIVE, NEUTRAL or NEGATIVE")
    justification: str
    confidence: float = Field(ge=0.0, le=1.0)


def _out(line: str) -> None:
    sys.stdout.write(f"{line}\n")


async def _list(settings: Settings, registry: ProviderRegistry) -> None:
    probe = RegistryProviderProbe(registry, settings.llm_provider)
    _out("Registered providers:")
    for name in registry.names:
        description = await probe.describe(name)
        marker = "OK " if description.selectable else "-- "
        default = " (default)" if description.is_default else ""
        detail = f"  {description.detail}" if description.detail else ""
        _out(f"  {marker}{description.name:<15} {description.model:<28}{default}{detail}")


async def _call(
    settings: Settings, registry: ProviderRegistry, name: str, model: str | None
) -> int:
    prompt = PromptLibrary().get(PROMPT_ID)
    provider = registry.create(name, model)
    _out(f"\nCalling {provider.name} / {provider.model} ...")

    try:
        result = await provider.complete(
            LlmRequest(
                prompt=prompt.render(sentence=_SENTENCE),
                response_model=SentimentProbe,
                prompt_id=prompt.id,
                prompt_version=prompt.version,
            )
        )
    except NanoVoxError as exc:
        _out(f"FAILED: {exc.message}")
        if exc.detail:
            _out(f"        {exc.detail}")
        return EXIT_FAILED
    finally:
        await provider.aclose()

    _out(f"  sentiment     {result.value.sentiment}")
    _out(f"  justification {result.value.justification}")
    _out(f"  confidence    {result.value.confidence}")
    _out(
        f"  attempts {result.attempts}  repaired {result.repaired}  "
        f"{result.latency_ms:.0f} ms  "
        f"tokens {result.usage.input_tokens}+{result.usage.output_tokens}"
        f"{'' if result.usage.reported else ' (not reported)'}"
    )
    return EXIT_OK


async def _run(arguments: argparse.Namespace) -> int:
    settings = get_settings()
    configure_logging(settings)
    registry = ProviderRegistry(settings, LlmAuditLog(include_bodies=settings.log_llm_prompts))

    await _list(settings, registry)
    if not arguments.call:
        return EXIT_OK
    return await _call(
        settings, registry, arguments.provider or settings.llm_provider, arguments.model
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check model provider availability.")
    parser.add_argument("--call", action="store_true", help="Make one real structured request.")
    parser.add_argument("--provider", help="Provider to call. Defaults to LLM_PROVIDER.")
    parser.add_argument("--model", help="Model override for the call.")
    arguments = parser.parse_args(argv)

    try:
        return asyncio.run(_run(arguments))
    except NanoVoxError as exc:
        _out(f"FAILED: {exc.message}")
        if exc.detail:
            _out(f"        {exc.detail}")
        return EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
