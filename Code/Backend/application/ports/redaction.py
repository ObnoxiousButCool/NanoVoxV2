"""Redaction port.

A no-op in this build (DEC-08): the corpus is synthetic, so there is nothing to
redact. The port exists anyway, and the pipeline calls it, because the difference
between "we would have to restructure the pipeline" and "we implement one
adapter" is the difference between a week and an afternoon when real member data
arrives.

**This is a hard prerequisite before any real transcript reaches a cloud
provider.** The no-op implementation says so in its own docstring so nobody
mistakes its presence for protection.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.entities.transcript import Transcript


class RedactionPort(ABC):
    """Removes personally identifying detail before analysis."""

    @abstractmethod
    def redact(self, transcript: Transcript) -> Transcript:
        """Return a transcript safe to send to a model provider."""

    @property
    @abstractmethod
    def is_active(self) -> bool:
        """Whether this implementation actually removes anything."""


class NoRedaction(RedactionPort):
    """Passes the transcript through unchanged.

    Correct for a synthetic corpus and **not** correct for real member calls.
    ``is_active`` is False so callers and operators can tell the difference.
    """

    def redact(self, transcript: Transcript) -> Transcript:
        return transcript

    @property
    def is_active(self) -> bool:
        return False
