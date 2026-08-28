"""The adapter between the on-disk prompt library and the application port."""

from __future__ import annotations

import pytest

from domain.errors import ConfigurationError, NotFoundError
from infrastructure.llm.prompt_source import FilePromptSource
from infrastructure.llm.prompts import PromptLibrary

SOURCE = FilePromptSource(PromptLibrary())


def test_it_renders_a_shipped_prompt_with_its_version() -> None:
    rendered = SOURCE.render("provider_check", sentence="The member sounded worried.")

    assert rendered.id == "provider_check"
    assert rendered.version
    assert "The member sounded worried." in rendered.text


def test_the_version_is_readable_without_rendering() -> None:
    # Provenance is recorded per analysis; asking for it must not need the
    # prompt's variables.
    assert (
        SOURCE.version_of("provider_check") == SOURCE.render("provider_check", sentence="x").version
    )


def test_a_missing_variable_raises_rather_than_leaking_a_placeholder() -> None:
    with pytest.raises(ConfigurationError, match="missing values"):
        SOURCE.render("provider_check")


def test_an_unknown_prompt_is_reported() -> None:
    with pytest.raises(NotFoundError, match="Unknown prompt"):
        SOURCE.version_of("no_such_prompt")
