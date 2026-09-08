"""Every constrained vocabulary has to tell the model what its values mean.

A ``Literal`` says which values are allowed and nothing about what any of them
stands for, so the model infers from the name. Measured on the v6 corpus with
resolution as a bare vocabulary: 18 of 61 authored RESOLVED calls came back as
PARTIALLY RESOLVED, and none of the four authored ESCALATED calls was found.
The guards here are what stop a value being added bare again — that is the
defect, and it is invisible at runtime because the model still answers.
"""

from __future__ import annotations

import pathlib
from typing import get_args

import pytest

from application.dto.analysis_schemas import AnalysisSchemas, build_analysis_schemas
from domain.taxonomy import SignalType, Taxonomy
from domain.value_objects.resolution import Resolution
from domain.value_objects.severity import Severity
from infrastructure.config.rubric_loader import load_rubric
from infrastructure.config.taxonomy_loader import load_taxonomy

CONFIG = pathlib.Path(__file__).resolve().parents[2] / "config"


@pytest.fixture(scope="module")
def schemas() -> AnalysisSchemas:
    taxonomy = load_taxonomy(CONFIG / "taxonomy.yaml")
    rubric = load_rubric(CONFIG / "rubric.yaml")
    return build_analysis_schemas(taxonomy, rubric)


@pytest.fixture(scope="module")
def taxonomy() -> Taxonomy:
    return load_taxonomy(CONFIG / "taxonomy.yaml")


def signal_code_field(schemas: AnalysisSchemas) -> str:
    """The ``code`` field of the signal model nested in L1.

    ``get_args`` rather than ``.__args__``: the field annotation is
    ``list[RaisedSignalOut]`` built at runtime, so its type is only ever
    ``type[Any] | None`` as far as a checker is concerned.
    """
    raised = get_args(schemas.l1.model_fields["signals"].annotation)[0]
    return str(raised.model_fields["code"].description)


def resolution_field(schemas: AnalysisSchemas) -> str:
    return str(schemas.l2.model_fields["resolution"].description)


class TestTheDefinitionsReachTheModel:
    def test_every_signal_code_is_defined_in_the_prompt(
        self, schemas: AnalysisSchemas, taxonomy: Taxonomy
    ) -> None:
        described = signal_code_field(schemas)

        for signal in taxonomy.signal_types:
            assert signal.code in described
            assert signal.description is not None
            # The first clause is enough to prove the description travelled
            # rather than only the code and label.
            assert signal.description.split(",")[0].strip() in " ".join(described.split())

    def test_every_resolution_value_is_defined_in_the_prompt(
        self, schemas: AnalysisSchemas
    ) -> None:
        described = resolution_field(schemas)

        for member in Resolution:
            assert member.value in described
            assert member.description.split(":")[0].strip() in " ".join(described.split())

    def test_states_the_boundary_that_was_actually_getting_it_wrong(
        self, schemas: AnalysisSchemas
    ) -> None:
        # The 18-call error was RESOLVED read as PARTIALLY RESOLVED, so the rule
        # separating them has to be in the text: work started and committed to
        # is resolved. Asserted on meaning-bearing words rather than a whole
        # sentence so the wording can be improved without breaking this.
        described = " ".join(resolution_field(schemas).split()).lower()

        assert "follow-up" in described
        assert "does not make the call partial" in described


class TestTheGuardsAgainstAddingAValueBare:
    def test_no_signal_type_ships_without_a_description(self, taxonomy: Taxonomy) -> None:
        bare = [s.code for s in taxonomy.signal_types if not (s.description or "").strip()]

        assert bare == [], f"signal types with no definition for the model: {bare}"

    def test_no_resolution_ships_without_a_description(self) -> None:
        bare = [m.value for m in Resolution if not m.description.strip()]

        assert bare == []


class TestRendering:
    def test_keeps_a_label_that_adds_to_a_snake_case_code(self, schemas: AnalysisSchemas) -> None:
        assert "clinical_risk (Unrecognised clinical urgency)" in signal_code_field(schemas)

    def test_drops_a_label_that_only_restates_the_code(self, schemas: AnalysisSchemas) -> None:
        # "PARTIALLY RESOLVED (Partially Resolved)" is paid for on every call
        # and says nothing.
        described = resolution_field(schemas)

        assert "- PARTIALLY RESOLVED:" in described
        assert "(Partially Resolved)" not in described


class TestCategoryBoundariesThatWereMeasuredWrong:
    """Categories already had a glossary; two of them still needed deciding.

    ``copay`` was chosen for 0 of the v6 corpus's 100 calls while 24 sat in the
    Cost Share & Policy queue, and ``enrollment_id_cards`` took 34 including
    all four Life & Beneficiary calls. Both were descriptions that distinguished
    without deciding, so the rule is asserted here rather than left to wording.
    """

    def test_cost_share_wins_a_call_that_is_both_cost_and_coverage(
        self, taxonomy: Taxonomy
    ) -> None:
        described = taxonomy.category("copay").description or ""

        assert "choose this one" in described

    def test_coverage_benefits_defers_where_an_amount_is_in_question(
        self, taxonomy: Taxonomy
    ) -> None:
        described = taxonomy.category("coverage_benefits").description or ""

        assert "that is copay" in described

    def test_the_cost_share_label_does_not_read_as_only_copays(self, taxonomy: Taxonomy) -> None:
        # The code cannot change; the label is what carries the breadth.
        assert taxonomy.category("copay").label == "Cost Share & Limits"

    def test_enrollment_gives_life_events_about_life_cover_back(self, taxonomy: Taxonomy) -> None:
        described = taxonomy.category("enrollment_id_cards").description or ""

        assert "life_beneficiary" in described

    def test_life_beneficiary_exists_and_says_what_it_takes(self, taxonomy: Taxonomy) -> None:
        described = taxonomy.category("life_beneficiary").description or ""

        assert "beneficiary" in described
        assert "death claim" in described

    def test_a_benefit_exhausted_is_not_a_terminated_policy(self, taxonomy: Taxonomy) -> None:
        # These two both answer "the plan stopped paying" and would otherwise
        # compete: an annual maximum reached is cost share, a policy that ended
        # is termination.
        described = taxonomy.category("copay").description or ""

        assert "coverage_termination" in described

    def test_every_category_reaches_the_model_with_its_definition(
        self, schemas: AnalysisSchemas, taxonomy: Taxonomy
    ) -> None:
        described = " ".join(str(schemas.l2.model_fields["category"].description).split())

        for category in taxonomy.categories:
            assert category.code in described
            assert category.description is not None
            assert category.description.split(",")[0].split("—")[0].strip() in described


class TestSignalTypeDescriptionIsOptional:
    def test_a_signal_type_can_still_be_built_without_one(self) -> None:
        # The field is optional so adding it did not invalidate every existing
        # taxonomy file. The shipped file is held to a higher bar by the guard
        # above.
        signal = SignalType("s", "S", Severity.LOW)

        assert signal.description is None

    def test_the_loader_reads_a_description_when_the_file_states_one(self) -> None:
        taxonomy = load_taxonomy(CONFIG / "taxonomy.yaml")
        clinical = next(s for s in taxonomy.signal_types if s.code == "clinical_risk")

        assert clinical.description is not None
        assert "medication" in clinical.description
