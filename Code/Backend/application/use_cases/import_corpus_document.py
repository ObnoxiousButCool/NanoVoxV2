"""Turning an uploaded corpus document into sample call files.

The corpus arrived as a PDF for the first five versions of this product and was
converted by a script somebody had to remember to run, with a Python environment
somebody had to have. This is that conversion as something the operator can do
from the screen.

Two things it deliberately does not do:

* **It does not analyse anything.** Import produces files; a corpus run spends
  money. Keeping them separate means an operator can look at what was extracted
  before committing to the bill.
* **It does not touch the corpus in use.** Files land in their own named
  directory. Promoting one to be *the* corpus is a separate, deliberate act,
  because the stored analyses are only meaningful against the transcripts they
  were made from.
"""

from __future__ import annotations

from dataclasses import dataclass

from application.ports.corpus_document import (
    CorpusDocumentReader,
    CorpusLibrary,
    ImportedCall,
    SavedCorpus,
)
from domain.errors import ValidationError

#: Refused above this. A corpus PDF is a few hundred kilobytes; anything at this
#: size is a mistake, and reading it would hold a worker for the duration.
MAX_DOCUMENT_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class ImportedCallSummary:
    """One extracted call, as the screen lists it.

    Carries what a reader needs to judge whether extraction worked — the number,
    who it is about, and how long the transcript came out — rather than the
    transcript itself, which would make the response enormous for no gain.
    """

    number: int
    reference: str
    title: str
    filename: str
    agent: str | None
    caller: str | None
    tier: str | None
    score: int | None
    resolution: str | None
    queue: str | None
    turns: int
    has_panel: bool
    broker: str | None
    repeat: bool


@dataclass(frozen=True)
class CorpusImport:
    """What one import produced."""

    saved: SavedCorpus
    calls: tuple[ImportedCallSummary, ...]

    @property
    def total(self) -> int:
        return len(self.calls)


@dataclass(frozen=True)
class ImportDocumentCommand:
    """A request to import a corpus document."""

    filename: str
    data: bytes


class ImportCorpusDocument:
    """Extracts calls from an uploaded document and saves them as markdown."""

    def __init__(self, *, reader: CorpusDocumentReader, library: CorpusLibrary) -> None:
        self._reader = reader
        self._library = library

    def execute(self, command: ImportDocumentCommand) -> CorpusImport:
        if not command.data:
            raise ValidationError("The uploaded file is empty.")
        if len(command.data) > MAX_DOCUMENT_BYTES:
            raise ValidationError(
                "That file is too large to import.",
                detail=(
                    f"{len(command.data) / 1_048_576:.1f} MB, against a limit of "
                    f"{MAX_DOCUMENT_BYTES // 1_048_576} MB."
                ),
            )

        # Extraction raises rather than returning partial results, so a document
        # whose shape has changed fails loudly here instead of quietly producing
        # a corpus with holes in it.
        calls = self._reader.extract(command.data)
        files = {call.filename: self._reader.render(call) for call in calls}
        saved = self._library.save(command.filename, files)

        return CorpusImport(
            saved=saved,
            calls=tuple(_summarise(call) for call in calls),
        )

    def versions(self) -> tuple[SavedCorpus, ...]:
        return self._library.versions()


def _summarise(call: ImportedCall) -> ImportedCallSummary:
    return ImportedCallSummary(
        number=call.number,
        # The same mapping the corpus run uses, so an operator comparing this
        # list against the Calls screen is comparing like with like.
        reference=f"C{call.number:04d}",
        title=call.title,
        filename=call.filename,
        agent=call.agent,
        caller=call.caller,
        tier=call.tier,
        score=call.score,
        resolution=call.resolution,
        queue=call.queue,
        # Counted from the rendered transcript's own lines rather than by running
        # the transcript parser: this is a report on extraction, and a parse
        # failure here should not fail the import.
        turns=sum(1 for line in call.transcript.splitlines() if line.strip()),
        has_panel=bool(call.panel),
        broker=call.broker,
        repeat=bool(call.repeat),
    )
