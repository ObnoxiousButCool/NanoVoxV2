"""Prompts are versioned files, so any stored output traces to exact wording."""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.errors import ConfigurationError, NotFoundError
from infrastructure.llm.prompts import PROMPTS_DIR, PromptLibrary, PromptTemplate

VALID = """---
id: example
version: 2.1.0
description: An example prompt.
---
Analyse {transcript} for {agent}.
"""


def write(directory: Path, name: str, content: str) -> Path:
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


class TestShippedPrompts:
    def test_the_shipped_prompts_load(self) -> None:
        library = PromptLibrary()

        assert "provider_check" in library.ids

    def test_every_shipped_prompt_declares_a_version(self) -> None:
        # The version is stored on every analysis; a prompt without one makes
        # output untraceable.
        library = PromptLibrary()

        for prompt_id in library.ids:
            assert library.get(prompt_id).version

    def test_the_prompt_directory_is_beside_the_adapters(self) -> None:
        assert PROMPTS_DIR.is_dir()


class TestRendering:
    def test_placeholders_are_substituted(self, tmp_path: Path) -> None:
        write(tmp_path, "example.md", VALID)
        template = PromptLibrary(tmp_path).get("example")

        assert template.render(transcript="the call", agent="Brad") == "Analyse the call for Brad."

    def test_the_declared_variables_are_discoverable(self, tmp_path: Path) -> None:
        write(tmp_path, "example.md", VALID)

        assert PromptLibrary(tmp_path).get("example").variables == {"transcript", "agent"}

    def test_a_missing_value_raises_rather_than_leaking_a_placeholder(self, tmp_path: Path) -> None:
        # Emitting a literal "{transcript}" into a prompt would produce a
        # plausible-looking analysis of nothing.
        write(tmp_path, "example.md", VALID)
        template = PromptLibrary(tmp_path).get("example")

        with pytest.raises(ConfigurationError, match="missing values for: agent"):
            template.render(transcript="the call")

    def test_metadata_is_parsed(self, tmp_path: Path) -> None:
        write(tmp_path, "example.md", VALID)
        template = PromptLibrary(tmp_path).get("example")

        assert template.id == "example"
        assert template.version == "2.1.0"
        assert template.description == "An example prompt."


class TestFailureModes:
    def test_a_file_without_front_matter_is_rejected(self, tmp_path: Path) -> None:
        write(tmp_path, "bad.md", "Just a prompt with no metadata.")

        with pytest.raises(ConfigurationError, match="no front matter"):
            PromptLibrary(tmp_path)

    def test_missing_metadata_is_named(self, tmp_path: Path) -> None:
        write(tmp_path, "bad.md", "---\nid: x\nversion: 1.0.0\n---\nBody.\n")

        with pytest.raises(ConfigurationError, match="missing 'description'"):
            PromptLibrary(tmp_path)

    def test_a_malformed_front_matter_line_is_named(self, tmp_path: Path) -> None:
        write(tmp_path, "bad.md", "---\nid x\n---\nBody.\n")

        with pytest.raises(ConfigurationError, match="not 'key: value'"):
            PromptLibrary(tmp_path)

    def test_duplicate_ids_are_refused(self, tmp_path: Path) -> None:
        write(tmp_path, "a.md", VALID)
        write(tmp_path, "b.md", VALID)

        with pytest.raises(ConfigurationError, match="declare id 'example'"):
            PromptLibrary(tmp_path)

    def test_an_empty_directory_is_a_configuration_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="No prompt templates found"):
            PromptLibrary(tmp_path)

    def test_a_missing_directory_is_a_configuration_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="directory not found"):
            PromptLibrary(tmp_path / "absent")

    def test_an_unknown_prompt_names_the_ones_that_exist(self, tmp_path: Path) -> None:
        write(tmp_path, "example.md", VALID)

        with pytest.raises(NotFoundError) as exc_info:
            PromptLibrary(tmp_path).get("nope")

        assert exc_info.value.detail is not None
        assert "example" in exc_info.value.detail


def test_a_template_with_no_placeholders_renders_unchanged() -> None:
    template = PromptTemplate(id="x", version="1", description="d", template="Nothing to fill.")

    assert template.render() == "Nothing to fill."
