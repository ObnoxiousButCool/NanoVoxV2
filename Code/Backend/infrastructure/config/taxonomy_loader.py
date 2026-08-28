"""Loads ``taxonomy.yaml`` into the domain's :class:`Taxonomy`."""

from __future__ import annotations

from pathlib import Path

from domain.errors import ConfigurationError, ValidationError
from domain.taxonomy import L4Category, Owner, SignalType, Taxonomy
from domain.value_objects.category import Category
from domain.value_objects.severity import Severity
from infrastructure.config.yaml_support import YamlReader, load_yaml_mapping

DESCRIPTION = "Taxonomy"
_SEVERITY_VALUES = ", ".join(member.value for member in Severity)


def load_taxonomy(path: Path) -> Taxonomy:
    """Read and validate the taxonomy file.

    Domain validation errors are re-raised as configuration errors: from the
    operator's point of view a malformed vocabulary is a configuration problem,
    and it should stop startup with a message naming the file.
    """
    data = load_yaml_mapping(path, description=DESCRIPTION)
    reader = YamlReader(data, source=f"{DESCRIPTION} ({path.name})")

    try:
        return Taxonomy(
            categories=tuple(_categories(reader)),
            l4_categories=tuple(_l4_categories(reader)),
            signal_types=tuple(_signal_types(reader)),
            sentiment_states=tuple(reader.sequence_of_strings("sentiment_states")),
        )
    except ValidationError as exc:
        raise ConfigurationError(
            f"{DESCRIPTION} file is invalid: {path}", detail=exc.message
        ) from exc


def _categories(reader: YamlReader) -> list[Category]:
    return [
        Category(
            code=entry.string("code"),
            label=entry.string("label"),
            description=entry.optional_string("description"),
        )
        for entry in reader.sequence_of_mappings("categories")
    ]


def _l4_categories(reader: YamlReader) -> list[L4Category]:
    categories: list[L4Category] = []
    for entry in reader.sequence_of_mappings("l4_categories"):
        owner = entry.mapping("owner")
        categories.append(
            L4Category(
                code=entry.string("code"),
                label=entry.string("label"),
                owner=Owner(code=owner.string("code"), name=owner.string("name")),
                default_severity=entry.enum(
                    "default_severity", Severity, expected=f"one of {_SEVERITY_VALUES}"
                ),
            )
        )
    return categories


def _signal_types(reader: YamlReader) -> list[SignalType]:
    return [
        SignalType(
            code=entry.string("code"),
            label=entry.string("label"),
            severity=entry.enum("severity", Severity, expected=f"one of {_SEVERITY_VALUES}"),
        )
        for entry in reader.sequence_of_mappings("signal_types")
    ]
