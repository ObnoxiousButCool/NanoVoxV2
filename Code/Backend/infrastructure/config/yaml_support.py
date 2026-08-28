"""Typed access to parsed YAML.

``yaml.safe_load`` returns ``Any``. These helpers narrow it explicitly and report
the exact path of a malformed value — ``rubric.yaml: dimensions.empathy.negative``
rather than a ``KeyError`` or, worse, a silently wrong default.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import yaml

from domain.errors import ConfigurationError

T = TypeVar("T")


def load_yaml_mapping(path: Path, *, description: str) -> dict[str, object]:
    """Read a YAML file that must contain a mapping at the top level."""
    if not path.is_file():
        raise ConfigurationError(
            f"{description} file not found: {path}",
            detail="Check the corresponding *_PATH setting.",
        )

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            f"{description} file is not valid YAML: {path}", detail=str(exc)
        ) from exc
    except OSError as exc:
        raise ConfigurationError(
            f"{description} file could not be read: {path}", detail=str(exc)
        ) from exc

    if not isinstance(raw, dict):
        raise ConfigurationError(
            f"{description} file must contain a mapping at the top level: {path}"
        )

    return {str(key): value for key, value in raw.items()}


class YamlReader:
    """Reads values out of a parsed mapping, reporting the path of any problem."""

    def __init__(self, data: dict[str, object], *, source: str, path: str = "") -> None:
        self._data = data
        self._source = source
        self._path = path

    def _at(self, key: str) -> str:
        return f"{self._path}.{key}" if self._path else key

    def _fail(self, key: str, expected: str, value: object) -> ConfigurationError:
        return ConfigurationError(
            f"{self._source}: {self._at(key)} must be {expected}.",
            detail=f"Got {value!r}.",
        )

    def require(self, key: str) -> object:
        if key not in self._data:
            raise ConfigurationError(f"{self._source}: {self._at(key)} is required.")
        return self._data[key]

    def string(self, key: str) -> str:
        value = self.require(key)
        if not isinstance(value, str) or not value.strip():
            raise self._fail(key, "a non-empty string", value)
        return value

    def optional_string(self, key: str) -> str | None:
        value = self._data.get(key)
        if value is None:
            return None
        if not isinstance(value, str):
            raise self._fail(key, "a string", value)
        return value

    def integer(self, key: str) -> int:
        value = self.require(key)
        # bool is an int subclass; `positive: true` is a mistake, not a 1.
        if isinstance(value, bool) or not isinstance(value, int):
            raise self._fail(key, "a whole number", value)
        return value

    def mapping(self, key: str) -> YamlReader:
        value = self.require(key)
        if not isinstance(value, dict):
            raise self._fail(key, "a mapping", value)
        return YamlReader(
            {str(k): v for k, v in value.items()}, source=self._source, path=self._at(key)
        )

    def mapping_items(self, key: str) -> list[tuple[str, YamlReader]]:
        reader = self.mapping(key)
        items: list[tuple[str, YamlReader]] = []
        for name in reader.keys():  # noqa: SIM118
            items.append((name, reader.mapping(name)))
        return items

    def sequence_of_mappings(self, key: str) -> list[YamlReader]:
        value = self.require(key)
        if not isinstance(value, list) or not value:
            raise self._fail(key, "a non-empty list", value)

        readers: list[YamlReader] = []
        for index, entry in enumerate(value):
            if not isinstance(entry, dict):
                raise ConfigurationError(
                    f"{self._source}: {self._at(key)}[{index}] must be a mapping.",
                    detail=f"Got {entry!r}.",
                )
            readers.append(
                YamlReader(
                    {str(k): v for k, v in entry.items()},
                    source=self._source,
                    path=f"{self._at(key)}[{index}]",
                )
            )
        return readers

    def sequence_of_strings(self, key: str) -> list[str]:
        value = self.require(key)
        if not isinstance(value, list) or not value:
            raise self._fail(key, "a non-empty list", value)
        for index, entry in enumerate(value):
            if not isinstance(entry, str) or not entry.strip():
                raise ConfigurationError(
                    f"{self._source}: {self._at(key)}[{index}] must be a non-empty string.",
                    detail=f"Got {entry!r}.",
                )
        return [str(entry) for entry in value]

    def enum(self, key: str, factory: Callable[[str], T], *, expected: str) -> T:
        """Read a string and convert it through an enum constructor."""
        value = self.string(key)
        try:
            return factory(value)
        except ValueError as exc:
            raise ConfigurationError(
                f"{self._source}: {self._at(key)} must be {expected}.",
                detail=f"Got {value!r}.",
            ) from exc

    def keys(self) -> list[str]:
        return list(self._data)

    def has(self, key: str) -> bool:
        return key in self._data
