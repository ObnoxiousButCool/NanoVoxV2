"""The shipped configuration must load, and a broken one must fail loudly.

These run against the real `config/*.yaml`, so an edit that breaks the taxonomy
or the rubric fails the build rather than the application at startup.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.errors import ConfigurationError
from domain.value_objects.severity import Severity
from infrastructure.config.paths import DEFAULT_RUBRIC_PATH, DEFAULT_TAXONOMY_PATH
from infrastructure.config.rubric_loader import load_rubric
from infrastructure.config.taxonomy_loader import load_taxonomy

CLINICAL_RISK = "clinical_risk"


class TestShippedTaxonomy:
    def test_loads_the_categories_from_the_corpus_index_and_the_two_added_since(
        self,
    ) -> None:
        taxonomy = load_taxonomy(DEFAULT_TAXONOMY_PATH)

        # DEC-02: seven from call_corpus_v3_index.xlsx, plus copay and
        # coverage_termination, which the index folded into Coverage & Benefits.
        assert len(taxonomy.categories) == 9
        assert taxonomy.category("coverage_benefits").label == "Coverage & Benefits"
        assert taxonomy.category("copay").label == "Copay & Cost Share"
        assert taxonomy.category("coverage_termination").label == "Coverage Termination"

    def test_every_category_says_what_it_covers(self) -> None:
        # The description is not decoration: it is sent to the model as the
        # definition of the code, and a code with none is chosen on its name.
        taxonomy = load_taxonomy(DEFAULT_TAXONOMY_PATH)

        assert all(category.description for category in taxonomy.categories)

    def test_defines_the_six_l4_categories_each_with_an_owner(self) -> None:
        taxonomy = load_taxonomy(DEFAULT_TAXONOMY_PATH)

        assert len(taxonomy.l4_categories) == 6
        assert taxonomy.l4_category("compliance_risk").owner.name == "Compliance"
        assert all(category.owner.name for category in taxonomy.l4_categories)

    def test_defines_the_clinical_risk_signal_the_gate_depends_on(self) -> None:
        taxonomy = load_taxonomy(DEFAULT_TAXONOMY_PATH)

        assert taxonomy.signal_type(CLINICAL_RISK).severity is Severity.CRITICAL

    def test_the_sentiment_vocabulary_covers_the_corpus_arcs(self) -> None:
        taxonomy = load_taxonomy(DEFAULT_TAXONOMY_PATH)

        # Call #89's arc, and Call #1's.
        assert taxonomy.sentiment_arc("WORRIED", "DISMISSED")
        assert taxonomy.sentiment_arc("FRUSTRATED", "REASSURED")


class TestShippedRubric:
    def test_loads_and_cross_checks_against_the_taxonomy(self) -> None:
        taxonomy = load_taxonomy(DEFAULT_TAXONOMY_PATH)
        rubric = load_rubric(DEFAULT_RUBRIC_PATH, taxonomy)

        assert rubric.version
        assert len(rubric.dimensions) == 6
        assert rubric.tiers.good == 86
        # Four, not five: five rated one of the corpus's thirteen agents.
        assert rubric.min_calls_for_tier_rating == 4

    def test_declares_the_clinical_gate(self) -> None:
        rubric = load_rubric(DEFAULT_RUBRIC_PATH, load_taxonomy(DEFAULT_TAXONOMY_PATH))

        gate = next(g for g in rubric.gates if g.argument == CLINICAL_RISK)
        assert gate.message == "Score withheld pending clinical review."

    def test_loads_without_a_taxonomy_when_no_cross_check_is_wanted(self) -> None:
        assert load_rubric(DEFAULT_RUBRIC_PATH).version


class TestFailureModes:
    def test_a_missing_file_names_the_setting_to_check(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="file not found"):
            load_taxonomy(tmp_path / "absent.yaml")

    def test_malformed_yaml_is_reported_as_configuration(self, tmp_path: Path) -> None:
        path = tmp_path / "taxonomy.yaml"
        path.write_text("categories: [oops\n", encoding="utf-8")

        with pytest.raises(ConfigurationError, match="not valid YAML"):
            load_taxonomy(path)

    def test_a_non_mapping_document_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "taxonomy.yaml"
        path.write_text("- just\n- a list\n", encoding="utf-8")

        with pytest.raises(ConfigurationError, match="mapping at the top level"):
            load_taxonomy(path)

    def test_a_missing_key_is_named_by_its_path(self, tmp_path: Path) -> None:
        path = tmp_path / "rubric.yaml"
        path.write_text("version: '1.0.0'\n", encoding="utf-8")

        with pytest.raises(ConfigurationError, match="base_score is required"):
            load_rubric(path)

    def test_a_wrongly_typed_value_names_its_full_path(self, tmp_path: Path) -> None:
        path = tmp_path / "rubric.yaml"
        path.write_text(
            "version: '1.0.0'\n"
            "base_score: 100\n"
            "max_positive_offset: 15\n"
            "dimensions:\n"
            "  empathy:\n"
            "    label: Empathy\n"
            "    positive: yes please\n"
            "    negative: 8\n"
            "    max_positive: 9\n"
            "    max_negative: 24\n"
            "tiers: { good: 86, average: 60 }\n"
            "min_calls_for_tier_rating: 5\n",
            encoding="utf-8",
        )

        with pytest.raises(ConfigurationError) as exc_info:
            load_rubric(path)

        assert "dimensions.empathy.positive must be a whole number" in exc_info.value.message

    def test_a_domain_rule_violation_is_reported_against_the_file(self, tmp_path: Path) -> None:
        path = tmp_path / "rubric.yaml"
        path.write_text(
            "version: '1.0.0'\n"
            "base_score: 100\n"
            "max_positive_offset: 15\n"
            "dimensions:\n"
            "  empathy:\n"
            "    label: Empathy\n"
            "    positive: 3\n"
            "    negative: 30\n"
            "    max_positive: 9\n"
            "    max_negative: 10\n"
            "tiers: { good: 86, average: 60 }\n"
            "min_calls_for_tier_rating: 5\n",
            encoding="utf-8",
        )

        with pytest.raises(ConfigurationError) as exc_info:
            load_rubric(path)

        assert exc_info.value.detail is not None
        assert "max_negative" in exc_info.value.detail

    def test_a_gate_watching_an_undefined_signal_is_refused(self, tmp_path: Path) -> None:
        # Renaming a signal in the taxonomy would otherwise silently disable the
        # clinical gate, and nothing would fail until a call scored as confirmed
        # that should have been withheld.
        path = tmp_path / "rubric.yaml"
        path.write_text(
            "version: '1.0.0'\n"
            "base_score: 100\n"
            "max_positive_offset: 15\n"
            "dimensions:\n"
            "  empathy:\n"
            "    label: Empathy\n"
            "    positive: 3\n"
            "    negative: 8\n"
            "    max_positive: 9\n"
            "    max_negative: 24\n"
            "tiers: { good: 86, average: 60 }\n"
            "min_calls_for_tier_rating: 5\n"
            "gates:\n"
            "  - id: watches_nothing\n"
            "    condition: signal_present\n"
            "    argument: signal_that_does_not_exist\n"
            "    effect: suspend_score\n"
            "    message: Withheld.\n",
            encoding="utf-8",
        )

        with pytest.raises(ConfigurationError) as exc_info:
            load_rubric(path, load_taxonomy(DEFAULT_TAXONOMY_PATH))

        assert exc_info.value.detail is not None
        assert "would never fire" in exc_info.value.detail

    def test_a_taxonomy_that_breaks_a_domain_rule_names_the_file(self, tmp_path: Path) -> None:
        path = tmp_path / "taxonomy.yaml"
        path.write_text(
            "categories:\n"
            "  - { code: a, label: A }\n"
            "  - { code: a, label: A again }\n"
            "l4_categories:\n"
            "  - code: p\n"
            "    label: P\n"
            "    owner: { code: o, name: O }\n"
            "    default_severity: HIGH\n"
            "signal_types:\n"
            "  - { code: s, label: S, severity: HIGH }\n"
            "sentiment_states: [NEUTRAL]\n",
            encoding="utf-8",
        )

        with pytest.raises(ConfigurationError) as exc_info:
            load_taxonomy(path)

        assert exc_info.value.detail is not None
        assert "Duplicate category code" in exc_info.value.detail

    def test_a_rubric_without_gates_is_valid(self, tmp_path: Path) -> None:
        # Gates are optional: a deployment may score without any safety override.
        path = tmp_path / "rubric.yaml"
        path.write_text(
            "version: '1.0.0'\n"
            "base_score: 100\n"
            "max_positive_offset: 15\n"
            "dimensions:\n"
            "  empathy:\n"
            "    label: Empathy\n"
            "    positive: 3\n"
            "    negative: 8\n"
            "    max_positive: 9\n"
            "    max_negative: 24\n"
            "tiers: { good: 86, average: 60 }\n"
            "min_calls_for_tier_rating: 5\n",
            encoding="utf-8",
        )

        assert load_rubric(path).gates == ()

    def test_a_non_mapping_list_entry_is_reported_with_its_index(self, tmp_path: Path) -> None:
        path = tmp_path / "taxonomy.yaml"
        path.write_text(
            "categories:\n  - just a string\nsentiment_states: [NEUTRAL]\n", encoding="utf-8"
        )

        with pytest.raises(ConfigurationError, match=r"categories\[0\] must be a mapping"):
            load_taxonomy(path)

    def test_an_empty_list_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "taxonomy.yaml"
        path.write_text("categories: []\nsentiment_states: [NEUTRAL]\n", encoding="utf-8")

        with pytest.raises(ConfigurationError, match="categories must be a non-empty list"):
            load_taxonomy(path)

    def test_a_blank_string_in_a_list_is_rejected_with_its_index(self, tmp_path: Path) -> None:
        path = tmp_path / "taxonomy.yaml"
        path.write_text(
            "categories:\n"
            "  - { code: a, label: A }\n"
            "l4_categories:\n"
            "  - code: p\n"
            "    label: P\n"
            "    owner: { code: o, name: O }\n"
            "    default_severity: HIGH\n"
            "signal_types:\n"
            "  - { code: s, label: S, severity: HIGH }\n"
            "sentiment_states: ['NEUTRAL', '  ']\n",
            encoding="utf-8",
        )

        with pytest.raises(ConfigurationError, match=r"sentiment_states\[1\]"):
            load_taxonomy(path)

    def test_a_non_mapping_where_a_mapping_is_required_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "rubric.yaml"
        path.write_text(
            "version: '1.0.0'\nbase_score: 100\nmax_positive_offset: 15\ndimensions: nope\n",
            encoding="utf-8",
        )

        with pytest.raises(ConfigurationError, match="dimensions must be a mapping"):
            load_rubric(path)

    def test_a_non_string_description_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "taxonomy.yaml"
        path.write_text(
            "categories:\n"
            "  - { code: a, label: A, description: 42 }\n"
            "sentiment_states: [NEUTRAL]\n",
            encoding="utf-8",
        )

        with pytest.raises(ConfigurationError, match="description must be a string"):
            load_taxonomy(path)

    def test_an_unknown_severity_is_rejected_by_name(self, tmp_path: Path) -> None:
        path = tmp_path / "taxonomy.yaml"
        path.write_text(
            "categories:\n"
            "  - { code: a, label: A }\n"
            "l4_categories:\n"
            "  - code: p\n"
            "    label: P\n"
            "    owner: { code: o, name: O }\n"
            "    default_severity: EXTREMELY_BAD\n"
            "signal_types:\n"
            "  - { code: s, label: S, severity: HIGH }\n"
            "sentiment_states: [NEUTRAL]\n",
            encoding="utf-8",
        )

        with pytest.raises(ConfigurationError, match="default_severity must be one of"):
            load_taxonomy(path)
