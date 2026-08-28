"""Loads ``rubric.yaml`` into the domain's :class:`Rubric`."""

from __future__ import annotations

from pathlib import Path

from domain.errors import ConfigurationError, ValidationError
from domain.scoring.rubric import Dimension, Gate, GateCondition, GateEffect, Rubric
from domain.taxonomy import Taxonomy
from domain.value_objects.tier import TierThresholds
from infrastructure.config.yaml_support import YamlReader, load_yaml_mapping

DESCRIPTION = "Rubric"
_CONDITIONS = ", ".join(member.value for member in GateCondition)
_EFFECTS = ", ".join(member.value for member in GateEffect)


def load_rubric(path: Path, taxonomy: Taxonomy | None = None) -> Rubric:
    """Read and validate the rubric file.

    When a taxonomy is supplied, gates that reference a signal are checked
    against it. That cross-check is the point: renaming a signal in the taxonomy
    would otherwise silently disable the clinical safety gate, and nothing would
    fail until a call quietly scored as confirmed that should not have.
    """
    data = load_yaml_mapping(path, description=DESCRIPTION)
    reader = YamlReader(data, source=f"{DESCRIPTION} ({path.name})")

    # Fields are read in declaration order so that a file missing several keys
    # reports the first one a reader would notice, rather than an arbitrary one.
    try:
        version = reader.string("version")
        base_score = reader.integer("base_score")
        max_positive_offset = reader.integer("max_positive_offset")
        dimensions = _dimensions(reader)
        tiers_reader = reader.mapping("tiers")
        tiers = TierThresholds(
            good=tiers_reader.integer("good"),
            average=tiers_reader.integer("average"),
        )
        min_calls = reader.integer("min_calls_for_tier_rating")
        gates = tuple(_gates(reader))

        rubric = Rubric(
            version=version,
            base_score=base_score,
            max_positive_offset=max_positive_offset,
            dimensions=dimensions,
            tiers=tiers,
            min_calls_for_tier_rating=min_calls,
            gates=gates,
        )
    except ValidationError as exc:
        raise ConfigurationError(
            f"{DESCRIPTION} file is invalid: {path}", detail=exc.message
        ) from exc

    if taxonomy is not None:
        _check_gate_signals(rubric, taxonomy, path)

    return rubric


def _dimensions(reader: YamlReader) -> dict[str, Dimension]:
    dimensions: dict[str, Dimension] = {}
    for code, entry in reader.mapping_items("dimensions"):
        dimensions[code] = Dimension(
            code=code,
            label=entry.string("label"),
            positive=entry.integer("positive"),
            negative=entry.integer("negative"),
            max_positive=entry.integer("max_positive"),
            max_negative=entry.integer("max_negative"),
        )
    return dimensions


def _gates(reader: YamlReader) -> list[Gate]:
    if not reader.has("gates"):
        return []
    return [
        Gate(
            id=entry.string("id"),
            condition=entry.enum("condition", GateCondition, expected=f"one of {_CONDITIONS}"),
            argument=entry.string("argument"),
            effect=entry.enum("effect", GateEffect, expected=f"one of {_EFFECTS}"),
            message=entry.string("message"),
        )
        for entry in reader.sequence_of_mappings("gates")
    ]


def _check_gate_signals(rubric: Rubric, taxonomy: Taxonomy, path: Path) -> None:
    for gate in rubric.gates:
        if gate.condition is GateCondition.SIGNAL_PRESENT and not taxonomy.has_signal_type(
            gate.argument
        ):
            raise ConfigurationError(
                f"{DESCRIPTION} file is invalid: {path}",
                detail=(
                    f"Gate {gate.id!r} watches for signal {gate.argument!r}, which is not "
                    "defined in the taxonomy. The gate would never fire."
                ),
            )
