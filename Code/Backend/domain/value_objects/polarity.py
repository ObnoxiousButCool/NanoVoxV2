"""Direction of a scoring or attribution signal."""

from __future__ import annotations

from enum import Enum


class Polarity(str, Enum):
    """Whether an observation counts for or against."""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"

    @property
    def is_positive(self) -> bool:
        return self is Polarity.POSITIVE
