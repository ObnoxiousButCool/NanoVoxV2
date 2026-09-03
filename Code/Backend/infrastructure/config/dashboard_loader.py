"""Loads ``dashboard.yaml`` into histogram settings and attention rules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from domain.aggregation.attention import AttentionRule, RuleKind
from domain.aggregation.resolution_time import DurationBandSettings
from domain.aggregation.statistics import HistogramSettings
from domain.errors import ConfigurationError, ValidationError
from domain.taxonomy import Taxonomy
from domain.value_objects.severity import Severity
from infrastructure.config.yaml_support import YamlReader, load_yaml_mapping

DESCRIPTION = "Dashboard configuration"
# Used when the file predates the duration_bands key. Matches the shipped
# config, so an upgraded install behaves the same as a fresh one.
DEFAULT_DURATION_BANDS = DurationBandSettings(lower_bounds=(0, 10, 20))
_SEVERITIES = ", ".join(member.value for member in Severity)
_KINDS = ", ".join(member.value for member in RuleKind)


@dataclass(frozen=True)
class DashboardConfig:
    """Everything that decides how the dashboard is computed."""

    version: str
    histogram: HistogramSettings
    duration_bands: DurationBandSettings
    attention_rules: tuple[AttentionRule, ...]


def load_dashboard_config(path: Path, taxonomy: Taxonomy | None = None) -> DashboardConfig:
    """Read and validate the dashboard configuration."""
    data = load_yaml_mapping(path, description=DESCRIPTION)
    reader = YamlReader(data, source=f"{DESCRIPTION} ({path.name})")

    try:
        version = reader.string("version")
        histogram_reader = reader.mapping("histogram")
        edges = tuple(_int_list(histogram_reader, "bin_edges", path))
        histogram = HistogramSettings(
            bin_edges=edges,
            coaching_threshold=histogram_reader.integer("coaching_threshold"),
        )
        # Optional: a dashboard.yaml written before this key existed must keep
        # loading after an upgrade. A missing section is an older file, not a
        # broken one, so it takes the default rather than failing startup.
        duration_bands = (
            DurationBandSettings(
                lower_bounds=tuple(
                    _int_list(reader.mapping("duration_bands"), "lower_bounds", path)
                )
            )
            if reader.has("duration_bands")
            else DEFAULT_DURATION_BANDS
        )
        rules = tuple(_rules(reader))
    except ValidationError as exc:
        raise ConfigurationError(
            f"{DESCRIPTION} file is invalid: {path}", detail=exc.message
        ) from exc

    if not rules:
        raise ConfigurationError(
            f"{DESCRIPTION} file defines no attention rules: {path}",
            detail="An empty queue would look like 'nothing needs attention'.",
        )

    if taxonomy is not None:
        _check_rule_subjects(rules, taxonomy, path)

    return DashboardConfig(
        version=version,
        histogram=histogram,
        duration_bands=duration_bands,
        attention_rules=rules,
    )


def _check_rule_subjects(rules: tuple[AttentionRule, ...], taxonomy: Taxonomy, path: Path) -> None:
    """A rule watching a signal that no longer exists would never fire.

    The same failure mode as a rubric gate watching a renamed signal: silent, and
    only visible as an item that stopped appearing.
    """
    for rule in rules:
        if (
            rule.kind is RuleKind.SIGNAL_PRESENT
            and rule.applies_to is not None
            and not taxonomy.has_signal_type(rule.applies_to)
        ):
            raise ConfigurationError(
                f"{DESCRIPTION} file is invalid: {path}",
                detail=(
                    f"Attention rule {rule.id!r} watches signal "
                    f"{rule.applies_to!r}, which is not defined in the taxonomy. "
                    "The rule would never fire."
                ),
            )


def _int_list(reader: YamlReader, key: str, path: Path) -> list[int]:
    value = reader.require(key)
    if not isinstance(value, list) or not value:
        raise ConfigurationError(
            f"{DESCRIPTION}: {key} must be a non-empty list.", detail=str(path)
        )
    edges: list[int] = []
    for index, entry in enumerate(value):
        if isinstance(entry, bool) or not isinstance(entry, int):
            raise ConfigurationError(
                f"{DESCRIPTION}: {key}[{index}] must be a whole number.", detail=f"Got {entry!r}."
            )
        edges.append(entry)
    return edges


def _rules(reader: YamlReader) -> list[AttentionRule]:
    return [
        AttentionRule(
            id=entry.string("id"),
            kind=entry.enum("kind", RuleKind, expected=f"one of {_KINDS}"),
            title=entry.string("title"),
            minimum=entry.integer("minimum"),
            severity=entry.enum("severity", Severity, expected=f"one of {_SEVERITIES}"),
            owner=entry.string("owner"),
            why=entry.string("why"),
            applies_to=entry.optional_string("applies_to"),
        )
        for entry in reader.sequence_of_mappings("attention_rules")
    ]
