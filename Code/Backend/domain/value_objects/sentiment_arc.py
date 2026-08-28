"""Sentiment arc: where the member started and where they ended.

The corpus contains 44 distinct arcs built from roughly two dozen states. Holding
the two ends separately, drawn from a controlled vocabulary, is what lets the
dashboard group them — a free-text "WORRIED → DISMISSED" cannot be aggregated.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.errors import ValidationError

ARROW = "→"


@dataclass(frozen=True)
class SentimentArc:
    """Opening and closing member sentiment, as vocabulary codes."""

    start: str
    end: str

    def __post_init__(self) -> None:
        for name, value in (("start", self.start), ("end", self.end)):
            if not value.strip():
                raise ValidationError(f"Sentiment arc {name} state must not be empty.")

    @property
    def improved(self) -> bool:
        return self.start != self.end

    def __str__(self) -> str:
        return f"{self.start} {ARROW} {self.end}"
