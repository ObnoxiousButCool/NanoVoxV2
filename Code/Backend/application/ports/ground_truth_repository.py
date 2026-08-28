"""Persistence port for authored corpus expectations (plan A3).

Kept apart from :class:`AnalysisRepository` on purpose. Ground truth is what a
human wrote about a call; an analysis is what the model concluded about it. One
repository holding both would make it easy to join them by accident, and a single
accidental join is all it takes to publish authored figures as measured ones.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from domain.entities.corpus_call import CorpusCall
from domain.entities.ground_truth import GroundTruth


class GroundTruthRepository(ABC):
    """Stores the authored panel that came with each corpus call."""

    @abstractmethod
    async def upsert_many(self, calls: Sequence[CorpusCall]) -> int:
        """Store or refresh ground truth for these calls; report how many were written.

        Upsert rather than insert because the corpus files are the source of
        truth: re-reading a corrected file must update the record, not fail on a
        duplicate or leave the stale version in place.
        """

    @abstractmethod
    async def get(self, reference: str) -> GroundTruth | None:
        """Authored expectations for one call reference, if any were recorded."""
