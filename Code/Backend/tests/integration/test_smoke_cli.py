"""The provider smoke command.

Documented in the runbook as the way to answer "is this provider going to work?"
before someone pastes a transcript and waits, so its exit codes and output are
part of the contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from frameworks_drivers.cli import smoke
from infrastructure.config.settings import Settings
from tests.support.settings import make_settings


@pytest.fixture
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    """Point the command at a temporary database with no cloud keys."""
    settings = make_settings(
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'smoke.db').as_posix()}",
        log_enabled=False,
        log_to_console=False,
        log_dir=tmp_path / "logs",
        ollama_base_url="http://127.0.0.1:1",  # nothing listens here
        openai_api_key="",
        anthropic_api_key="",
    )
    monkeypatch.setattr(smoke, "get_settings", lambda: settings)
    return settings


def test_listing_providers_succeeds_even_when_none_are_usable(
    isolated: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    # A local-first deployment with blank cloud keys is the normal state; listing
    # must not fail because of it.
    assert smoke.main([]) == smoke.EXIT_OK

    output = capsys.readouterr().out
    assert "ollama" in output
    assert "openai" in output


def test_unconfigured_providers_are_listed_with_the_reason(
    isolated: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    smoke.main([])

    output = capsys.readouterr().out
    assert "OPENAI_API_KEY is not set" in output
    assert "not implemented in this build" in output


def test_the_default_provider_is_marked(
    isolated: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    smoke.main([])

    assert "(default)" in capsys.readouterr().out


def test_a_call_against_an_unreachable_provider_fails_with_a_reason(
    isolated: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = smoke.main(["--call"])

    assert exit_code == smoke.EXIT_FAILED
    assert "FAILED" in capsys.readouterr().out


def test_selecting_an_unconfigured_provider_names_the_missing_setting(
    isolated: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = smoke.main(["--call", "--provider", "anthropic"])

    assert exit_code == smoke.EXIT_FAILED
    assert "ANTHROPIC_API_KEY is not set" in capsys.readouterr().out


def test_selecting_azure_says_it_is_not_implemented(
    isolated: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    # It must never quietly answer with a different provider.
    exit_code = smoke.main(["--call", "--provider", "azure_foundry"])

    assert exit_code == smoke.EXIT_FAILED
    assert "not implemented in this build" in capsys.readouterr().out


def test_an_unknown_provider_is_reported(
    isolated: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = smoke.main(["--call", "--provider", "gemini"])

    assert exit_code == smoke.EXIT_FAILED
    assert "Unknown model provider" in capsys.readouterr().out
