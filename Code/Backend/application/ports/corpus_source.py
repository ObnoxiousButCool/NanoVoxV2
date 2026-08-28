"""Port for reading the authored call corpus."""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.entities.corpus_call import CorpusCall


class CorpusSource(ABC):
    """Supplies the corpus calls a run will analyse."""

    @abstractmethod
    def load(self) -> tuple[CorpusCall, ...]:
        """Read every corpus call, in corpus order.

        Raises:
            ConfigurationError: the corpus location is missing or unreadable. A
                run that silently found zero calls would report success having
                done nothing.
        """

    @abstractmethod
    def describe(self) -> str:
        """Human-readable location, for the UI and for error messages."""
