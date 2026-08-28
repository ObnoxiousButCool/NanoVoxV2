"""Adapts the on-disk prompt library to the application's prompt port."""

from __future__ import annotations

from typing import Any

from application.ports.prompts import PromptSource, RenderedPrompt
from infrastructure.llm.prompts import PromptLibrary


class FilePromptSource(PromptSource):
    """Serves rendered prompts from versioned markdown files."""

    def __init__(self, library: PromptLibrary) -> None:
        self._library = library

    def render(self, prompt_id: str, **values: Any) -> RenderedPrompt:
        template = self._library.get(prompt_id)
        return RenderedPrompt(
            id=template.id, version=template.version, text=template.render(**values)
        )

    def version_of(self, prompt_id: str) -> str:
        return self._library.get(prompt_id).version
