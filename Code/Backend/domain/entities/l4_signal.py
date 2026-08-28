"""An operational-BI finding: something that needs doing, and who owns it."""

from __future__ import annotations

from dataclasses import dataclass

from domain.errors import ValidationError
from domain.taxonomy import L4Category
from domain.value_objects.severity import Severity


@dataclass(frozen=True)
class L4Signal:
    """One action signal raised by a call."""

    category: L4Category
    severity: Severity
    narrative: str
    recommended_action: str | None = None

    def __post_init__(self) -> None:
        if not self.narrative.strip():
            raise ValidationError(
                f"L4 signal for {self.category.code!r} must explain what was found."
            )

    @property
    def owner_name(self) -> str:
        return self.category.owner.name
