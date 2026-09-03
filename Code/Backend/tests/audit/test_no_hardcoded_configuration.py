"""Automated audit gate for D4: configuration lives in configuration, not in code.

Two rules are enforced:

1. No source file outside ``infrastructure/config`` may contain a URL or an
   absolute filesystem path. That package is where defaults are *supposed* to
   live; everywhere else, such a literal is a value that should have been
   injected.
2. Every setting must be documented in ``.env.example``, so nobody has to read
   the source to discover what is configurable.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from infrastructure.config.paths import BACKEND_ROOT
from infrastructure.config.settings import Settings

SOURCE_PACKAGES = ("domain", "application", "infrastructure", "frameworks_drivers")

# Where configuration defaults are allowed to be written as literals.
ALLOWED_LITERAL_PATHS = (
    BACKEND_ROOT / "infrastructure" / "config",
    BACKEND_ROOT / "infrastructure" / "persistence" / "migrations",
)

URL_PATTERN = re.compile(r"https?://")
ABSOLUTE_PATH_PATTERN = re.compile(r"\b[A-Za-z]:[\\/]")


def _source_files() -> list[Path]:
    return [
        path
        for package in SOURCE_PACKAGES
        for path in (BACKEND_ROOT / package).rglob("*.py")
        if not any(path.is_relative_to(allowed) for allowed in ALLOWED_LITERAL_PATHS)
    ]


def test_there_are_source_files_to_audit() -> None:
    # Guards against the audit silently passing because the glob found nothing.
    assert len(_source_files()) > 5


@pytest.mark.parametrize("pattern", [URL_PATTERN, ABSOLUTE_PATH_PATTERN], ids=["url", "abs-path"])
def test_no_configuration_literals_outside_the_config_package(pattern: re.Pattern[str]) -> None:
    offenders: list[str] = []
    for path in _source_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(BACKEND_ROOT)}:{number}: {line.strip()}")

    assert not offenders, (
        "Configuration literals found outside infrastructure/config. "
        "Move these into settings:\n" + "\n".join(offenders)
    )


# A setting entry in the template, whether active or commented out. A setting
# whose default is correct almost everywhere is documented as a commented
# example rather than a live value: the rule is that nobody should have to read
# the source to discover a setting exists, not that every setting must be set.
#
# The distinction matters. Requiring a live value put absolute paths from one
# developer's machine into the template, and every fresh checkout then failed at
# startup looking for a directory that only existed on that machine.
_SETTING_ENTRY = re.compile(r"^\s*#*\s*([A-Z][A-Z0-9_]*)\s*=")


def _documented_settings() -> set[str]:
    example = BACKEND_ROOT / ".env.example"
    return {
        match.group(1).lower()
        for line in example.read_text(encoding="utf-8").splitlines()
        if (match := _SETTING_ENTRY.match(line))
    }


def test_every_setting_is_documented_in_env_example() -> None:
    undocumented = sorted(set(Settings.model_fields) - _documented_settings())

    assert not undocumented, f".env.example is missing: {', '.join(undocumented)}"


def test_env_example_documents_no_settings_that_do_not_exist() -> None:
    stale = sorted(_documented_settings() - set(Settings.model_fields))

    assert not stale, f".env.example documents settings that no longer exist: {', '.join(stale)}"
