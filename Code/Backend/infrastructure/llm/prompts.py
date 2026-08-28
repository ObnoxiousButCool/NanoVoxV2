"""Versioned prompt templates.

Prompts are files, not string literals, and each carries a version in its front
matter. That version is stored on every analysis, so any stored output can be
traced back to the exact wording that produced it — without which "the scores
changed last Tuesday" is unanswerable.

Templates use ``str.format`` placeholders. Rendering with a missing variable
raises rather than silently emitting ``{transcript}`` into the prompt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from domain.errors import ConfigurationError, NotFoundError

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

_FRONT_MATTER = re.compile(r"^---\s*\n(?P<meta>.*?)\n---\s*\n(?P<body>.*)$", re.DOTALL)
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


@dataclass(frozen=True)
class PromptTemplate:
    """One versioned prompt."""

    id: str
    version: str
    description: str
    template: str

    @property
    def variables(self) -> frozenset[str]:
        return frozenset(_PLACEHOLDER.findall(self.template))

    def render(self, **values: Any) -> str:
        missing = self.variables - set(values)
        if missing:
            raise ConfigurationError(
                f"Prompt {self.id!r} is missing values for: {', '.join(sorted(missing))}."
            )
        return self.template.format(**values)


def _parse(path: Path) -> PromptTemplate:
    text = path.read_text(encoding="utf-8")
    match = _FRONT_MATTER.match(text)
    if match is None:
        raise ConfigurationError(
            f"Prompt file has no front matter: {path}",
            detail="Expected an opening '---' block declaring id, version and description.",
        )

    meta: dict[str, str] = {}
    for line in match.group("meta").splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise ConfigurationError(
                f"Prompt front matter line is not 'key: value': {line!r}", detail=str(path)
            )
        meta[key.strip()] = value.strip()

    for required in ("id", "version", "description"):
        if required not in meta:
            raise ConfigurationError(f"Prompt front matter is missing {required!r}: {path}")

    return PromptTemplate(
        id=meta["id"],
        version=meta["version"],
        description=meta["description"],
        template=match.group("body").strip(),
    )


class PromptLibrary:
    """Loads and serves the prompt templates on disk."""

    def __init__(self, directory: Path = PROMPTS_DIR) -> None:
        self._directory = directory
        self._templates: dict[str, PromptTemplate] = {}
        self._load()

    def _load(self) -> None:
        if not self._directory.is_dir():
            raise ConfigurationError(f"Prompt directory not found: {self._directory}")

        for path in sorted(self._directory.glob("*.md")):
            template = _parse(path)
            if template.id in self._templates:
                raise ConfigurationError(
                    f"Two prompt files declare id {template.id!r}.", detail=str(path)
                )
            self._templates[template.id] = template

        if not self._templates:
            raise ConfigurationError(f"No prompt templates found in {self._directory}")

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._templates))

    def get(self, prompt_id: str) -> PromptTemplate:
        try:
            return self._templates[prompt_id]
        except KeyError as exc:
            raise NotFoundError(
                f"Unknown prompt: {prompt_id!r}.",
                detail=f"Known prompts: {', '.join(self.ids)}",
            ) from exc
