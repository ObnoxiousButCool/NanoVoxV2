"""The shipped dashboard configuration, and what happens when it is wrong."""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.aggregation.attention import RuleKind
from domain.errors import ConfigurationError
from domain.value_objects.severity import Severity
from infrastructure.config.dashboard_loader import load_dashboard_config
from infrastructure.config.paths import DEFAULT_DASHBOARD_PATH, DEFAULT_TAXONOMY_PATH
from infrastructure.config.taxonomy_loader import load_taxonomy

MINIMAL = """
version: "1.0.0"
histogram:
  bin_edges: [0, 50, 90]
  coaching_threshold: 60
attention_rules:
  - id: a_rule
    kind: signal_present
    applies_to: clinical_risk
    title: Something happened
    minimum: 1
    severity: HIGH
    owner: Operations
    why: "{count} calls."
"""


def write(directory: Path, content: str) -> Path:
    path = directory / "dashboard.yaml"
    path.write_text(content, encoding="utf-8")
    return path


class TestShippedConfiguration:
    def test_it_loads(self) -> None:
        config = load_dashboard_config(DEFAULT_DASHBOARD_PATH)

        assert config.version
        assert config.histogram.bin_edges[0] == 0
        assert config.attention_rules

    def test_the_coaching_threshold_matches_the_rubric_average_floor(self) -> None:
        # A histogram marking a different band than the rubric calls POOR would
        # colour bars that disagree with the tier beside them.
        config = load_dashboard_config(DEFAULT_DASHBOARD_PATH)

        assert config.histogram.coaching_threshold == 60

    def test_every_rule_names_an_owner_and_a_severity(self) -> None:
        for rule in load_dashboard_config(DEFAULT_DASHBOARD_PATH).attention_rules:
            assert rule.owner
            assert isinstance(rule.severity, Severity)

    def test_every_signal_rule_names_the_signal_it_watches(self) -> None:
        # Without this a rule fires on any signal and headlines it wrongly.
        rules = load_dashboard_config(DEFAULT_DASHBOARD_PATH).attention_rules

        for rule in rules:
            if rule.kind is RuleKind.SIGNAL_PRESENT:
                assert rule.applies_to, f"{rule.id} watches every signal"

    def test_it_cross_checks_against_the_shipped_taxonomy(self) -> None:
        taxonomy = load_taxonomy(DEFAULT_TAXONOMY_PATH)

        assert load_dashboard_config(DEFAULT_DASHBOARD_PATH, taxonomy).attention_rules


class TestFailureModes:
    def test_a_rule_watching_an_undefined_signal_is_refused(self, tmp_path: Path) -> None:
        # The same failure mode as a rubric gate watching a renamed signal:
        # silent, and visible only as an item that stopped appearing.
        path = write(tmp_path, MINIMAL.replace("clinical_risk", "signal_that_does_not_exist"))

        with pytest.raises(ConfigurationError) as exc_info:
            load_dashboard_config(path, load_taxonomy(DEFAULT_TAXONOMY_PATH))

        assert exc_info.value.detail is not None
        assert "would never fire" in exc_info.value.detail

    def test_a_config_with_no_rules_is_refused(self, tmp_path: Path) -> None:
        # An empty queue would read as "nothing needs attention".
        path = write(tmp_path, MINIMAL.split("attention_rules:")[0] + "attention_rules: []\n")

        with pytest.raises(ConfigurationError, match="non-empty list"):
            load_dashboard_config(path)

    def test_an_unknown_rule_kind_is_named(self, tmp_path: Path) -> None:
        path = write(tmp_path, MINIMAL.replace("kind: signal_present", "kind: vibes"))

        with pytest.raises(ConfigurationError, match="kind must be one of"):
            load_dashboard_config(path)

    def test_a_non_numeric_bin_edge_is_rejected(self, tmp_path: Path) -> None:
        path = write(tmp_path, MINIMAL.replace("[0, 50, 90]", "[0, 'fifty', 90]"))

        with pytest.raises(ConfigurationError, match="must be a whole number"):
            load_dashboard_config(path)

    def test_a_rule_without_an_owner_is_reported_against_the_file(self, tmp_path: Path) -> None:
        path = write(tmp_path, MINIMAL.replace("owner: Operations", "owner: '  '"))

        with pytest.raises(ConfigurationError, match="must be a non-empty string"):
            load_dashboard_config(path)

    def test_an_unusable_threshold_is_reported_against_the_file(self, tmp_path: Path) -> None:
        path = write(tmp_path, MINIMAL.replace("minimum: 1", "minimum: 0"))

        with pytest.raises(ConfigurationError) as exc_info:
            load_dashboard_config(path)

        assert exc_info.value.detail is not None
        assert "at least 1" in exc_info.value.detail

    def test_a_missing_file_names_the_setting_to_check(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="file not found"):
            load_dashboard_config(tmp_path / "absent.yaml")
