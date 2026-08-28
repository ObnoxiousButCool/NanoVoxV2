"""Persistence port for analysed calls."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from domain.entities.analysis import CallAnalysis


class AnalysisRepository(ABC):
    """Stores and retrieves complete call analyses."""

    @abstractmethod
    async def save(self, analysis: CallAnalysis) -> int:
        """Persist an analysis atomically and return its database id."""

    @abstractmethod
    async def get(self, call_id: int) -> CallAnalysis | None:
        """Load one analysis, or ``None`` if there is no such call."""

    @abstractmethod
    async def next_reference(self) -> str:
        """Allocate the next human-facing call reference."""

    @abstractmethod
    async def existing_references(self, references: Sequence[str]) -> frozenset[str]:
        """Which of these references are already stored.

        A corpus run asks this once rather than probing per call: the answer
        decides what it skips, and a hundred round trips to learn it would be a
        hundred round trips before any work started.
        """

    @abstractmethod
    async def delete_by_reference(self, reference: str) -> bool:
        """Remove a stored call by reference; report whether one was there."""
