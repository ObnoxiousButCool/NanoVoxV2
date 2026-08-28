"""Prompt source port.

The use case needs rendered prompt text and the version that produced it; it must
not know that prompts happen to be markdown files on disk.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RenderedPrompt:
    """A prompt ready to send, carrying the version to record against the result."""

    id: str
    version: str
    text: str


class PromptSource(ABC):
    """Supplies rendered, versioned prompts."""

    @abstractmethod
    def render(self, prompt_id: str, **values: Any) -> RenderedPrompt:
        """Render the named prompt. Raises if a required value is missing."""

    @abstractmethod
    def version_of(self, prompt_id: str) -> str:
        """The version of the named prompt."""
