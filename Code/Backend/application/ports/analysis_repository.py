"""Persistence port for analysed calls."""

from __future__ import annotations

from abc import ABC, abstractmethod

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
