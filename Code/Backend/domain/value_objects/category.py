"""Call category.

A record rather than an enum: the category set is taxonomy data (DEC-02), and
extending it from seven to twelve must be a configuration change plus a
re-classification run, not a code change. No code branches on an individual
category, so nothing here needs to know the members.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.errors import ValidationError


@dataclass(frozen=True)
class Category:
    """One member of the call taxonomy."""

    code: str
    label: str
    description: str | None = None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValidationError("Category code must not be empty.")
        if not self.label.strip():
            raise ValidationError(f"Category {self.code!r} must have a label.")
