"""The taxonomy constrains the model so the dashboard can aggregate at all."""

from __future__ import annotations

import pytest

from domain.errors import NotFoundError, ValidationError
from domain.taxonomy import L4Category, Owner, SignalType, Taxonomy
from domain.value_objects.category import Category
from domain.value_objects.severity import Severity

OWNER = Owner(code="operations", name="Operations")


def taxonomy(**overrides: object) -> Taxonomy:
    defaults: dict[str, object] = {
        "categories": (Category("coverage", "Coverage"), Category("claims", "Claims")),
        "l4_categories": (L4Category("process", "Process", OWNER, Severity.HIGH),),
        "signal_types": (SignalType("clinical_risk", "Clinical risk", Severity.CRITICAL),),
        "sentiment_states": ("NEUTRAL", "WORRIED", "DISMISSED"),
    }
    defaults.update(overrides)
    return Taxonomy(**defaults)  # type: ignore[arg-type]


class TestLookups:
    def test_finds_a_category_by_code(self) -> None:
        assert taxonomy().category("claims").label == "Claims"

    def test_an_unknown_code_names_the_ones_that_exist(self) -> None:
        with pytest.raises(NotFoundError) as exc_info:
            taxonomy().category("nonsense")

        assert exc_info.value.detail is not None
        assert "coverage" in exc_info.value.detail

    def test_finds_l4_categories_and_signal_types(self) -> None:
        subject = taxonomy()

        assert subject.l4_category("process").owner.name == "Operations"
        assert subject.signal_type("clinical_risk").severity is Severity.CRITICAL
        assert subject.has_signal_type("clinical_risk")
        assert not subject.has_signal_type("invented")

    def test_unknown_l4_and_signal_lookups_raise(self) -> None:
        with pytest.raises(NotFoundError, match="Unknown L4 category"):
            taxonomy().l4_category("nope")
        with pytest.raises(NotFoundError, match="Unknown signal type"):
            taxonomy().signal_type("nope")


class TestSentimentVocabulary:
    def test_builds_an_arc_from_known_states(self) -> None:
        arc = taxonomy().sentiment_arc("WORRIED", "DISMISSED")

        assert str(arc) == "WORRIED → DISMISSED"

    @pytest.mark.parametrize(
        ("start", "end", "expected"),
        [("INVENTED", "NEUTRAL", "start"), ("NEUTRAL", "INVENTED", "end")],
    )
    def test_rejects_a_state_outside_the_vocabulary(
        self, start: str, end: str, expected: str
    ) -> None:
        # An unconstrained state produces a dashboard category of one.
        with pytest.raises(ValidationError, match=f"Unknown sentiment {expected} state"):
            taxonomy().sentiment_arc(start, end)


class TestValidation:
    def test_rejects_duplicate_category_codes(self) -> None:
        with pytest.raises(ValidationError, match="Duplicate category code"):
            taxonomy(categories=(Category("a", "A"), Category("a", "Again")))

    def test_rejects_duplicate_signal_codes(self) -> None:
        with pytest.raises(ValidationError, match="Duplicate signal type code"):
            taxonomy(
                signal_types=(
                    SignalType("s", "S", Severity.LOW),
                    SignalType("s", "S again", Severity.LOW),
                )
            )

    def test_rejects_duplicate_sentiment_states(self) -> None:
        with pytest.raises(ValidationError, match="duplicate"):
            taxonomy(sentiment_states=("NEUTRAL", "NEUTRAL"))

    def test_requires_at_least_one_category_and_sentiment_state(self) -> None:
        with pytest.raises(ValidationError, match="at least one call category"):
            taxonomy(categories=())
        with pytest.raises(ValidationError, match="sentiment vocabulary"):
            taxonomy(sentiment_states=())

    def test_owner_and_l4_codes_must_not_be_empty(self) -> None:
        with pytest.raises(ValidationError, match="Owner code"):
            Owner(code=" ", name="Operations")
        with pytest.raises(ValidationError, match="must have a name"):
            Owner(code="ops", name=" ")
        with pytest.raises(ValidationError, match="L4 category code"):
            L4Category(" ", "Label", OWNER, Severity.HIGH)
        with pytest.raises(ValidationError, match="Signal type code"):
            SignalType(" ", "Label", Severity.HIGH)
