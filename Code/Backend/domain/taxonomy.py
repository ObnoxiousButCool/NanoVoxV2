"""The controlled vocabularies the analysis is constrained to.

Everything here is loaded from ``config/taxonomy.yaml``. The distinction against
the enums in ``value_objects`` is deliberate:

* **Enums** (Resolution, Tier, Severity, SpeakerRole, Polarity) are values the
  code branches on individually — first-contact resolution is *defined* as
  RESOLVED. Making those configurable would mean configuration could break
  arithmetic.
* **Taxonomy records** (categories, L4 categories, signal types, sentiment
  states) are values the code only counts and groups by. Those are data, and
  changing them is a configuration edit.

Constraining the model to a vocabulary is what makes the dashboard able to
aggregate at all: free text cannot be grouped.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.errors import NotFoundError, ValidationError
from domain.value_objects.category import Category
from domain.value_objects.sentiment_arc import SentimentArc
from domain.value_objects.severity import Severity


@dataclass(frozen=True)
class Owner:
    """The team accountable for acting on a signal."""

    code: str
    name: str

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValidationError("Owner code must not be empty.")
        if not self.name.strip():
            raise ValidationError(f"Owner {self.code!r} must have a name.")


@dataclass(frozen=True)
class L4Category:
    """An operational-BI action category, with the team that owns it."""

    code: str
    label: str
    owner: Owner
    default_severity: Severity

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValidationError("L4 category code must not be empty.")


@dataclass(frozen=True)
class SignalType:
    """A named condition a call can raise, such as an unrecognised clinical risk."""

    code: str
    label: str
    severity: Severity

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValidationError("Signal type code must not be empty.")


def _index(
    items: tuple[Category, ...] | tuple[L4Category, ...] | tuple[SignalType, ...], kind: str
) -> dict[str, Category | L4Category | SignalType]:
    index: dict[str, Category | L4Category | SignalType] = {}
    for item in items:
        if item.code in index:
            raise ValidationError(f"Duplicate {kind} code in taxonomy: {item.code!r}.")
        index[item.code] = item
    return index


@dataclass(frozen=True)
class Taxonomy:
    """Every controlled vocabulary, loaded once and validated on construction."""

    categories: tuple[Category, ...]
    l4_categories: tuple[L4Category, ...]
    signal_types: tuple[SignalType, ...]
    sentiment_states: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.categories:
            raise ValidationError("Taxonomy must define at least one call category.")
        if not self.sentiment_states:
            raise ValidationError("Taxonomy must define a sentiment vocabulary.")
        _index(self.categories, "category")
        _index(self.l4_categories, "L4 category")
        _index(self.signal_types, "signal type")
        if len(set(self.sentiment_states)) != len(self.sentiment_states):
            raise ValidationError("Taxonomy sentiment states contain a duplicate.")

    def category(self, code: str) -> Category:
        for item in self.categories:
            if item.code == code:
                return item
        raise NotFoundError(
            f"Unknown call category: {code!r}.", detail=self._known(self.categories)
        )

    def l4_category(self, code: str) -> L4Category:
        for item in self.l4_categories:
            if item.code == code:
                return item
        raise NotFoundError(
            f"Unknown L4 category: {code!r}.", detail=self._known(self.l4_categories)
        )

    def signal_type(self, code: str) -> SignalType:
        for item in self.signal_types:
            if item.code == code:
                return item
        raise NotFoundError(
            f"Unknown signal type: {code!r}.", detail=self._known(self.signal_types)
        )

    def has_signal_type(self, code: str) -> bool:
        return any(item.code == code for item in self.signal_types)

    def sentiment_arc(self, start: str, end: str) -> SentimentArc:
        """Build an arc, rejecting states outside the vocabulary.

        Rejecting here is what keeps the dashboard groupable: an unconstrained
        state would produce a category of one.
        """
        for name, state in (("start", start), ("end", end)):
            if state not in self.sentiment_states:
                raise ValidationError(
                    f"Unknown sentiment {name} state: {state!r}.",
                    detail=f"Known states: {', '.join(self.sentiment_states)}",
                )
        return SentimentArc(start=start, end=end)

    @staticmethod
    def _known(
        items: tuple[Category, ...] | tuple[L4Category, ...] | tuple[SignalType, ...],
    ) -> str:
        return f"Known codes: {', '.join(item.code for item in items)}"
