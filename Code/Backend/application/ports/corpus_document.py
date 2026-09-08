"""Reading a corpus document, and saving what came out of it.

Two ports, because the two halves fail differently and are worth swapping
independently: extraction is format-specific and the thing most likely to need a
second implementation (a DOCX corpus, a JSON export), while saving is a
filesystem concern that a deployment may want to point elsewhere.

:class:`ImportedCall` lives here rather than in ``domain`` on purpose. It is not
a call the product knows about — it is a transient record of what one document
said, on its way to becoming the markdown that ``CorpusSource`` then reads. The
domain's :class:`~domain.entities.corpus_call.CorpusCall` is the entity; this is
the courier.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ImportedCall:
    """One call lifted out of a corpus document.

    Every field but the number and transcript is optional. A document that omits
    the end time or the queue is a document with fewer fields, not a broken one,
    and a placeholder written here would be indistinguishable from data.
    """

    number: int
    title: str
    call_date: date | None
    start: str | None
    end: str | None
    handle_seconds: int | None
    queue: str | None
    caller: str | None
    tier: str | None
    score: int | None
    resolution: str | None
    start_mood: str | None
    end_mood: str | None
    agent: str | None
    context: str | None
    topics: str | None
    broker: str | None
    repeat: str | None
    transcript: str
    panel: str

    @property
    def handle_time(self) -> str | None:
        """Handle time as the corpus writes it: ``5m 21s``, or ``9m``."""
        if self.handle_seconds is None:
            return None
        minutes, seconds = divmod(self.handle_seconds, 60)
        return f"{minutes}m {seconds}s" if seconds else f"{minutes}m"

    @property
    def filename(self) -> str:
        return f"call_{self.number:03d}.md"


@dataclass(frozen=True)
class SavedCorpus:
    """Where an imported corpus landed, and what is in it."""

    name: str
    directory: Path
    files: int


class CorpusDocumentReader(Protocol):
    """Turns an uploaded document into calls, and calls into corpus markdown."""

    def extract(self, data: bytes) -> tuple[ImportedCall, ...]:
        """Every call the document contains.

        Raises:
            ValidationError: if the document carries no calls, numbers two the
                same, or has headings that yielded no transcript. Extraction is
                deliberately all-or-nothing: a partial corpus analyses and
                reports successfully while quietly missing evidence.
        """
        ...

    def render(self, call: ImportedCall) -> str:
        """One call as the markdown that ``CorpusSource`` reads."""
        ...


class CorpusLibrary(Protocol):
    """Stores imported corpora as named, separate directories."""

    def save(self, name: str, files: dict[str, str]) -> SavedCorpus:
        """Write ``{filename: content}`` under ``name``, replacing that name.

        Replacing only the one name is the point: an import must not be able to
        overwrite the corpus a stored analysis was made from.
        """
        ...

    def versions(self) -> tuple[SavedCorpus, ...]:
        """Every corpus in the library, newest first."""
        ...
